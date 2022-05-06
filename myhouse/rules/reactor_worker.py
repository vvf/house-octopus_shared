# listen to the mqtt queue and react to the events
import asyncio
import json
import logging
from asyncio.coroutines import iscoroutinefunction
from collections import defaultdict

from hbmqtt.mqtt.constants import QOS_0
from werkzeug.exceptions import NotFound
from werkzeug.routing import Map, Rule

from myhouse.mqtt import get_mqtt_async_client, AsyncMQTTClient

logger = logging.getLogger(__name__)


class Reactor:
    def __init__(self):
        self._need_update_urls = True
        self.topics_map = Map()
        self.reactor_functions = defaultdict(list)
        self.urls = None
        self.registry = {}
        self.waiting_tasks = {}
        self.mqtt_client = None
        self.ws_dispatch = None
        self.ws_send_subscribed_message = None

    def route(self, topic_re, **options):
        def decorator(reactor_func):
            if not iscoroutinefunction(reactor_func):
                raise AttributeError("route handler should me a coroutine function")
            options['endpoint'] = topic_re
            logger.info(f" added route {topic_re} -> "
                        f"{reactor_func.__module__}.{reactor_func.__name__} "
                        f"({len(self.reactor_functions[topic_re])+1})")
            self.topics_map.add(Rule(topic_re, {}, **options))
            self.reactor_functions[topic_re].append(reactor_func)
            self._need_update_urls = True
            return reactor_func

        return decorator

    def add_ws_subscription(self, topic_re: str, endpoint: str, params=None):
        return
        logger.info(f"add WS route: {topic_re} -> {endpoint}")
        self.urls = None
        self.topics_map.add(Rule(topic_re, params or {}, endpoint=endpoint))

        def _send_to_ws(payload, args):
            if self.ws_send_subscribed_message is None:
                return
            self.ws_send_subscribed_message(endpoint, payload, args)

        self.reactor_functions[endpoint].append(_send_to_ws)

    async def listen_to_mqtt(self):
        mqtt_client: AsyncMQTTClient = await get_mqtt_async_client()
        self.mqtt_client = mqtt_client
        logger.info('Start listen to mqtt server {}'.format(mqtt_client.is_connected))
        await mqtt_client.subscribe([
            ('/house/device/#', QOS_0),
            ('/house/telegramm/#', QOS_0),
            ('/house/notify/#', QOS_0)])
        logger.info('Subscribed')
        while True:
            try:
                message = await mqtt_client.deliver_message()
            except Exception as err:
                logger.error('Error when deliver message:{}'.format(err))
                logger.exception(repr(err))
                return
            logger.info("Got from MQTT topic:%s", message.topic)
            payload = None

            if message.data:
                try:
                    payload = json.loads(message.data.decode())
                except:
                    logger.error('invalid payload (not JSON?): {}'.format(message.data))
            if payload:
                asyncio.ensure_future(self._handle_message(message, payload))
            else:
                logger.error("No payload in message from %s: %s", message.topic, message)
            asyncio.ensure_future(self._send_to_ws(message, payload or {}))

    async def _handle_message(self, message, payload):
        try:
            await self.route_message(message.topic, payload)
        except Exception as err:
            logger.error('Error in calling route for {}'.format(message.topic))
            logger.exception(repr(err))

    async def _send_to_ws(self, message, payload):
        if not self.ws_dispatch:
            return
        try:
            await self.ws_dispatch(message.topic, payload)
        except Exception as err:
            logger.error('Error in dispatch to WS channel %s', message.topic)
            logger.exception(repr(err))

    async def route_message(self, topic, payload):
        # look for the rules which wait for message in this topic
        if self.urls is None or self._need_update_urls:
            logger.info("get routes")
            self.urls = self.get_urls()
            self._need_update_urls = False
        try:
            endpoint, args = self.urls.match(topic)
        except NotFound:
            # logger.error('No reactor for topic {}'.format(topic))
            return

        if endpoint and endpoint in self.reactor_functions:
            logger.debug('Route {} to {}'.format(repr(topic), endpoint))
            # TODO: might be run in parallel all handlers
            for coroutine_handler in self.reactor_functions[endpoint]:
                await coroutine_handler(payload, **args)

    def get_urls(self):
        return self.topics_map.bind('mqtt.server', '/')

    async def _pinger(self):
        mqtt = await get_mqtt_async_client()
        await mqtt.ping()
        asyncio.get_event_loop().call_later(30, self.do_ping)

    def do_ping(self):
        asyncio.ensure_future(self._pinger())


reactor = Reactor()
