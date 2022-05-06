#!/usr/bin/env python
import asyncio
import json
import logging
import os
import random
from string import ascii_letters
from urllib.parse import parse_qs

import websockets
from websockets.exceptions import ConnectionClosed

logger = logging.getLogger(__name__)
PORT = 8088


async def dispatcher(ws, path_and_qs):
    # depending on path just add to needed queue and loop forever (ignoring messages)
    if '?' in path_and_qs:
        path, qs = path_and_qs.split('?', 1)
        params = parse_qs(qs)
    else:
        path = path_and_qs
        qs = None
        params = {}

    # TODO: here might be security check: expect token in the params and validate it using data from redis
    logger.info('Connected to "{}"'.format(path))
    subscriber = await Subscriber.append(path, ws, params)
    while True:
        try:
            message_raw_data = await ws.recv()
        except ConnectionClosed:
            subscriber.state = 'done'
            message_raw_data = None
            break

        if message_raw_data is None:
            break
        await subscriber.process_ws_message(message_raw_data)


# there might be another way is listening to pattern channel through psubscribe

class Subscriber:
    redis_connection = None
    subscriber = None
    subscriber_creating_lock = asyncio.Lock()
    is_running = False
    connections = {}
    subscriptions = ['socketio']  # any non empty list should be at the first time
    subscribed_routes = {}
    add_subscription = None

    def __init__(self, channel, ws, params):
        self.channel = channel
        self.ws = ws
        self.state = 'ready'
        self.subs_count = 0
        self.id = ''.join(random.choices(ascii_letters, k=12))
        self.params = params

    async def send(self, msg):
        if not self.ws.open:
            logger.debug('Socket on {} closed'.format(self.channel))
            self.state = 'done'
            self.connections[self.channel].remove(self)
            return
        await self.ws.send(json.dumps(msg))

    @classmethod
    async def send_subscribed_message(cls, endpoint, payload, args):
        logger.info(f"Send subscribed message {endpoint}")
        subscriber: Subscriber = cls.subscribed_routes.get(endpoint)
        if subscriber is None or subscriber.state == 'done':
            return

        await subscriber.send(json.dumps({
            "args": args,
            "payload": payload
        }))

    @classmethod
    async def dispatch_message(cls, channel, msg):
        logger.debug(
            'Send msg to "{}" to {} subscribers'.format(channel, len(cls.connections.get(channel, []))))
        if cls.connections.get(channel):
            for ws_connection in cls.connections[channel]:
                if ws_connection.state != 'done':
                    await ws_connection.send(msg)
                cls.connections[channel] = [
                    ws_connection for ws_connection in cls.connections[channel]
                    if ws_connection.state != 'done'
                ]
        elif channel in cls.connections and channel != 'socketio':
            logger.debug("Nobody listen the channel %s, unsubsribe from it on next connection", channel)
            # next append call will remove this channel from subscriptions
            del cls.connections[channel]
            if not cls.connections:
                cls.connections['socketio'] = []

    @classmethod
    async def append(cls, path, ws, params):
        subscriber = Subscriber(path, ws, params)
        if path not in cls.connections:
            cls.connections[path] = []
            cls.subscriptions = list(cls.connections.keys())
        cls.connections[path].append(subscriber)
        if cls.add_subscription is not None:
            endpoint = subscriber.make_endpoint_name()
            cls.subscribed_routes[endpoint] = subscriber
            cls.add_subscription(path, endpoint, subscriber.params)
        return subscriber

    async def process_ws_message(self, raw_data):
        try:
            data = json.loads(raw_data)
        except Exception:
            logger.error("Error parsing message from %s\n%s",
                         self.channel, raw_data)
            return
        if 'topic' in data and 'payload' in data:
            message = data['payload']
            if isinstance(message, (list, tuple, dict)):
                message = json.dumps(message)
            elif not isinstance(message, (str, bytes)):
                message = str(message)
            from myhouse.rules.utils import publish
            await publish(data['topic'], message)
            return
        if 'subscribe' in data:
            if self.add_subscription is not None:
                self.add_subscription(data['subscribe'], self.make_endpoint_name())
            return
        logger.warning('Received unexpected message from websocket on channel %s:\n%s',
                       self, raw_data)

    def make_endpoint_name(self):
        self.subs_count += 1
        return f"{self.id}-{self.subs_count}"


def run_wsserver():
    host = os.environ.get("WSSERVER_HOST") or '0.0.0.0'
    port = os.environ.get("WSSERVER_PORT") or PORT

    logger.info('Start websockets server on {}:{}'.format(host, port))

    start_server = websockets.serve(dispatcher, host, port)

    asyncio.get_event_loop().run_until_complete(start_server)


def main():
    run_wsserver()
    asyncio.get_event_loop().run_forever()


def run_server_logging_debug():
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler())
    wslogger = logging.getLogger('websockets.server')
    wslogger.setLevel(logging.INFO)
    wslogger.addHandler(logging.StreamHandler())
    main()


if __name__ == '__main__':
    run_server_logging_debug()
