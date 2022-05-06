# there is some coroutines
import asyncio
import json
import logging
from functools import reduce
from typing import Optional

import aiohttp
import async_timeout

from myhouse.aiolistener.utils import notify
from myhouse.models import Device
from myhouse.mqtt import get_mqtt_async_client

logger = logging.getLogger(__name__)

loop = asyncio.get_event_loop()

__http_session: Optional[aiohttp.ClientSession] = None


def get_http_session(timeout=30):
    global __http_session
    if __http_session is not None and not __http_session.closed:
        return __http_session
    __http_session = aiohttp.ClientSession(conn_timeout=timeout, read_timeout=timeout)
    return __http_session


async def make_turn_http_request(device, relay, mode, new_value):
    session = get_http_session()
    if isinstance(relay, (list, tuple)):
        params = {f'{mode}{r}': str(new_value) for r in relay}
    elif isinstance(relay, dict):
        params = {f'{mode}{r}': str(v) for r, v in relay.items()}
    else:
        params = {f'{mode}{relay}': str(new_value)}

    url = 'http://{}/turn'.format(device.ip_address)

    response = await session.get(url, params=params)
    if mode == 'd' and response.status == 404:
        url = 'http://{}/dimm'.format(device.ip_address)
        response = await session.get(url, params=params)
    response_text = await response.read()
    response.close()
    response.raise_for_status()
    try:
        response_data = await response.json()
    except:
        response_data = response_text
    logger.info('from turn url %s ? %s response status=%s, response text = %s',
                response.request_info.url, params,
                response.status, response_data)
    return response_text


async def turn(device: Device, relay, new_value='on', notify_new_state=True, mode='r'):
    if device.device_type.startswith('broadlink/'):
        from myhouse.rules.broadlink import turn
        try:
            from flask import current_app
            with current_app.app_context():
                result = await loop.run_in_executor(None, turn, device, new_value)
            if notify_new_state:
                await get_broadlink_device_status(device, True, True)
            return True
        except Exception as err:
            logger.error('Error in request turn for device {}'.format(device.ip_address))
            logger.exception(err)
            return False

    mode = mode == 'r' and 'r' or 'd'  # relays or dimmers
    for try_no in range(3):
        try:
            with async_timeout.timeout(30):
                response_text = await make_turn_http_request(device, relay, mode, new_value)
                if notify_new_state and response_text is not None:
                    await notify(device.mac_address, response_text.decode('utf8'), 'state')
            logger.debug("Turn successful. Dev=%s, %s to %s. Result=%s",
                         device.mac_address, relay, new_value, response_text)
            return response_text is not None
        except asyncio.TimeoutError:
            logger.error('Timeout when try to turn device %s %s', device.name, device.ip_address)
        except Exception as err:
            logger.error('Error in request turn for device %s. %s', device.ip_address, device.mac_address)
            logger.exception(err)
        logger.info("Make next try to turn device %s (%s)", device.name, device.ip_address)
    return False


async def get_broadlink_device_status(device: Device, notify_new_state=True, include_device_info=False):
    from . import broadlink
    device_json = await loop.run_in_executor(None, broadlink.get_status, device)
    is_online = bool(device_json)
    if not is_online:
        device_json = {}
    if notify_new_state:
        if include_device_info:
            device_json['device_info'] = device.as_dict()
            device_json['device_info']['is_online'] = is_online
        await notify(device.mac_address, json.dumps(device_json), 'state')
    return device_json


async def get_device_status(device: Device, notify_new_state=True, include_device_info=False):
    if device.device_type.startswith('broadlink/'):
        return await get_broadlink_device_status(device, notify_new_state, include_device_info)
    session = get_http_session()
    logger.info(f"Ask status from http://{device.ip_address}/")
    try:
        response = await session.get(
            'http://{}/'.format(device.ip_address)
        )
        if response.status == 200 or include_device_info:
            if response.status == 200:
                device_json = await response.text()
                device_json = json.loads(device_json)
            else:
                device_json = {}
            if notify_new_state:
                if include_device_info:
                    device_json['device_info'] = device.as_dict()
                    if response.status != 200:
                        device_json['device_info']['is_online'] = False
                logger.info(f"Notify new state of {device.name} {device.ip_address}")
                await notify(device.mac_address, json.dumps(device_json), 'state')
            response.close()
            return device_json
        response.close()
    except Exception as error:
        logger.exception(error)
    return None


async def http_query_device(device, query_path, params=None):
    session = get_http_session()
    try:
        url = 'http://{}/{}'.format(device.ip_address, query_path)
        response = await session.get(url, params=params)
        if response.status == 200:
            device_json = await response.text()
            try:
                device_json = json.loads(device_json)
            except Exception as error:
                logger.exception(error)
                logger.error("response text: %s", device_json)
                device_json = {}
        else:
            logger.debug(f'Got response from {device.name}({device.ip_address}) with status = {response.status}')
            device_json = {}
        response.close()
        return device_json
    except Exception as error:
        logger.exception(error)



async def get_device_by_mac(mac):
    filter_result = await loop.run_in_executor(None, Device.query.filter, Device.mac_address == mac)
    return await loop.run_in_executor(None, filter_result.first)



async def get_all_devices():
    result = await loop.run_in_executor(None, Device.query.all)
    return result



async def update_device_info(device, info):
    result = await loop.run_in_executor(None, device.check_and_update, info)
    return result


@asyncio.coroutine
def update_device_info_unsafe(device, info):
    result = yield from loop.run_in_executor(None, device.update, **info)
    return result


@asyncio.coroutine
def get_device_by_id(device_id):
    result = yield from loop.run_in_executor(None, Device.get_by_id, device_id)
    return result


def update_device(device_id, kwargs):
    from myhouse.runner import app
    with app.app_context():
        # logger.debug('update_device {} {}'.format(device_id, kwargs))

        device = Device.query.filter_by(id=device_id).first()
        if device:
            device.update(**kwargs)
        return device


async def config(device, config=None):
    session = get_http_session(20)

    params = None
    if isinstance(config, dict):
        params = {
            r == 'ht' and 'hold_time' or r: v
            for r, v in config.items() if r != 'success'
        }
    url = 'http://{}/config'
    response = await session.get(url, params=params)
    if response.status == 200:
        response_config = await response.json()
    else:
        response_config = None
    response.close()
    if response_config:
        return response_config
    logger.warning('from config url {} response status={}, response text = {}'.format(
            url, response.status, await response.read()))

    return False


async def get_temp(device):
    session = get_http_session(20)

    url = 'http://{}/temp'.format(device.ip_address)
    response = await session.get(url)
    if response.status == 200:
        response_json = await response.json()
    else:
        response_json = None
    response.close()
    if response_json:
        return response_json
    logger.warning('from temp url %s response status=%s, response text = %s',
                   url, response.status, await response.read())

    return False


async def publish(topic: str, payload):
    mqtt_client = await get_mqtt_async_client()
    try:
        logger.info('Publish to {}'.format(topic))
        if not isinstance(payload, str):
            payload = json.dumps(payload)
        await mqtt_client.publish(topic, payload.encode(), 0)
    except Exception as err:
        logger.error('Error while notify to {}, payload: {}'.format(topic, payload))
        logger.exception(err)


def is_valid_card_number(raw_card):
    try:
        card_no = raw_card[:-2]
        checksum_need = int(raw_card[-2:], 16)
        checksum_is = reduce(lambda a, b: a ^ b, [int(card_no[x * 2:x * 2 + 2], 16) for x in range(len(card_no) // 2)],
                             0)
        return checksum_is == checksum_need
    except:
        return False
