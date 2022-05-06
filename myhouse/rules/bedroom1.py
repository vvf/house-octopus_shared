from asyncio import coroutine

from .reactor_worker import reactor
import logging

logger = logging.getLogger(__name__)

SWITCH_DEVICE = '13e668'


@reactor.route('/house/device/{}/<any(up|down):action>'.format(SWITCH_DEVICE))
async def bedroom_action(payload, action):
    logger.debug(payload)
    logger.debug(action)
