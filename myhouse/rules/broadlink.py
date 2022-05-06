import json
from threading import Thread, Lock

from broadlink import discover, device, sp2
from broadlink.exceptions import AuthorizationError

from myhouse.models import Device
import logging

devices_by_mac = {}
devices_models_by_mac = {}
logger = logging.getLogger(__name__)

discover_lock = Lock()


def start_discover(current_app):
    logger.debug("Start discover broadlink devices")
    discover_lock.acquire(True, 11)
    devices = discover(timeout=10, local_ip_address='0.0.0.0')
    logger.debug(f"Done discover broadlink devices, found = {len(devices)}")
    devices_by_mac.update({
        dev.mac.hex().lower(): dev
        for dev in devices
        if dev.auth()
    })
    with current_app.app_context():
        for dev_src in devices:
            dev: Device = Device.query.filter(Device.mac_address == dev_src.mac.hex().lower()).first()
            if dev is None:
                dev = Device(
                    mac_address=dev_src.mac.hex().lower(),
                    name=f'broadlink/{dev_src.type}/{dev_src.mac.hex().lower()}'
                )
                logger.info(f"Add broadlink device - {dev_src.type}: {dev_src.mac.hex()}  ip:{dev_src.host}")
            else:
                logger.info(f"Found broadlink device - {dev_src.type}: {dev_src.mac.hex()}  ip:{dev_src.host}")
            dev.ip_address = dev_src.host[0]
            dev.device_type = 'broadlink/' + dev_src.type
            dev.is_online = True
            dev.save()
    discover_lock.release()


def run_discover_thread():
    from flask import current_app
    logger.debug("run_discover_thread")
    Thread(target=start_discover, args=(current_app._get_current_object(),),
           name=f"start discover broadlink devices").start()


def device_model_to_bl_dev(fn):
    def decorated(device_model: Device, *args, **kwargs):
        if device_model.mac_address not in devices_by_mac:
            logger.warning(f"Device with mac {device_model.mac_address} not found - start discover again")
            run_discover_thread()
            return
        dev = devices_by_mac[device_model.mac_address]
        return fn(dev, *args, **kwargs)

    return decorated


@device_model_to_bl_dev
def turn(dev: sp2, state: str):
    if state not in {True, False}:
        if state.isdigit():
            state = bool(int(state))
        else:
            state = str(state).lower() == 'on'
    logger.debug(f"Broadlink turn {dev.host} to {state}")
    try:
        dev.set_power(state)
    except AuthorizationError:
        dev.auth()
        dev.set_power(state)
        
    return dev.check_power()


@device_model_to_bl_dev
def get_status(dev: sp2):
    logger.debug(f"Broadlink get_status of {dev.host}")
    return {
        'r0': 'on' if dev.check_power() else 'off'
    }


run_discover_thread()
