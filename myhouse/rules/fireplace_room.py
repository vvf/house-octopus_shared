# there are rules for the devices in the garage

import logging

from .reactor_worker import reactor
from .utils import publish, get_device_by_mac, turn

logger = logging.getLogger(__name__)

LIGHTS_DEV = 'b67793'
SWITCH_DEV = '816f4e'
knock_patterns = []

temp_correction = {
    't2826a76e40063': -4.75
}

POS_OF_LIGHTS = {
    '0': [0],
    '1': [1, 2, 3, 4, 5, 6],
    '4': [1, 2, 3]
}


async def switch_light(event=None, pos=None, *other):
    if event is None or pos is None:
        return
    if other:
        logger.warning(f"Unknown arguments of switch_lights {other}")
    todo = 'on' if event == '1' else 'off'
    lights = await get_device_by_mac(LIGHTS_DEV)
    await turn(lights, relay=POS_OF_LIGHTS[pos], new_value=todo)


@reactor.route('/house/device/{}/events/<any(up, down, temp):event>'.format(SWITCH_DEV))
async def fireplace_room_switch(payload, event):
    switch = await get_device_by_mac(SWITCH_DEV)

    if event == 'temp':
        kwargs = payload.get('kwargs', {})
        for thermometer_id in kwargs:
            if thermometer_id.startswith('t'):
                if thermometer_id in temp_correction:
                    kwargs[thermometer_id] = round(float(kwargs[thermometer_id]) + temp_correction[thermometer_id], 3)
                await publish(
                    '/house/temp/{}'.format(thermometer_id[1:]),
                    {"temperature": kwargs[thermometer_id]}
                )
            # TODO: save somewhere temperatures
        return
    if switch:
        logger.info(f"KidsRoom switch {event}:{''.join(payload['args'])}")
        await switch_light(*payload.get('args', []))

# @reactor.route('/house/device/{}/events/<event>'.format(SWITCH_DEV))
#async def fireplace_room_bits(payload, event):
#     logger.debug("Event from switch: {}, {}".format(event, payload))
