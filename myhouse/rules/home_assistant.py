import asyncio
import json
import logging

from myhouse.devices_ids import (BACKYARD_DEV, BATHROOM_LIGHT_DEV, BATHROOM_SHOWER_DEV,
                                 BEDROOM_LIGHT_DEVICE, BED_LIGHT_DEV,
                                 DINNING_LIGHT1_DEV, KIDROOM_LIGHTS_DEV,
                                 MUDROOM_DEV, OUTSIDE_LIGHTS_DEV)
from myhouse.mqtt import get_mqtt_async_client

logger = logging.getLogger(__name__)

HOME_ASSISTANT_TOPIC_TPL = '/home_assistant/{component}/{device_id}/config'

DEVICE_INFO = {
    DINNING_LIGHT1_DEV: {
        (2, 3): ('light', 'свет в столовой'),
    },
    BEDROOM_LIGHT_DEVICE: {
        (0, 1): ('light', 'свет в спальне'),
    },
    MUDROOM_DEV: {
        (0,): ('light', 'свет над калиткой'),
        (1,): ('light', 'свет в прихожей')
    },
    KIDROOM_LIGHTS_DEV: {
        (0, 1, 2, 3, 5, 6, 7): ('light', 'свет в детской'),
    },
    OUTSIDE_LIGHTS_DEV: {
        (0, 1, 2): ('light', 'свет перед домом'),
        (3, 6, 7): ('light', 'свет за домом'),
        (3, 4, 5): ('light', 'гирлянды на улице'),
    },
    BATHROOM_LIGHT_DEV: {
        (0, 1, 2, 3): ('light', 'свет в ванной')
    },
    BATHROOM_SHOWER_DEV: {
        (0,): ('light', 'свет в душевой')
    },
    BACKYARD_DEV: {
        (0,): ('dimmer', 'во дворе'),
        (2,): ('dimmer', 'на веранде'),
    },
    BED_LIGHT_DEV: {
        (0,): ('dimmer', 'свет над кроватью вове'),
        (3,): ('dimmer', 'свет над кроватью ире'),
        (2,): ('dimmer', 'подсветка пола в спальне'),
        (1, 4, 5): ('dimmer', 'подсветка ниш в спальне'),

    }

}


async def send_ha_all_subdevs(dev_id):
    sub_devs = DEVICE_INFO.get(dev_id, {})
    if not sub_devs:
        logger.info("No information about %s", dev_id)
        return
    for relays, (dev_type, dev_name) in sub_devs.items():
        mode = 'd' if dev_type == 'dimmer' else 'r'
        await send_ha_config_light(dev_id, relays, mode, dev_name)
        await asyncio.sleep(1)

__arp_table = None
def get_mac(dev_id):
    global __arp_table
    if not __arp_table:
        __arp_table = {}
        with open('/proc/net/arp') as f:
            head = f.readline()
            i1 = head.index('HW type')
            i2 = head.index('HW address')
            i3 = head.index('Mask', i2)
            print(i1, i2, i3)
            for ln in f:
                ip = ln[:i1].strip()
                mac = ln[i2:i3].strip()
                dev_id = ''.join(mac.split(':')[-3:])
                if mac == '00:00:00:00:00:00':
                    continue
                __arp_table[dev_id] = (mac, ip)
    return __arp_table.get(dev_id) or (None, None)


async def send_ha_config_light(dev_id, relay_nums, mode='r', name=None, icon=None):
    if not relay_nums:
        raise Exception("Need at least one relay number")
    dev_uniq_id = f'esp-vvf-{mode}-{dev_id}-{"-".join(map(str, relay_nums))}'
    config = {
        'platform': 'mqtt',
        'enabled_by_default': True,
        'unique_id': dev_uniq_id,
        'object_id': dev_uniq_id,
        # 'device': {
        #     "manufacturer": f"VVF-{dev_id}",
        #     "name": name,
        #     "identifiers": ['light', f'esp-vvf-{dev_id}']
        # },
        "device_class": "light",
        'name': name,
        'icon': icon or 'mdi:ceiling-light-multiple-outline',
        'optimistic': False,
    }
    # mac_address, ip_address = get_mac(dev_id)
    # if mac_address:
    #     config['device']['connections'] = [['mac', mac_address], ['ip', ip_address]]
    off_condition = f'value_json.state{relay_nums[0]} == 0 or value_json.state{relay_nums[0]} == "0" '
    if mode == 'd':
        logger.info("Config dimmer")
        config.update({
            'on_command_type': 'brightness',
            "brightness_command_topic": f"/house/device/{dev_id}/ha/dimm/"+
            ','.join(map(str, relay_nums)) + '/',
            "brightness_scale": 100,
            "brightness_state_topic": f'/house/device/{dev_id}/events/state',
            # "brightness_value_template": "{{value_json.state%s}}" % relay_nums[0],
            "brightness_value_template": "{{value_json.state%s}}" % relay_nums[0],

            'state_topic': f'/house/device/{dev_id}/event/state',
            'state_value_template': '{{"OFF" if value_json.state%s == 0 else "ON"}}' % relay_nums[0],

            'command_topic': f'/house/device/{dev_id}/action/dimm',
            'payload_on': json.dumps({"state": "on", "dimmers": relay_nums}),
            'payload_off': json.dumps({"state": "off", "dimmers": relay_nums}),
        })
    else:
        # off_condition = " and ".join(f"value_json.state{i} == 0" for i in relay_nums)
        logger.info("off_condition = %s", off_condition)
        config.update({
            'state_topic': f'/house/device/{dev_id}/events/state',
            'state_value_template': '{% if ' + off_condition + ' %}off{% else %}on{% endif %}',
            'command_topic': f'/house/device/{dev_id}/action/turn',
            'payload_on': json.dumps({"state": "on", "relay": relay_nums}),
            'payload_off': json.dumps({"state": "off", "relay": relay_nums}),
        })

    await send_ha_device_config(dev_uniq_id, 'light', config)


async def send_ha_device_config(dev_id, component, config):
    mqtt_client = await get_mqtt_async_client()
    config['unique_id'] = dev_id
    config['object_id'] = dev_id
    payload = json.dumps(config)
    try:
        rv = await mqtt_client.publish(
            HOME_ASSISTANT_TOPIC_TPL.format(
                component=component,
                device_id=dev_id
            ),
            (payload or '').encode(),
            0)
        return rv
    except Exception as err:
        logger.exception('Error while notify:{}'.format(err))


def main():
    async def async_main():
        for dev_id in DEVICE_INFO.keys():
            await send_ha_all_subdevs(dev_id)
            await asyncio.sleep(5)

    asyncio.run(async_main())


if __name__ == '__main__':
    main()
# import asyncio
# asyncio.run(send_ha_all_subdevs(BED_LIGHT_DEV))