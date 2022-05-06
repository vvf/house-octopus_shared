import logging

from myhouse.devices_ids import MUDROOM_DEV
from myhouse.rules import reactor
from myhouse.rules.utils import get_device_by_mac, http_query_device, turn

logger = logging.getLogger(__name__)

DINNING_LIGHTS1_DEV = '8264cb'
KCHNLGHT_DEV = '84b557'
from enum import IntEnum


class ConfigActions(IntEnum):
    NO_OP = 0
    RELAY_TOGGLE = 1
    RELAY_ON = 2
    RELAY_OFF = 3
    RELAY_ALL_TOGGLE = 4
    RELAY_ALL_ON = 5
    RELAY_ALL_OFF = 6


@reactor.route('/house/notify/reactor/started')
@reactor.route('/house/notify/power_up')
async def reconfigure_switch(payload):
    logger.info("On start or power up reconfigure dinning switch")
    device = await get_device_by_mac(DINNING_LIGHTS1_DEV)
    if not device:
        return
    result = await http_query_device(device, 'config', {
        # there used only channel 2 which have to turn on|off all lights
        "on2down": ConfigActions.RELAY_ALL_ON.value,
        "on2up": ConfigActions.RELAY_ALL_OFF.value,
        # other - NOP
        "on1down": ConfigActions.NO_OP.value,
        "on1up": ConfigActions.NO_OP.value,
        "on0down": ConfigActions.NO_OP.value,
        "on0up": ConfigActions.NO_OP.value,
        "on3down": ConfigActions.NO_OP.value,
        "on3up": ConfigActions.NO_OP.value,
    })
    logger.info("Reconfigure DINNING LIGHTS SWITCH to %s", result)
    #     http://192.168.77.195/config?on2down=5&on2up=6&on1down=0&on1up=0&on0down=0&on0up=0&on3down=0&on3up=0


@reactor.route(f'/house/device/{DINNING_LIGHTS1_DEV}/events/<any(up,down,temp):event>')
async def dinning_room_up_light(payload, event):
    if not payload:
        logger.error("No payload")
        return
    device = await get_device_by_mac(DINNING_LIGHTS1_DEV)
    if not device:
        logger.error("No device %s", DINNING_LIGHTS1_DEV)
        return
    logger.warning("payload=%s", payload)
    switch_no = int(payload['args'][1])
    logger.info("switch_no=%s", switch_no)
    if switch_no == 3:
        mud_room_dev = await get_device_by_mac(MUDROOM_DEV)
        res = await turn(mud_room_dev, 1, (event == "up") and "on" or "off")
        logger.info("Turn MudRoom light result: %s", res)


logger.debug("{} loaded".format(__name__))
