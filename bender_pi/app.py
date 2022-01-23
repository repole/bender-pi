"""
    bender_pi.__init__
    ~~~~~~~~~~~~~~~~~~

    Houses the bender-pi hermes app.

"""
# :copyright: (c) 2022 by Nicholas Repole
# :license: MIT - See LICENSE for more details.

import aiohttp
import asyncio
import configparser
import json
import logging
import os
import re
from rhasspyhermes_app import HermesApp, HotwordDetected, TopicData

_LOGGER = logging.getLogger("asyncio")

MEDIA_CENTER_VOL = None
BENDER_VOL = None
CONFIG = configparser.ConfigParser()
CONFIG.read(os.path.join(__file__, "..", "config.cfg"))
API_URL = (
    CONFIG["MEDIA_CENTER"]["PROTOCOL"] +
    "://" +
    CONFIG["MEDIA_CENTER"]["HOST"] +
    ":" +
    CONFIG["MEDIA_CENTER"]["PORT"])

app = HermesApp(
    "Bender",
    host=CONFIG["MQTT"]["HOST"],
    port=CONFIG["MQTT"]["PORT"])


async def run_cmd(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await proc.communicate()
    return proc.returncode, stdout, stderr


async def mute_media_center(client_session):
    _LOGGER.info("MC dim")
    data = {"volumeLevel": "mute"}
    url = f"{API_URL}/api/mediaCenter/speakers/volume"
    async with client_session.post(url, json=data) as response:
        result = await response.read()
        return


async def unmute_media_center(client_session):
    _LOGGER.info("MC undim")
    data = {"volumeLevel": "unmute"}
    url = f"{API_URL}/api/mediaCenter/speakers/volume"
    async with client_session.post(url, json=data) as response:
        result = await response.read()
        return


async def dim_bender():
    _LOGGER.info("Bender dim")
    return_code, stdout, stderr = await run_cmd("amixer sget Snapcast")
    vol_pattern = re.compile(r"\[(.*?)\]")
    vol_match = vol_pattern.search(stdout.decode())
    if vol_match:
        vol = vol_match.group().replace("[", "").replace("]", "")
        global BENDER_VOL
        BENDER_VOL = vol
    await run_cmd("amixer -c 2 set Snapcast 50%")


async def undim_bender():
    _LOGGER.info("Bender undim")
    vol = BENDER_VOL
    if vol is not None:
        await run_cmd(f"amixer -c 2 set Snapcast {vol}%")


@app.on_hotword
async def wake(hotword: HotwordDetected):
    _LOGGER.info(f"Handle hotword for {hotword.site_id}")
    if not hotword.site_id == CONFIG["GLOBAL"]["SITE_ID"]:
        return
    async with aiohttp.ClientSession() as client_session:
        results = await asyncio.gather(
            mute_media_center(client_session),
            dim_bender())


@app.on_topic("hermes/tts/say")
async def handle_say(data: TopicData, payload: bytes):
    payload = json.loads(payload)
    if not payload.get("siteId") == CONFIG["GLOBAL"]["SITE_ID"]:
        return
    _LOGGER.info("Handle say for " + payload.get("siteId"))
    async with aiohttp.ClientSession() as client_session:
        results = await asyncio.gather(
            mute_media_center(client_session),
            dim_bender())


@app.on_topic("hermes/tts/sayFinished")
async def handle_say_finished(data: TopicData, payload: bytes):
    payload = json.loads(payload)
    if not payload.get("siteId") == CONFIG["GLOBAL"]["SITE_ID"]:
        return
    _LOGGER.info("Handle sayFinished for " + payload.get("siteId"))
    async with aiohttp.ClientSession() as client_session:
        results = await asyncio.gather(
            unmute_media_center(client_session),
            undim_bender())
        _LOGGER.info("dim done")


@app.on_topic("hermes/asr/textCaptured")
async def handle_text_captured(data: TopicData, payload: bytes):
    payload = json.loads(payload)
    if not payload.get("siteId") == CONFIG["GLOBAL"]["SITE_ID"]:
        return
    _LOGGER.info("Handle textCaptured for " + payload.get("siteId"))
    async with aiohttp.ClientSession() as client_session:
        results = await asyncio.gather(
            unmute_media_center(client_session),
            undim_bender())


@app.on_topic("hermes/error/asr")
async def handle_text_captured(data: TopicData, payload: bytes):
    payload = json.loads(payload)
    if not payload.get("siteId") == CONFIG["GLOBAL"]["SITE_ID"]:
        return
    _LOGGER.info("Handle ASR error for " + payload.get("siteId"))
    async with aiohttp.ClientSession() as client_session:
        results = await asyncio.gather(
            unmute_media_center(client_session),
            undim_bender())
