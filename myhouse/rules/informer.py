import asyncio
import logging
import os

import aiohttp
import async_timeout

from .bathroom import LIGHT_DEVICE as BATHROOM_LIGHT_DEVICE, LIGHT_SWITCH as BATHROOM_LIGHT_SWITCH, \
    MOTION_SENSOR as BATHROOM_MOTION_SENSOR, SHOWER_FLOW_DEVICE
from .reactor_worker import reactor
from .utils import get_device_by_id, get_device_by_mac, update_device

# send messages by telegramm

WALL_LIGHTS_MAC = '9c27b1'
event_decode = {
    WALL_LIGHTS_MAC: {
        'XD': "Нажали кнопку подсветки стола",
        'Xu': "Отпустили кнопку подсветки стола",
        'XU': "Отпустили кнопку подсветки стола",
        'XL': "Удерживают кнопку подсветки стола",
        'YD': "Нажали кнопку подсветки стены",
        'Yu': "Отпустили кнопку подсветки стены",
        'YU': "Отпустили кнопку подсветки стены",
        'YL': "Удерживают кнопку подсветки стены"
    },
    BATHROOM_LIGHT_DEVICE: {
        'up': {
            '{args[1]}': {
                str(BATHROOM_LIGHT_SWITCH): 'Включен свет в ванной (включателем)',
                str(BATHROOM_MOTION_SENSOR): 'IGNORE',
                'ANY': 'IGNORE'
            }
        },
        'down': {
            "{args[1]}": {
                str(BATHROOM_MOTION_SENSOR): 'Обнаружено движение в ванной',
                str(BATHROOM_LIGHT_SWITCH): 'Выключен свет в ванной (включателем)',
                'ANY': 'IGNORE'
            }
        },
        'hold': 'IGNORE'
    }

}

logger = logging.getLogger(__name__)

URL = 'https://api.telegram.org/bot'  # Адрес HTTP Bot API
TOKEN = os.environ.get('TG_BOT_TOKEN')
ADMINS_ID = list(map(int, os.environ.get('TG_ADMINS_IDS', "1430319").split(':')))

send_notify_to = set()


@reactor.route('/house/notify/turn_<any(on,off):on_off>')
async def inform_subscribing(payload, on_off):
    if on_off == 'on':
        send_notify_to.add(payload['chat_id'])
        response_text = "You subscribed to all events"
    else:
        send_notify_to.remove(payload['chat_id'])
        response_text = "You unsubscribed from events"
    await send_text(payload['chat_id'], response_text)


@reactor.route('/house/notify/telegramm')
async def inform_direct_message(payload):
    logger.debug('--- Will send message: '.format(payload['message']))
    for admin_chat in ADMINS_ID:
        await send_text(admin_chat, payload['message'])


def extract_message(key_tpl, msgs, payload):
    try:
        result_key = key_tpl.format(**payload)
        result = msgs.get(result_key)
    except (KeyError, IndexError, ValueError) as err:
        logger.debug("extract_message error:")
        logger.error(err)
        result = None
        result_key = None
    if not result and result_key:
        any_message = msgs.get('ANY')
        if not any_message:
            return None
        try:
            result = any_message.format(result_key)
        except (KeyError, IndexError, ValueError):
            result = any_message
    return result


@reactor.route(
    '/house/device/<any({}):device_mac>/events/<event>'.format(','.join([BATHROOM_LIGHT_DEVICE, WALL_LIGHTS_MAC])))
async def inform_buttons_events(payload, device_mac, event):
    if str(device_mac) == SHOWER_FLOW_DEVICE:
        return
    if str(device_mac).strip() == WALL_LIGHTS_MAC and str(event).strip() == 'S':
        return
    if event == 'state':
        return
    logger.debug('Got event to notify {} from device ID:{}'.format(event, device_mac))

    if not send_notify_to:
        return
    if device_mac.startswith('id-'):
        device = await get_device_by_id(device_mac[3:])
    else:
        device = await get_device_by_mac(device_mac)
        if not device.is_online:
            device.is_online = True
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, update_device, device.id, dict(is_online=True))
    if device:
        device_mac = device.mac_address
        default_message = "Событие от устройства {} ({}): {}\npayload={}".format(device.name, device_mac, event,
                                                                                 payload)
    else:
        default_message = "Событие от неизвестного устройства {} : {}\npayload={}".format(device_mac, event, payload)
    device_events = event_decode.get(device_mac, {})
    event_detail = device_events.get(event)
    if isinstance(event_detail, str):
        inform_message = event_detail
    elif event_detail:
        try:
            inform_message = '\n'.join(ln for ln in
                                       [extract_message(key_tpl, msgs, payload) for key_tpl, msgs in
                                        event_detail.items()]
                                       if ln and ln != 'IGNORE') or default_message
        except Exception as err:
            logger.error(err)
            inform_message = default_message
    else:
        inform_message = default_message

    if inform_message == 'IGNORE':
        logger.debug("Rule says to ignore this event")
        return

    for admin_chat in send_notify_to:
        await send_text(admin_chat, inform_message)


shower_messages = {
    'start': 'Включили душ',
    'finish': 'Выключили душ'
}


@reactor.route('/house/device/shower/<event>')
async def inform_shower_events(payload, event):
    if not send_notify_to:
        return
    message = shower_messages.get(event)
    if not message:
        return
    for admin_chat in send_notify_to:
        await send_text(admin_chat, message.format(**payload))


if TOKEN:
    async def send_text(chat_id, text):
        """Отправка текстового сообщения по chat_id
        ToDo: повторная отправка при неудаче"""
        data = {'chat_id': chat_id, 'text': text, 'reply_markup': '{"hide_keyboard":true}'}  # Формирование запроса
        session = aiohttp.ClientSession()
        try:
            logger.debug('Send message to {} (len={})'.format(chat_id, len(text)))
            with async_timeout.timeout(45):
                url = URL + TOKEN + '/sendMessage'
                response = await session.post(url, data=data)
                response_text = await response.read()
                response.close()
                return True
        except Exception as err:
            logger.error('Error in send telegram message')
            logger.error(err)
        finally:
            await session.close()
        return False
else:
    async def send_text(chat_id, text):
        logger.error('NO TG_BOT_TOKEN defined in eviroment variable')

startup_message = "House events systems started."


@reactor.route('/house/notify/reactor/started')
async def inform_start(payload):
    logger.error("Started event caught. Say it to admin")
    for admin_chat in ADMINS_ID:
        await send_text(admin_chat, startup_message)


# logger.addHandler(logging.StreamHandler())
# logger.setLevel(logging.DEBUG)
