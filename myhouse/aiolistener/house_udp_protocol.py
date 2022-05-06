import asyncio
import datetime
from sqlalchemy.exc import SQLAlchemyError

from myhouse.aiolistener.ping import start_ping_device
from myhouse.aiolistener.utils import get_device_type_by_udp_data, notify
from myhouse.models import Device
from myhouse.extensions import db

import json
import logging
logger = logging.getLogger(__name__)


class HouseServerUdpProtocol:
    def connection_made(self, transport):
        logger.debug('start {}'.format(transport))
        self.transport = transport

    def datagram_received(self, data, addr):
        ip_addr, src_port = addr
        signature, dev_id_hex, *other = data.decode('ascii').split(':')
        logger.debug('{}\tGET udp data from {}:{}\t{}'.format(datetime.datetime.now(), ip_addr, src_port, data))
        if signature == 'ESP-VVF':
            dev_id = int(dev_id_hex, 16)
            packet = {
                'device_id': dev_id,
                'ip_address': ip_addr,
            }
            event_type = 'got_up'
            if other:
                event_type, *other = other
                data = {
                    'kwargs': dict(x.split('=', 1) for x in other if '=' in x),
                    'args': [x for x in other if not '=' in x]
                }
                if not data['args']:
                    del data['args']
                if not data['kwargs']:
                    del data['kwargs']
                if data:
                    packet['data'] = data
            payload = json.dumps(packet)
            if event_type:
                event_type = '/' + event_type
            asyncio.ensure_future(notify(dev_id_hex, payload, event_type))
            # TODO: move blocking calls to the separate threads
            device = Device.query.filter(Device.mac_address == dev_id_hex).first()
            if not device:
                logger.debug('Create device record')
                device = Device(
                    mac_address=dev_id_hex,
                    ip_address=ip_addr,
                    is_online=True,
                    name='new device {}'.format(dev_id_hex),
                    device_type=get_device_type_by_udp_data(packet.get('data'))
                    # TODO: try to determine type by data from it
                )
                try:
                    logger.debug("Device id={}".format(device.id))
                    device.save()
                except SQLAlchemyError as sql_error:
                    logger.error(sql_error)
                    db.session.rollback()
            elif device.ip_address != ip_addr:
                device.ip_address = ip_addr
                try:
                    device.save()
                except SQLAlchemyError as sql_error:
                    logger.error(sql_error)
                    db.session.rollback()

            start_ping_device(device)
            # ping_device.apply_async((device.id,))

    def error_received(self, exc):
        logger.error('Error received:', exc)


def start_udp_server():
    loop = asyncio.get_event_loop()
    logger.debug("start UDP server")
    connect_coro = loop.create_datagram_endpoint(
        HouseServerUdpProtocol, local_addr=('0.0.0.0', 0xB0BA))
    asyncio.ensure_future(connect_coro)
    logger.debug('UDP Listener started')
