import logging

from myhouse.rules import reactor
from myhouse.rules.utils import http_query_device, get_device_by_mac

logger = logging.getLogger(__name__)
BACKYARD_DEV = '58cf0c'


@reactor.route('/house/device/{}/action/effect'.format(BACKYARD_DEV))
async def backyard_effect(payload):
    if not payload:
        return
    device = await get_device_by_mac(BACKYARD_DEV)
    if not device:
        return
    url_params = {
        'stepTime': payload.get('stepTime', 3),
        'fromPin': payload.get('fromPin', 0),
        'toPin': payload.get('toPin', 4),
        'level': payload.get('level', 100),
    }
    if 'whenNextPin' in payload:
        url_params['whenNextPin'] = payload['whenNextPin']
    response = await http_query_device(device, 'effect', params=url_params)
    return response.get('Ok')


BLOCKS = [
    (0, 4),
    (4, 0),
    (6, 8),
    (7, 7),
    (8, 9),
]


@reactor.route('/house/device/{}/action/turn_block'.format(BACKYARD_DEV))
async def backyard_turn_block(payload):
    if not payload:
        logger.warning("Do nothing: turn_block without payload.")
        return
    device = await get_device_by_mac(BACKYARD_DEV)
    if not device:
        logger.warning("Do nothing: Don't know that device (no IP address of device).")
        return
    block = payload.get('where', 0)
    p_from, p_to = BLOCKS[block]
    url_params = {
        'stepTime': 5,
        'fromPin': p_from,
        'toPin': p_to,
        'level': payload.get('state', 100) or 0,
    }
    url_params['whenNextPin'] = max([url_params['level'] // 2, 20])
    response = await http_query_device(device, 'effect', params=url_params)
    logger.debug(f'Got response: {response}')
    return response.get('Ok')
