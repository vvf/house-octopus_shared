from asyncio import coroutine

import asyncio
from datetime import datetime, timedelta

from myhouse.models import DeviceSchedule, Device
from myhouse.mqtt import get_mqtt_async_client
from myhouse.rules.utils import get_device_status, publish, get_device_by_id
from .utils import get_device_by_mac, turn
from .reactor_worker import reactor
import logging

logger = logging.getLogger(__name__)


# /house/device/<device_mac>/action/schedule/add
#  payload:
#   action - just action: "turn", "dimm", etc (without /house/device/<device_mac>/action/)
#   payload - payload for action: what exactly need to do.
#   ## time fields: None = any, positive - at this number, negative - per number.
#   minutes - example: 3: at 3 minutes, -3: every 3 minutes.
#   hours -
#   mday -
#   month -
#   wday -
#   is_once - boolean: if true - delete task after executing


# /house/device/<device_mac>/action/timer
# payload:
#  payload, action - the same as above
#   ## time fields set different from current time:
#   seconds -
#   minutes -
#   hours -
#   days -
#   weeks -


@reactor.route('/house/device/<device_mac>/action/schedule/<any(add, ask, delete):action>')
@coroutine
def device_schedule(payload, device_mac, action):
    if not payload and action != 'ask':
        return
    device = yield from get_device_by_mac(device_mac)
    if not device:
        logger.error("No device with MAC {} found".format(device_mac))
        return
    if action not in schedule_actions:
        logger.error("Invalid schedule action - {}".format(action))
    rv = yield from schedule_actions[action](payload, device)
    return rv


@reactor.route('/house/device/<device_mac>/action/timer')
@coroutine
def device_schedule_timer(payload, device_mac):
    global scheduled_tasks
    if not payload:
        return
    device = yield from get_device_by_mac(device_mac)
    if not device:
        logger.error("No device with MAC {} found".format(device_mac))
        return

    if not all(payload.get(field) for field in ('device_id', 'action')) or \
            not any(payload.get(field) for field in ('days', 'seconds', 'minutes', 'hours', 'weeks')):
        logger.warning("device_schedule_timer: invalid payload: {}".format(payload))
        return
    payload['device_id'] = device.id
    act_time = datetime.now()
    act_time += timedelta(
        days=payload.get("days", 0),
        seconds=payload.get("seconds", 0),
        minutes=payload.get("minutes", 0),
        hours=payload.get("hours", 0),
        weeks=payload.get("weeks", 0)
    )
    task = DeviceSchedule(
        device_id=device.id,
        is_once=True,
        minutes=act_time.minute,
        hours=act_time.hour,
        mday=act_time.day,
        month=act_time.month,
        action=payload['action'],
        payload=payload.get('payload', ''),
    )
    if not scheduled_tasks:
        scheduled_tasks = []
    scheduled_tasks.append(task)
    yield from device_schedule_ask({}, device)


@coroutine
def device_schedule_add(payload, device):
    global scheduled_tasks
    payload['device_id'] = device.id
    try:
        task = DeviceSchedule.create(
            **payload
        )
    except Exception as error:
        logger.error(error)

    if not scheduled_tasks:
        scheduled_tasks = []
    scheduled_tasks.append(task)
    yield from device_schedule_ask({}, device)


@coroutine
def device_schedule_delete(payload, device):
    global scheduled_tasks
    task_id = payload.get('task_id')
    if not task_id:
        return
    scheduled_tasks = filter(lambda task: task.id != task_id or task.device_id != device.id)
    yield from device_schedule_ask({}, device)


@coroutine
def device_schedule_ask(payload, device):
    yield from publish('/house/device/{}/schedule'.format(device.mac_address),
                       {'schedule': [task.as_dict() for task in scheduled_tasks if task.device_id == device.id]})


schedule_actions = {
    'add': device_schedule_add,
    'delete': device_schedule_delete,
    'ask': device_schedule_ask
}

scheduled_tasks = []
device_by_id_cache={}

@coroutine
def scheduler():
    global scheduled_tasks, device_by_id_cache
    logger.debug('Start scheduler')
    try:
        yield from asyncio.sleep(5)
        loop = asyncio.get_event_loop()
        scheduled_tasks = yield from loop.run_in_executor(None, DeviceSchedule.query.all)
        scheduled_tasks = scheduled_tasks or []
        if scheduled_tasks:
            devices_in_tasks = yield from loop.run_in_executor(None, Device.query.filter, Device.id.in_(
                {task.device_id for task in scheduled_tasks}
            ))
            device_by_id_cache = {
                dev.id: dev for dev in devices_in_tasks
            }
        # tick_tack = True
        logger.debug('Scheduler has {} tasks'.format(len(scheduled_tasks)))
        while True:
            tasks_to_remove = []
            # if tick_tack:
            #     logger.debug('scheduler Tick, check {} tasks'.format(len(scheduled_tasks)))
            # tick_tack = not tick_tack
            for task in scheduled_tasks:
                is_fired = yield from check_task(task)
                if is_fired and task.is_once:
                    tasks_to_remove.append(task)
            yield from asyncio.sleep(30)
            if tasks_to_remove:
                scheduled_tasks = list(filter(lambda item: item not in tasks_to_remove, scheduled_tasks))
            for task in tasks_to_remove:
                if task.id:
                    task.delete()
                scheduled_tasks.remove(task)
    except Exception as err:
        logger.exception(err)
        logger.error('SCHEDULER NOT WORK!!!')


@coroutine
def check_task(task):
    global device_by_id_cache
    current_time = datetime.now()
    currents = [
        current_time.second,
        current_time.minute,
        current_time.hour,
        current_time.day,
        current_time.month,
        current_time.weekday()
    ]
    tasks = [
        task.seconds,
        task.minutes,
        task.hours,
        task.mday,
        task.month,
        task.wday
    ]
    if all(compare_time_item(planned, current) for planned, current in zip(tasks, currents)):
        if task.device_id in device_by_id_cache:
            device = device_by_id_cache[task.device_id]
        else:
            device = yield from get_device_by_id(task.device_id)
            device_by_id_cache[device.id] = device
        if device:
            yield from publish('/house/device/{}/action/{}'.format(device.mac_address, task.action), task.payload)
        else:
            task.is_once = True
        return True
    return False


def compare_time_item(planned, current):
    if planned is None:
        return True
    if planned >= 0:
        return planned == current
    return current % (-planned) == 0


asyncio.ensure_future(scheduler())
