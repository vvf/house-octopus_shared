# there are rules for the devices in the garage
import asyncio
import logging
from typing import List

from wifi_tracker.devices import BLUE_FISH_CAR_MAC
from .reactor_worker import reactor
from .utils import get_device_status, publish, get_device_by_mac, turn
from ..devices_ids import MUDROOM_DEV

logger = logging.getLogger(__name__)

GARAGE_DEV1 = 'a1480d'
GARAGE_DEV2 = '9cb86a'
BLUE_FISH_CAR_DEV = ''.join(BLUE_FISH_CAR_MAC.lower().split(':'))
DEV1_BUTTON = 3
DEV1_MOTION_SENSOR = 1
DEV1_LIGHT_IN_FRONT1 = [0, 2]

garage_turn_off = {}


def turn_off_device_after_while(turn_args: List[tuple]):
    for args in turn_args:
        asyncio.ensure_future(turn(*args, new_value="off"))


@reactor.route(f'/house/device/{BLUE_FISH_CAR_DEV}/<event>')
async def blue_fish_car_status(payload, event):
    if event in {'online', 'offline'}:
        logger.info("Car is %s", event)
        device4 = await get_device_by_mac(GARAGE_DEV1)
        device8 = await get_device_by_mac(GARAGE_DEV2)
        device_gate = await get_device_by_mac(MUDROOM_DEV)
        if event == 'online':
            if garage_turn_off.get('task') is not None:
                garage_turn_off['task'].cancel()
            if device8 is not None:
                await turn(device8, [0, 1, 2], "on")
            if device4 is not None:
                await turn(device4, [0, 1, 2, 3], "on")
            if device_gate is not None:
                await turn(device_gate, [0], "on")
        else:
            garage_turn_off['task'] = asyncio.get_event_loop().call_later(
                300,  # turn off after 5 min
                turn_off_device_after_while, [
                    (device8, [0, 1, 2]),
                    (device4, [0, 1, 2, 3]),
                    device_gate, [0]
                ]
            )
        return
    if payload:
        logger.info("Car status: %s", payload)


@reactor.route('/house/device/{}/events/<any(up, down, hold):event>'.format(GARAGE_DEV1))
async def garage(payload, event):
    device4 = await get_device_by_mac(GARAGE_DEV1)
    device8 = await get_device_by_mac(GARAGE_DEV2)
    if not event in {'up', 'down', 'hold'}:
        return
    event_source_number = int(payload['args'][1])
    if event in ['up', 'down'] and event_source_number == DEV1_MOTION_SENSOR:
        await turn(device4, DEV1_LIGHT_IN_FRONT1, event == 'up' and 'off' or 'on')

    if event_source_number == DEV1_BUTTON and event in {'up', 'hold'}:
        if event == 'hold':
            turn_to = 'off'
        else:
            device_status = await get_device_status(device4)
            turn_to = device_status['state{}'.format(DEV1_BUTTON)] == 0 and 'off' or 'on'
        logger.debug('Turn light at front to {}'.format(turn_to))
        await turn(device8, [0, 1, 2], turn_to)

    if device4:
        await publish('/house/device/id-{}/events/{}'.format(device4.id, event), payload)
