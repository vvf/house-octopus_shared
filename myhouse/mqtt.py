from amqtt.client import MQTTClient
from amqtt.client import base_logger as async_mqtt_logger
import asyncio
import logging

DEVICES_NOTIFY_TOPIC_BASE_TPL = '/house/device/{}'
DEVICES_UDP_NOTIFY_TOPIC_TPL = '/house/device/{}/events'
DEVICES_PING_NOTIFY_TOPIC_TPL = '/house/device/{}/online_status'
DEVICES_TCP_NOTIFY_TOPIC_TPL = '/house/device/{}/events'

HOME_ASSISTANT_TOPIC_TPL = '/home_assistant/{component}/{device_id}/config'

MQTT_CONNECTION_PARAMS = ('127.0.0.1', 1883)
# MQTT_CONNECTION_PARAMS = ('192.168.77.177', 1883)


logger = logging.getLogger(__name__)

__sync_client = None


def get_mqtt_sync_client():
    global __sync_client
    if not __sync_client:
        from paho.mqtt import client as mqtt
        __sync_client = mqtt.Client()  # TODO: add here auth info to connect
        __sync_client.connect(*MQTT_CONNECTION_PARAMS)
    return __sync_client


class AsyncMQTTClient(MQTTClient):
    @property
    def is_connected(self):
        return self._connected_state.is_set()


__async_client = None
__pinger_task = None



async def get_mqtt_async_client():
    global __async_client, __pinger_task
    if not __async_client:
        async_mqtt_logger.setLevel(logging.INFO)
        __async_client = AsyncMQTTClient(config={
            'auto_reconnect': True, 
            'ping_delay': 2, 'reconnect_max_interval': 5, 'reconnect_retries': 15, 'keep_alive': 3600})
        __async_client.logger.setLevel(logging.INFO)
#        __async_client.handle_connection_close
        await __async_client.connect('mqtt://{}:{}/'.format(*MQTT_CONNECTION_PARAMS))
        logger.error("MQTT Connected:{}".format(__async_client.is_connected))
    else:
        if not __async_client.is_connected:
            await __async_client.ping()

        while not __async_client.is_connected:
            await asyncio.sleep(1)
        async_mqtt_logger.debug('... reconnected')
    return __async_client
