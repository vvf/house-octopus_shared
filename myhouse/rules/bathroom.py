# there are rules for the devices in the garage
import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from myhouse.rules.utils import get_device_status
from .reactor_worker import reactor
from .utils import get_device_by_mac, publish, turn

logger = logging.getLogger(__name__)

SHOWER_FLOW_DEVICE = '9c06e9'
LIGHT_DEVICE = 'a136e3'
LIGHT_SWITCH = 0
MOTION_SENSOR = 3
MOTION_SENSOR_DELAY = 60 * 5
MOTION_SENSOR_DELAY_IN_THE_MORNING = 60 * 15
MOTION_SENSOR_DELAY_AT_NIGHT = 60 * 2
MOTION_SENSOR_DELAY_AFTER_SHOWER_OFF = 60 * 15
SWITCH_ON_DELAY = 60 * 30

SHOWER_OFF_TIMEOUT = 15

bathroom_motion_off_task: Optional[asyncio.Task] = None


@dataclass
class ShowerSession:
    start_time: datetime
    water_counter: Optional[int] = 0
    finish_time: Optional[datetime] = None
    task: Optional[asyncio.Task] = None


shower_session: Optional[ShowerSession] = None


@reactor.route('/house/device/{}/events'.format(SHOWER_FLOW_DEVICE))
async def shower(payload):
    global shower_session, bathroom_motion_off_task
    '''
    Count wasted water as periods
    Turn light on when shower off
    '''
    if not payload or 'data' not in payload:
        return
    flow = int(payload.get('data', {}).get('kwargs', {}).get('flow', '0'))
    if not flow:
        return
    if not shower_session:
        shower_session = ShowerSession(datetime.now())
        if bathroom_motion_off_task is not None:
            try:
                logger.debug("Cancel turn off the light")
                bathroom_motion_off_task.cancel()
            except Exception as err:
                logger.exception(err)
            bathroom_motion_off_task = None

    shower_session.finish_time = datetime.now()
    shower_session.water_counter += flow
    if shower_session.task and not shower_session.task.cancelled():
        shower_session.task.cancel()
    else:
        asyncio.create_task(publish('/house/device/shower/start', '{}'))

    shower_session.task = asyncio.get_event_loop().call_later(
        SHOWER_OFF_TIMEOUT,
        lambda: asyncio.create_task(save_shower_session_after_off())
    )


@reactor.route('/house/device/{}/events/down'.format(LIGHT_DEVICE))
async def bathroom_lights(payload):
    global bathroom_motion_off_task
    '''
    If switch is on then ignore from motion sensor events (lock)
    If motion sensor change (down - is motion detected), then wait some time and turn off the light
    '''
    if not payload:
        return
    switch_no = int(payload['args'][1])
    device = await get_device_by_mac(LIGHT_DEVICE)
    lights_switch_state = await get_device_status(device)
    if switch_no == MOTION_SENSOR:
        if bathroom_motion_off_task:
            logger.debug("Motion detected, cancel turn off...")
            logger.debug("Cancel turn off the light")
            bathroom_motion_off_task.cancel()
            bathroom_motion_off_task = None
        delay = MOTION_SENSOR_DELAY
        now_hour = get_current_hour_as_float()
        if lights_switch_state[f'button{LIGHT_SWITCH}'] > 0:
            delay = SWITCH_ON_DELAY
        elif 6 < now_hour < 9 or now_hour > 21:
            delay = MOTION_SENSOR_DELAY_IN_THE_MORNING
        is_night = now_hour > 21.5 or now_hour < 7.2
        is_deep_night = 1 < now_hour < 5.7
        strip_device = await get_device_by_mac(SHOWER_FLOW_DEVICE)
        if is_deep_night:
            # ничего не включать если глубокая ночь
            logger.debug("Deep night - ignore all.")
            delay = 1
        elif is_night:
            delay = MOTION_SENSOR_DELAY_AT_NIGHT
            if lights_switch_state[f'button{LIGHT_SWITCH}'] > 0:
                # включить подсветку только если выключатель в положении "вкл"
                logger.debug("Night, but switch is on")
                await turn(device, [0, 1, 2, 3], 'on')
            else:
                logger.debug("Night - turn light in shower")
                await turn(strip_device, [0], 'on')
        elif lights_switch_state[f'button{LIGHT_SWITCH}'] > 0:
            # включить все если выключатель в положении "вкл"
            logger.info("Switch is on = turn on all.")
            await turn(device, [0, 1, 2, 3], 'on')
        else:
            # включить половину если выключатель в положении "выкл"
            logger.info("Switch is off = turn on half.")
            await turn(device, [3, 1], 'on')
        bathroom_motion_off_task = asyncio.create_task(
            turn_off_after_motion(
                [strip_device, device], delay
            ), name="TimerBathOff"
        )
        logger.info("Schedule off in %s sec", delay)
    elif switch_no == LIGHT_SWITCH:
        # включения здесь нет, потому что напрямую включается выключателем в устройстве
        if bathroom_motion_off_task:
            logger.debug("Switch turned on: extend turn off time")
            logger.debug("Cancel turn off the light")
            bathroom_motion_off_task.cancel()
            bathroom_motion_off_task = None
        if lights_switch_state[f'button{LIGHT_SWITCH}'] > 0:
            delay = SWITCH_ON_DELAY
            bathroom_motion_off_task = asyncio.create_task(turn_off_after_motion(device, delay))

    if device:
        await publish('/house/device/id-{}/events/down'.format(device.id), payload)


