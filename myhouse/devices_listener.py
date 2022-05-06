#!/usr/bin/env python

# there are will be code of listening udp socket and change data, and broadcast message
import asyncio
import os
from logging.handlers import TimedRotatingFileHandler

import logging

from myhouse.aiolistener.house_udp_protocol import start_udp_server
from myhouse.aiolistener.ping import start_ping_device
# from myhouse.aiolistener.web import start_web_server
from myhouse.aiolistener import logger

from myhouse.models import Device

loop = asyncio.get_event_loop()


def start_devices_listeners_and_pingers():
    logger.debug('Initial start listeners and pingers for devices')
    for device in Device.query.filter(Device.ip_address != None).all():
        logger.debug('\t{}\t{}'.format(device.ip_address, device.name))
        start_ping_device(device)


pkgpath = os.path.dirname(__file__)
logs_dir = os.path.join(pkgpath, 'logs')
rotate_handler = TimedRotatingFileHandler(
    os.path.join(logs_dir, 'house-device-listener.log'),
    when='d', backupCount=10)
log_formatter = logging.Formatter('%(asctime)s %(name)s %(levelname)-8s %(message)s')
rotate_handler.setFormatter(log_formatter)
logger.addHandler(rotate_handler)
# logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.DEBUG)

async_logger = logging.getLogger('asyncio')
async_logger.setLevel(logging.INFO)
async_logger.addHandler(logging.StreamHandler())


def start_loop():
    start_devices_listeners_and_pingers()
    # start_web_server()
    udp_server = start_udp_server()
    try:
        loop.set_debug(True)
        loop.run_forever()
    finally:
        # udp_server.close()
        loop.close()
