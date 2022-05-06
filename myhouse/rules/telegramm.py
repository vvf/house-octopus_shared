from asyncio import coroutine
from functools import wraps

from myhouse.models import Device
from myhouse.rules.utils import get_device_status, publish
from .utils import get_device_by_mac, turn
from .reactor_worker import reactor

import logging

logger = logging.getLogger(__name__)

TELEGRAMM_TO_USER_TOPIC = '/house/notify/telegramm'


def answer_to_telegram(fn):
    coro = coroutine(fn)
    @wraps(fn)
    def wrapper(payload, *args, **kwargs):
        answer = yield from coro(payload, *args, **kwargs)
        yield from publish(TELEGRAMM_TO_USER_TOPIC, answer)
    return coroutine(wrapper)


@reactor.route('/house/telegramm/start')
@answer_to_telegram
def telegramm_get_devices(payload):
    """
    return to the telegramm commands list
    """
    return '''
    /get_devices - get list of devices and commands to get theirs status
    /water - show last time when shower was used
    '''

@reactor.route('/house/telegramm/get_devices')
@answer_to_telegram
def get_devices(payload):
    """
    return to the telegramm channel devices list
    """
    text = '\n'.join('/device/{}/status - {} {}'.format(dev.id, dev.name, dev.is_online and 'ok' or 'off') for dev in Device.query.all())

    return text

@reactor.route('/house/telegramm/device/<int:device_id>/status')
@answer_to_telegram
def device_status(payload, device_id):
    """
    return to the telegramm channel devices list
    """
    device = Device.get_by_id(device_id)
    if not device:
        return 'No that device'

    answer = yield from get_device_status(device)
    # TODO: parse answer and translate to the human language
    return answer


@reactor.route('/house/telegramm/device/<int:device_id>/turn/<int:relay_no>')
@answer_to_telegram
def device_turn(payload, device_id, relay_no):
    """
    return to the telegramm channel devices list
    """
    pass


@reactor.route('/house/telegramm/humans_words')
@answer_to_telegram
def telegramm(payload):
    """
    parse human language and try to understand what exactly he wants
    """
    pass