async def save_shower_session_after_off():
    global shower_session, bathroom_motion_off_task
    # TODO: save shower session (notify shower off)
    if not shower_session:
        logger.error('No shower session to save')
        return
    if shower_session.finish_time is None:
        shower_session.finish_time = datetime.now()
    usage_time: timedelta = shower_session.finish_time - shower_session.start_time
    from myhouse.rules.informer import ADMINS_ID, send_text
    for admin_chat in ADMINS_ID:
        await send_text(admin_chat, "Душ использовался {}:{}!".format(
            usage_time.total_seconds() // 60, usage_time.total_seconds() % 60
        ))

    logger.debug(
        'SHOWER SESSION:\tfrom {start_time:%T} to {finish_time:%T} counter={water_counter}'.format(**shower_session))

    device = await get_device_by_mac(LIGHT_DEVICE)
    await turn(device, [0, 1, 2], 'on')
    if bathroom_motion_off_task is not None:
        logger.debug("Cancel turn off the light")
        bathroom_motion_off_task.cancel()
        bathroom_motion_off_task = None

    asyncio.create_task(
        publish('/house/device/shower/finish',
                json.dumps({
                    k: getattr(shower_session, k).isoformat()
                    for k in ['finish_time', 'start_time']
                })
                )
    )

    # bathroom_motion_off_task = asyncio.create_task(
    #     turn_off_after_motion(device, delay=MOTION_SENSOR_DELAY_AFTER_SHOWER_OFF)
    # )
    shower_session = None


def get_current_hour_as_float() -> float:
    now_hour = datetime.now()
    return now_hour.hour + now_hour.minute / 60


async def turn_off_after_motion(device, delay=MOTION_SENSOR_DELAY):
    global bathroom_motion_off_task, shower_session
    motion_device = await get_device_by_mac(LIGHT_DEVICE)
    try:
        await asyncio.sleep(delay)
        if shower_session:
            logger.info("Don't turn off the lights: Wait while shower is working")
            while shower_session:
                await asyncio.sleep(5)
        logger.debug("start waiting for %s seconds before turn lights off", delay)

        while await is_motion_active(motion_device):
            await asyncio.sleep(delay)

        if shower_session:
            bathroom_motion_off_task = asyncio.create_task(
                turn_off_after_motion(device, delay=delay)
            )
            return
        if isinstance(device, (list, tuple)):
            logger.debug("No motion {} seconds. Turn lights (all devices) off".format(delay))
            await asyncio.gather(*[
                turn(dev, [0, 1, 2, 3], 'off')
                for dev in device
            ])
        else:
            logger.debug("No motion {} seconds. Turn off the light".format(delay))
            await turn(device, [0, 1, 2, 3], 'off')
    except asyncio.CancelledError:
        logger.debug("X-( killed the task of turning off the lights")
        bathroom_motion_off_task = None


async def is_motion_active(device):
    lights_switch_state = await get_device_status(device)
    return lights_switch_state[f'button{MOTION_SENSOR}'] > 0
