import asyncio
import datetime
import logging

import aiohttp
import async_timeout

from myhouse.aiolistener.house_event_protocol import create_tcp_listener
from myhouse.aiolistener.utils import close_tcp_listener, get_device_type_by_root_response, update_device, notify

logger = logging.getLogger(__name__)
http_pinging_tasks = {}
loop = asyncio.get_event_loop()

ALLOWED_TCP_PING = False


def start_ping_device(device):
    global http_pinging_tasks
    from myhouse.aiolistener.house_event_protocol import tcp_event_listeners

    if device.ip_address not in http_pinging_tasks or \
            http_pinging_tasks[device.ip_address].get('allow_cancel', False):
        if device.ip_address in http_pinging_tasks:
            http_pinging_tasks[device.ip_address]['task'].cancel()
        logger.debug('start ping loop for {}'.format(device.ip_address))
        http_pinging_tasks[device.ip_address] = {
            'task': asyncio.ensure_future(ping_device(device)),
            'allow_cancel': False,
            'ping_count': 0
        }
    else:
        logger.debug('Disallow ping {} yet'.format(device.ip_address))


    if device.ip_address in tcp_event_listeners and ALLOWED_TCP_PING:
        if tcp_event_listeners[device.ip_address].get('task') \
                and datetime.datetime.now() - tcp_event_listeners[device.ip_address].get('start_time',
                                                                                         datetime.datetime.now()) < datetime.timedelta(
                    minutes=2):
            return
        if tcp_event_listeners[device.ip_address].get('task') and tcp_event_listeners[device.ip_address].get(
                'start_time'):
            logger.debug('Last ping start:{}\t{}\t{}'.format(
                tcp_event_listeners[device.ip_address].get('start_time'),
                datetime.datetime.now() - tcp_event_listeners[device.ip_address].get('start_time',
                                                                                     datetime.datetime.now()),
                datetime.datetime.now() - tcp_event_listeners[device.ip_address].get('start_time',
                                                                                     datetime.datetime.now()) < datetime.timedelta(
                    minutes=1)
            ))
    if device.ip_address not in tcp_event_listeners\
            or datetime.datetime.now() - tcp_event_listeners[device.ip_address]['start_time'] >\
                    datetime.timedelta(minutes=1):  # allow_cancel

        if tcp_event_listeners.get(device.ip_address, {}).get('task'):
            tcp_event_listeners[device.ip_address]['task'].cancel()
        if tcp_event_listeners.get(device.ip_address, {}).get('connection'):
            logger.debug('Close previous event listener for {}'.format(device.ip_address))
            asyncio.ensure_future(close_tcp_listener(tcp_event_listeners[device.ip_address]['connection']))
        logger.debug('start event listener for {}'.format(device.ip_address))
        tcp_event_listeners[device.ip_address] = {
            'task': asyncio.ensure_future(create_tcp_listener(device)),
            'start_time': datetime.datetime.now(),
            'connection': None
        }
    elif tcp_event_listeners[device.ip_address].get('task'):
        logger.debug("Connecting tcp task is running. Can't cancel until a minute")
    else:
        logger.debug("Any other reason to don't start listener???")


async def ping_device(device):
    global http_pinging_tasks
    # check if pinger loop for this device (address) already exists and
    device_id = device.id
    try:
        await asyncio.sleep(8)
        while True:
            session = aiohttp.ClientSession()

            with async_timeout.timeout(60):
                # logger.debug("\t>>>http ping {}".format(device.ip_address))
                try:
                    http_pinging_tasks[device.ip_address]['allow_cancel'] = False
                    response = await session.get('http://{}/'.format(device.ip_address))
                    #  by status update device
                    if response.status == 200:
                        device_json_text = await response.read()
                        if device.device_type == 'unknown':
                            new_device_type = get_device_type_by_root_response(device_json_text)
                            if new_device_type != device.device_type:
                                device.device_type = new_device_type
                                result = await loop.run_in_executor(
                                    None,
                                    update_device,
                                    device_id, dict(device_type=new_device_type)
                                )
                                logger.debug("device updated = {}".format(result))
                                # yield from notify(device.mac_address, device_json_text.decode('utf8'), 'state')
                        if not device.is_online:
                            result = await loop.run_in_executor(
                                None,
                                update_device,
                                device_id, dict(is_online=True)
                            )
                            logger.debug("device updated (is_online=True) = {}".format(result))
                            device.is_online = True
                    else:
                        logger.debug(">>>{}\tresponse status={}".format(device.ip_address, response.status))
                    new_status = response.status == 200
                except aiohttp.ClientError as err:
                    if device.is_online:
                        logger.error('{}\t{}\t{}\tDevice goes offline'.format(device.name, device.ip_address,
                                                                              datetime.datetime.now()))
                        asyncio.ensure_future(notify(
                            device.mac_address,
                            '{}',
                            '/offline'
                        ))

                    new_status = False
                except asyncio.CancelledError as err:
                    raise err
                except Exception as err:
                    logger.error(
                        '{}\t{}\t{}\thttp ping error: {}'.format(device.name, device.ip_address,
                                                                 datetime.datetime.now(), err.__class__.__name__))
                    logger.error(err)
                    new_status = False

                # allow cancel only when task is waiting. So allow task to get some result - success or fail
                http_pinging_tasks[device.ip_address]['allow_cancel'] = True

                if device.is_online != new_status:
                    result = await loop.run_in_executor(
                        None,
                        update_device,
                        device_id, dict(is_online=new_status)
                    )
                    if new_status:
                        # ping (this) detects devise is came online
                        await asyncio.sleep(5)
                        rv = await create_tcp_listener(device)
                        rv = await notify(device.mac_address, '', subtopic=device.is_online and 'online' or 'offline')
                    device.is_online = new_status
            await session.close()
            http_pinging_tasks[device.ip_address]['ping_count'] += 1
            await asyncio.sleep(device.is_online and 60 or 120)

            ## send some data to tcp connection to keep alive the tcp connection
            # tcp_connection = tcp_event_listeners.get(device.ip_address, {}).get('connection')
            # if tcp_connection:
            #     try:
            #         tcp_connection[0].write(b" \n")  # when it is back - it will trimmed and ignored because it's empty
            #         tcp_connection[0].write(b" \r\n")  # when it is back - it will trimmed and ignored because it's empty
            #     except Exception as err:
            #         logger.error("Can't write to tcp connection transport:")
            #         logger.exception(err)
            #         yield from asyncio.sleep(30)
            #         yield from loop.run_in_executor(None, start_ping_device, device)
            #     return
    except asyncio.CancelledError:
        # logger.warn('Ping of {} canceled'.format(device.ip_address))
        return
