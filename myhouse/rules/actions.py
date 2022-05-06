import asyncio
import logging

from myhouse.mqtt import get_mqtt_async_client
from myhouse.rules.utils import get_all_devices, get_device_status, update_device_info
from myhouse.devices_ids import BACKYARD_DEV
from .reactor_worker import reactor
from .utils import get_device_by_mac, turn

logger = logging.getLogger(__name__)


@reactor.route('/house/device/<device_mac>/action/turn')
async def mqtt_turn(payload, device_mac):
    if not payload:
        return
    device = await get_device_by_mac(device_mac)
    if not device:
        logger.error("No device with MAC {} found".format(device_mac))
        if device_mac.startswith('9b9890'):
            from myhouse.rules.broadlink import run_discover_thread
            run_discover_thread()
        return
    state = payload.get('state', 'tgl')
    relay = payload.get('relay', [])
    if not relay and relay != 0 or relay is False:
        logger.error("Nothing to turn (at least one relay need) {}".format(device_mac))
        return
    if device_mac == '9cb86a':
        logger.debug("Ask turn device with MAC %s begin. relay=%s state=%s",
                     device_mac, relay, state)
    await turn(device, relay, state)
    # logger.debug("Turn device with MAC {} done".format(device_mac))


@reactor.route('/house/device/<device_mac>/action/dimm')
async def mqtt_dimm(payload, device_mac):
    if not payload:
        return
    device = await get_device_by_mac(device_mac)
    if not device:
        logger.error("No device with MAC {} found".format(device_mac))
        return
    # if not device.is_online:
    #     logger.error("Device {} ({}) offline".format(device.name, device.ip_address))
    #     return
    state = payload.get('state', '128')
    dimmers = payload.get('dimmers', [])
    if not dimmers:
        logger.error("Nothing to turn (at least one dimmer need) {}".format(device_mac))
        return
    # logger.debug("dimm {} lights {} to {}".format(device.name, dimmers, state))
    # logger.debug("Ask turn device with MAC {} begin".format(device_mac))
    await turn(device, dimmers, state, mode='d')
    # logger.debug("Turn device with MAC {} done".format(device_mac))


@reactor.route('/house/device/<device_mac>/ha/dimm/<dimmers>/')
async def mqtt_ha_dimm(payload, device_mac, dimmers):
    if not payload:
        payload = '0'
    device = await get_device_by_mac(device_mac)
    if not device:
        logger.error("No device with MAC {} found".format(device_mac))
        return
    # if not device.is_online:
    #     logger.error("Device {} ({}) offline".format(device.name, device.ip_address))
    #     return
    if not dimmers:
        logger.error("Nothing to turn (at least one dimmer need) {}".format(device_mac))
        return
    state = int(payload)
    dimmers = list(map(int, dimmers.split(',')))
    # logger.debug("dimm {} lights {} to {}".format(device.name, dimmers, state))
    logger.info("HA turn device with MAC %s to state %s items %s", device_mac, state, dimmers)
    if device_mac == BACKYARD_DEV:
        from .backyard import backyard_turn_block
        await backyard_turn_block({"state": state, "where": dimmers[0]})
    await turn(device, dimmers, state, mode='d')
    # logger.debug("Turn device with MAC {} done".format(device_mac))


tasks = {
}


def make_task_key(device, dimmers):
    return device.mac_address + ':'.join(map(str, dimmers))


@reactor.route('/house/device/<device_mac>/action/<any(sunrise, sunset):direction>')
async def mqtt_sunrise(payload, device_mac, direction):
    global tasks
    if not payload:
        return
    device = await get_device_by_mac(device_mac)
    if not device:
        logger.error("No device with MAC {} found".format(device_mac))
        return

    if not device.is_online:
        logger.error("Device {} ({}) offline".format(device.name, device.ip_address))
        return

    dimmers = payload.get('dimmers', [])
    delay = payload.get('delay') or (payload.get('time') and payload.get('time') // 255) or 30
    if delay < 0.1:
        delay = 0.1
    step = int(payload.get('step', 1))
    if step < 1:
        step = 1
    if not dimmers:
        logger.error("Nothing to dimm (at least one dimmer need)\t dev:{}".format(device_mac))
        return
    key = make_task_key(device, dimmers)
    if tasks.get(key):
        tasks[key].cancel()
    tasks[key] = asyncio.create_task(_sun(
        device, dimmers,
        delay=delay,
        step=step,
        rise=(direction == 'sunrise')))


async def _sun(device, dimmers, rise=True, delay=30, step=1):
    global tasks
    try:
        if rise:
            _range = range(1, 255, step)
        else:
            _range = range(255, 0, -step)
        for state in _range:
            try:
                await turn(device, dimmers, str(state), mode='d', notify_new_state=False)
            except Exception as error:
                logger.error('Error in sun(rise|set):')
                logger.exception(error)
                continue
            await asyncio.sleep(delay)

        if rise:
            await turn(device, dimmers, 'on', mode='d', notify_new_state=False)
        else:
            await turn(device, dimmers, 'off', mode='d', notify_new_state=False)
    except asyncio.CancelledError:
        pass
    finally:
        key = make_task_key(device, dimmers)
        del tasks[key]


@reactor.route('/house/device/<device_mac>/action/ask_status')
async def mqtt_ask_status(payload, device_mac):
    device = await get_device_by_mac(device_mac)
    if not device:
        logger.error("No device with MAC {} found".format(device_mac))
        return
    await get_device_status(device, notify_new_state=True)


@reactor.route('/house/device/<device_mac>/action/set_info')
async def mqtt_set_info(payload, device_mac):
    device = await get_device_by_mac(device_mac)
    if not device:
        logger.error("No device with MAC {} found".format(device_mac))
        return
    await update_device_info(device, payload)


@reactor.route('/house/notify/reactor/ping')
async def mqtt_ping(payload):
    mqtt_client = await get_mqtt_async_client()
    try:
        await mqtt_client.publish('/house/notify/reactor/pong', payload)
    except Exception as err:
        logger.error('Error while notify:{}'.format(err))


@reactor.route('/house/devices/get_list')
async def mqtt_get_devs(payload):
    devices = await get_all_devices()
    for device in devices:
        await get_device_status(device, notify_new_state=True, include_device_info=True)
