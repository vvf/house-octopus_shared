import asyncio
import json
import logging
from os import environ

from amqtt.client import MQTTClient

from devices_ids import (BACKYARD_DEV, BATHROOM_LIGHT_DEV, BATHROOM_SHOWER_DEV, BEDROOM_LIGHT_DEVICE, BED_LIGHT_DEV,
                         BROADLINK_SP1, DINNING_LIGHT1_DEV,
                         ESP_SOCKET0, GARAGE_DEV,
                         KITCHEN_LIGHT_DEV, MUDROOM_DEV, KIDROOM_LIGHTS_DEV, OUTSIDE_LIGHTS_DEV, WALL_LIGHT_DEV,
                         WATERING_DEV2, WATERING_DEV4)

logger = logging.getLogger(__name__)
__async_client = None
__pinger_task = None

BED_LIGHT_LEFT_SIDE = 0
BED_LIGHT_RIGHT_SIDE = 3
BED_LIGHT_FLOOR = 2
BED_LIGHT_WND1 = 1
BED_LIGHT_WND2 = 4  # and WND0
BED_LIGHT_WND3 = 5

MQTT_CONNECTION_PARAMS = ('127.0.0.1', 1883)
# MQTT_CONNECTION_PARAMS = ('192.168.77.177', 1883)


class AsyncMQTTClient(MQTTClient):
    @property
    def is_connected(self):
        return self._connected_state.is_set()


async def get_mqtt_async_client():
    global __async_client, __pinger_task
    if not __async_client:
        __async_client = AsyncMQTTClient(config={
            'auto_reconnect': True,
            'ping_delay': 2, 'reconnect_max_interval': 5, 'reconnect_retries': 15, 'keep_alive': 3600})
        __async_client.logger.setLevel(logging.DEBUG)
        #        __async_client.handle_connection_close
        rv = await __async_client.connect(
            environ.get("MQTT_URL") or 'mqtt://{}:{}/'.format(*MQTT_CONNECTION_PARAMS)
        )
    else:
        if not __async_client.is_connected:
            rv = await __async_client.ping()

        while not __async_client.is_connected:
            await asyncio.sleep(1)
    return __async_client


async def publish(topic, payload):
    mqtt_client = await get_mqtt_async_client()
    try:
        if not isinstance(payload, str):
            payload = json.dumps(payload)
        logger.info("send to topic %s, payload %s", topic, payload)
        await mqtt_client.publish(topic, payload.encode(), 0)
    except Exception as err:
        pass
        # logger.error('Error while notify to {}, payload: {}'.format(topic, payload))
        # logger.exception(err)


DEVS_BY_WHERE = {
    'frontside': {OUTSIDE_LIGHTS_DEV: [0, 1, 2],
                  # GARAGE_DEV: [3, 4],
                  MUDROOM_DEV: [0, 3]},
    'outside': {
        OUTSIDE_LIGHTS_DEV: [0, 1, 2, 3, 6, 7],
        MUDROOM_DEV: [0]
    },
    'backside': {OUTSIDE_LIGHTS_DEV: [3, 6, 7]},
    '🎄🏠-hny': {OUTSIDE_LIGHTS_DEV: [3, 4, 5]},
    'garage': {GARAGE_DEV: [0, 1, 2]},
    'bedroom': {BEDROOM_LIGHT_DEVICE: [0, 1]},
    'bathroom': {BATHROOM_LIGHT_DEV: [0, 1, 2, 3]},
    'shower': {BATHROOM_SHOWER_DEV: [0]},
    'детская': {KIDROOM_LIGHTS_DEV: [0, 1, 2, 3, 5, 6, 7]},
    'dinning': {DINNING_LIGHT1_DEV: [2, 3]},
    'kitchen': {KITCHEN_LIGHT_DEV: [0]},
    'прихожая': {MUDROOM_DEV: [1]},
    'калитка': {MUDROOM_DEV: [0]},
    'розетка0': {ESP_SOCKET0: [0]},
    'розетка1': {BROADLINK_SP1: [0]},
    'all': {
        'd18195': [0, 1, 2, 3, 4, 5, 6, 7],
        OUTSIDE_LIGHTS_DEV: [0, 1, 2, 3, 4, 5, 6, 7],
        GARAGE_DEV: [0, 1, 2, 3],
        'a136e3': [0, 1, 2, 3],
        '13e668': [0, 1, 2, 3],
        DINNING_LIGHT1_DEV: [2, 3],
        '9c06e9': [0],
        ESP_SOCKET0: [0],
    }
}

