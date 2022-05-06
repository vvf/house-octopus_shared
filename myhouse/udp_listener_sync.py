#!/usr/bin/env python

# there are will be code of listening udp socket and change data, and broadcast message
import json
import socket
from threading import Thread
import logging
import datetime

from myhouse.mqtt import DEVICES_UDP_NOTIFY_TOPIC_TPL, get_mqtt_sync_client

from myhouse.extensions import db
from myhouse.models import Device

logger = logging.getLogger(__name__)

udp_sock = socket.socket(type=socket.SOCK_DGRAM)

mqtt_client = get_mqtt_sync_client()

def listener():
    udp_sock.bind(('0.0.0.0', 0xB0BA))
    logger.warn('{:%D %T}\tStart listen udp packets from ESPs'.format(datetime.datetime.now()))

    while True:
        data, addr = udp_sock.recvfrom(1024)
        ip_addr, src_port = addr
        signature, dev_id_hex, *other = data.decode('ascii').split(':')
        logger.debug('{}\tGET udp data from {}:{}\t{}'.format(datetime.datetime.now(), ip_addr, src_port, data))
        if signature == 'ESP-VVF':
            dev_id = int(dev_id_hex, 16)
            payload = json.dumps({
                'device_id': dev_id,
                'ip_address': ip_addr,
                'data': other
            })
            mqtt_client.publish(DEVICES_UDP_NOTIFY_TOPIC_TPL.format(dev_id_hex), payload)

            # device = Device.query.filter(Device.mac_address == dev_id_hex).first()
            # if not device:
            #     device = Device.create(
            #         mac_address=dev_id_hex,
            #         ip_address=ip_addr,
            #         is_online=True
            #     )
            #     db.session.commit()
            # ping_device.apply_async((device.id, ))



udp_listener_thread = None


def start_udp_switch_listener():
    global udp_listener_thread
    if udp_listener_thread and udp_listener_thread.isAlive():
        return
    try:
        udp_sock.close()
    except Exception as e:
        pass
    udp_listener_thread = Thread(target=listener)
    udp_listener_thread.start()


logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.DEBUG)

if __name__ == '__main__':
    listener()
