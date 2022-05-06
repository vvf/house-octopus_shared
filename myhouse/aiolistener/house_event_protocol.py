import asyncio

import logging

import json

from myhouse.aiolistener.utils import notify

tcp_event_listeners = {}

logger = logging.getLogger(__name__)
loop = asyncio.get_event_loop()


class HouseDeviceEventProtocol(asyncio.Protocol):
    def __init__(self, device):
        self.device = device
        self._event_str = ''

    def connection_made(self, transport):
        logger.debug('Connected to {} ({})'.format(self.device.ip_address, self.device.name))
        self.device.is_online = True
        asyncio.ensure_future(notify(
            self.device.mac_address,
            '{}',
            '/online'
        ))
        self.device.save()

    def data_received(self, data):
        self._event_str += data.decode()
        if '\r\n' in self._event_str:
            logger.debug('TCP event from {}:\t{}'.format(self.device.name, self._event_str.strip('\r\n\t ')))
            for event in self._event_str.split('\n'):
                event = event.strip().strip('\r\n \t')
                if event:
                    try:
                        event_type, *event_params = event.split(':')
                        if event_params and event_params[0] == 'JSON':
                            payload = json.loads(':'.join(event_params[1:]))
                        else:
                            if '=' in event_type:
                                event_type, *params2 = event_type.split('=')
                                logger.debug("New event type={}, params2={}".format(event_type, params2))
                                event_params.append(params2.join('='))
                            payload = {
                                'kwargs': dict(x.split('=', 1) for x in event_params if '=' in x),
                                'args': [x for x in event_params if '=' not in x]
                            }

                        if event_type == 'S':
                            continue

                        logger.debug("Event from=%s type=%s, payload=%s",
                                     self.device.mac_address,
                                     event_type, payload)
                        asyncio.ensure_future(notify(
                            self.device.mac_address,
                            json.dumps(payload),
                            '/' + event_type
                        ))
                    except Exception as error:
                        logger.error(repr(error))
                        logger.error(error.__traceback__)
            self._event_str = ''

    def connection_lost(self, exc):
        logger.debug('The server closed the connection. reconnect')
        asyncio.ensure_future(notify(
            self.device.mac_address,
            '{}',
            '/connection_lost'
        ))
        if self.device.ip_address:
            tcp_event_listeners[self.device.ip_address]['allow_cancel'] = True
            from myhouse.aiolistener.ping import start_ping_device
            start_ping_device(self.device)


@asyncio.coroutine
def create_tcp_listener(device):
    global tcp_event_listeners
    if tcp_event_listeners.get(device.ip_address, {}).get('error') in {'no-tcp', 'offline'}:
        return
    # logger.debug('Try to connect to the device {} and listen to the events from it'.format(device.ip_address))
    # device = yield from loop.run_in_executor(None, Device.query.get, (device_id,))
    try:
        yield from asyncio.sleep(1)
        connection = yield from loop.create_connection(
            lambda: HouseDeviceEventProtocol(device),
            host=device.ip_address,
            port=8077
        )
        tcp_event_listeners[device.ip_address]['connection'] = connection
        logger.debug("# TCP Event listener started #\t{} {}".format(device.ip_address, device.name))
        yield from asyncio.sleep(2)
    except ConnectionRefusedError:
        tcp_event_listeners[device.ip_address]['error'] = 'no-tcp'
        tcp_event_listeners[device.ip_address]['connection'] = None
        logger.error("Device doesn't have notification tcp channel.\t{} {}".format(device.ip_address, device.name))
    except asyncio.CancelledError:
        logger.error(
            "Creating device's notification tcp channel cancelled.\t{} {}".format(device.ip_address, device.name))
    except OSError as os_err:
        if os_err.errno == 113:
            tcp_event_listeners[device.ip_address]['error'] = 'offline'
            logger.error("Device is offline.\t{} {}".format(device.ip_address, device.name))
        else:
            tcp_event_listeners[device.ip_address]['error'] = str(os_err)
            logger.error("Device tcp channel os error.\t{} {}".format(device.ip_address, device.name))
            logger.error(os_err)
        tcp_event_listeners[device.ip_address]['connection'] = None
    except Exception as err:
        tcp_event_listeners[device.ip_address]['error'] = err
        tcp_event_listeners[device.ip_address]['connection'] = None
        logger.error('Another error {}:'.format(err.__class__.__name__))
        logger.error(err)
    finally:
        tcp_event_listeners[device.ip_address]['allow_cancel'] = True
        # if connection:
        #     yield from connection.close