WATER_DEVS_BY_WHERE = {
    'front0': {WATERING_DEV2: 0},
    'front1': {WATERING_DEV2: 1},

    'back4': {WATERING_DEV4: 3},
    'back3': {WATERING_DEV4: 2},
    'back2': {WATERING_DEV4: 1},
    'back1': {WATERING_DEV4: 0}

}


class Commands:
    def __init__(self, bot):
        self.bot = bot

    async def light(self, chat, state, where, silent=False, *args):
        if where == 'backyard':
            logger.debug(f'Turn light {state} in {where}')
            try:
                await self.backyard(chat, 0, 100 if state == 'on' else 0, silent)
            except Exception as err:
                logger.exception(err)
            return
        devices = DEVS_BY_WHERE.get(where)
        if not devices or state not in {'off', 'on'}:
            return False
        if where == 'all' and state == 'on':
            return False
        await self._send_action(devices, state)
        if not silent:
            chat.reply('Light {} at {}'.format(state, where))

    async def _send_action(self, devices, state='off', action='action/turn', payload=None):
        common_payload = payload
        logger.debug("Send %s to %s state=%s", action, ','.join(devices.keys()), state)
        for device_id, relays in devices.items():
            topic = '/house/device/{}/{}'.format(device_id, action)
            if common_payload is None:
                payload = {
                    'state': state,
                    'relay': relays
                }
            await publish(topic, payload)

    async def watering(self, chat, where, time='10', silent=False, *args):
        if where in {'start_program', 'stop_program'}:
            await publish(
                '/house/device/{}/events/{}'.format(WATERING_DEV4, where),
                payload={'kwargs': {'from_telegram': True}})
            return
        devices = WATER_DEVS_BY_WHERE.get(where)
        if not devices:
            return False
        for device_id, valve_no in devices.items():
            action = 'events/watering'
            topic = '/house/device/{}/{}'.format(device_id, action)
            await publish(topic,
                          payload={'kwargs': {
                              'from_telegram': True,
                              'state': time,
                              'valve_no': valve_no
                          }})
        if not silent:
            chat.reply('Watering at {}'.format(where))

    async def bed_light(self, chat, where, power, silent=False):
        if not isinstance(where, (list, tuple)):
            where = [where]
        logger.info("Dimm %s to %s", where, power)
        await publish(
            '/house/device/{}/action/dimm'.format(BED_LIGHT_DEV),
            payload={"state": power, "dimmers": where})

        if not silent:
            chat.reply('Подсветка кровати {} (#{})'.format(
                power and f'включена на {power}%' or 'выключена',
                where
            ))

    async def wall_light(self, chat, where, power, silent=False):
        await publish(
            '/house/device/{}/action/dimm'.format(WALL_LIGHT_DEV),
            payload={"state": power, "dimmers": [where]})

        if not silent:
            chat.reply('Подсветка {} (#{})'.format(
                power and f'включена на {power}%' or 'выключена',
                where
            ))

    async def backyard(self, chat, where, power, silent=False):
        await publish(
            '/house/device/{}/action/turn_block'.format(BACKYARD_DEV),
            payload={"state": int(power), "where": int(where)}
        )

        if not silent:
            chat.reply('Подсветка {} (#{})'.format(
                power and f'включена на {power}%' or 'выключена',
                where
            ))

    async def dinning(self, chat, where, power, silent=False):
        await publish(
            '/house/device/{}/action/dimm'.format(WALL_LIGHT_DEV),
            payload={"state": power, "dimmers": [where]})

        if not silent:
            chat.reply('Подсветка {} (#{})'.format(
                power and f'включена на {power}%' or 'выключена',
                where
            ))
