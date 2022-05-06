import asyncio
import importlib
import logging
import os
import pkgutil
from logging.handlers import TimedRotatingFileHandler

from .reactor_worker import reactor
from myhouse.wsserver import Subscriber, run_wsserver

logger = logging.getLogger(__name__)

listen_task = None
is_waiting_disconnect = False


def reconnect_mqtt(reactor):
    asyncio.ensure_future(reconnect_coro(reactor))


async def reconnect_coro(reactor):
    global listen_task, is_waiting_disconnect
    # if mqtt client already is
    if reactor.mqtt_client:
        # do nothing if it is already doing
        if is_waiting_disconnect:
            return
        is_waiting_disconnect = True
        # wait for disconnect from mqtt
        await reactor.mqtt_client._handler.wait_disconnect()
        # check if it is really not connected :)
        if not reactor.mqtt_client._connected_state.is_set():
            logger.debug('disconnected, waiting connect')
            # stop listener (subscriber) task
            if listen_task:
                listen_task.cancel()
                listen_task = None
            # wait for connect to broker
            await reactor.mqtt_client._connected_state.wait()
            logger.debug('Reconected...')
        is_waiting_disconnect = False
        # restart self to react to the next disconnect
        asyncio.get_event_loop().call_later(1, reconnect_mqtt, reactor)
    else:
        await asyncio.sleep(3)
        asyncio.get_event_loop().call_later(1, reconnect_mqtt, reactor)
    # start listener (subscriber) task
    if not listen_task:
        logger.debug('... start listen to mqtt channels')
        listen_task = asyncio.ensure_future(reactor.listen_to_mqtt())


def ws_to_mqtt(topic: str, payload: str):
    from . import utils
    asyncio.ensure_future(utils.publish(topic, payload))


async def on_start():
    from .utils import publish
    await asyncio.sleep(5)
    await publish('/house/notify/reactor/started', {'ok': True})


def start_loop(debug):
    global listen_task
    pkgpath = os.path.dirname(__file__)
    logs_dir = os.path.join(os.path.dirname(pkgpath), 'logs')
    rotate_handler = TimedRotatingFileHandler(
        os.path.join(logs_dir, 'house-reactor.log'),
        when='d', backupCount=10)
    log_formatter = logging.Formatter('%(asctime)s %(name)s %(levelname)-8s %(message)s')
    rotate_handler.setFormatter(log_formatter)
    logger.addHandler(rotate_handler)
    if debug:
        logger.addHandler(logging.StreamHandler())

    logger.setLevel(logging.DEBUG)
    logger.debug('search rules in path {}'.format(pkgpath))
    pkgs = pkgutil.iter_modules([pkgpath])
    logger.debug('Load packeges {}'.format([name for _, name, _ in pkgs]))
    for ldr, name, is_pkg in pkgutil.iter_modules([pkgpath]):
        logger.debug('load rules from module {}'.format(name))
        importlib.import_module('.' + name, __package__)
    loop = asyncio.get_event_loop()
    # "dependency injection" (connections)
    reactor.ws_dispatch = Subscriber.dispatch_message
    reactor.ws_send_subscribed_message = Subscriber.send_subscribed_message
    Subscriber.add_subscription = reactor.add_ws_subscription

    run_wsserver()
    logger.debug("Connect to MQTT")
    listen_task = asyncio.ensure_future(reactor.listen_to_mqtt())
    reconnect_mqtt(reactor)
    asyncio.ensure_future(on_start())
    #    loop.run_until_complete(reactor.listen_to_mqtt())
    logger.debug("Start event loop")
    try:
        loop.run_forever()
    finally:
        loop.close()
