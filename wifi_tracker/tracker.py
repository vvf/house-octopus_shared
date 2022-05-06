import asyncio
import json
import logging
from datetime import datetime
from os import environ

import amqtt.client
from amqtt.client import MQTTClient

from wifi_tracker.devices import IROS_IPHONE_MAC, BLUE_FISH_CAR_MAC
from wifi_tracker.keenetic import KeeneticClient

logger = logging.getLogger(__name__)
__async_client = None
__pinger_task = None

DEVICES_TO_CHECK = {
    IROS_IPHONE_MAC,
    BLUE_FISH_CAR_MAC
}

FIELDS_TO_PUBLIC = [
    "ip", "hostname", "name",
    "active", "rxbytes", "txbytes", "last-seen",
    "link", "txrate", "uptime", "rssi"
]
TRACK_CHANGES_OF = [
    "active", "link"
]
ONE_MB = 1024 * 1024

UPTIME_OF_BECOME_ONLINE = 5  # сколько секунд аптайма считат что устройство только что появилось
LAST_SEEN_TIME_OF_OFFLINE = 10  # сколько секунд не было устройства в онлайне чтобы считать что оно ушо в оффлайн
CHECKING_INTERVAL = 3  # every 3 sec ask router of devices status
CHECKS_PER_SEND_STATUS = 20 * 5  # every 20 checks - send status to mqtt (once in minute)


async def get_mqtt_async_client():
    global __async_client, __pinger_task
    if not __async_client:
        __async_client = MQTTClient(config={
            'auto_reconnect': True,
            'ping_delay': 2,
            'reconnect_max_interval': 5,
            'reconnect_retries': 15, 'keep_alive': 3600})
        __async_client.logger.setLevel(logging.DEBUG)
        rv = await __async_client.connect(environ.get("MQTT_URL", "mqtt://127.0.0.1"))
    else:
        if not __async_client._connected_state.is_set():
            try:
                rv = await __async_client.ping()
            except amqtt.client.ClientException:
                pass

        while not __async_client._connected_state.is_set():
            await asyncio.sleep(1)
    return __async_client


__last_values = {}
__last_status = {}


async def publish_device_status(host: dict):
    payload = {
        field: host.get(field)
        for field in FIELDS_TO_PUBLIC
    }
    new_values = '/'.join(str(host.get(field, '')) for field in TRACK_CHANGES_OF)
    mac = ''.join(host['mac'].split(':'))

    payload_bytes = None
    mqtt = None
    payload["title"] = host.get("name") or host.get("hostname")
    if __last_status.get(mac, 0) > CHECKS_PER_SEND_STATUS:

        topic = f'/house/device/{mac}/wifi-status'
        payload_bytes = json.dumps(payload).encode()
        mqtt = await get_mqtt_async_client()
        await mqtt.publish(topic, payload_bytes, 0)
        logger.info("Send status of device %s active/link: %s", mac, new_values)
        __last_status[mac] = 0
    else:
        __last_status[mac] = __last_status.get(mac, 0) + 1

    if mac not in __last_values:
        __last_values[mac] = new_values
    elif __last_values[mac] != new_values:
        show_values = '/'.join(str(host.get(field, '')) for field in FIELDS_TO_PUBLIC)
        logger.info("Status changed: %s", show_values)
        __last_values[mac] = new_values

        if host.get("active") is None:
            return

        if payload_bytes is None:
            payload_bytes = json.dumps(payload).encode()
            mqtt = await get_mqtt_async_client()

        if host["active"]:
            logger.info("Device %s become ONLINE @ %s", payload["title"],
                        datetime.now().isoformat())
            await mqtt.publish(f'/house/device/{mac}/online', payload_bytes, 0)
        else:
            logger.info("Device %s become OFFLINE @ %s", payload["title"],
                        datetime.now().isoformat())
            await mqtt.publish(f'/house/device/{mac}/offline', payload_bytes, 0)


async def checking_loop(keenetic: KeeneticClient):
    while True:
        answer = await keenetic.show.ip.hotspot()
        hosts = answer['host']
        for host in hosts:
            if host['mac'] in DEVICES_TO_CHECK:
                await publish_device_status(host)
        await asyncio.sleep(CHECKING_INTERVAL)


async def main():
    from aiomisc.log import basic_config
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("amqtt.client.plugins").setLevel(logging.INFO)
    logging.getLogger("amqtt.client").setLevel(logging.INFO)
    basic_config()
    keenetic = KeeneticClient('192.168.77.1', 'vvf', 'vvf')
    async with keenetic.session:
        logger.info("Auth to router")
        await keenetic.auth()
        logger.info("Start checking")
        await checking_loop(keenetic)


if __name__ == '__main__':
    asyncio.run(main())
