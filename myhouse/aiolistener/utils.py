#######
#

from myhouse.models import Device
import logging

from myhouse.mqtt import get_mqtt_async_client, DEVICES_UDP_NOTIFY_TOPIC_TPL

logger = logging.getLogger(__name__)


def update_device(device_id, kwargs):
    from myhouse.runner import app
    with app.app_context():
        # logger.debug('updrtyate_device {} {}'.format(device_id, kwargs))

        device = Device.query.filter_by(id=device_id).first()
        if device:
            device.update(**kwargs)
        return device


def get_device_type_by_udp_data(params):
    if params and isinstance(params, dict) and 'flow' in params['kwargs']:
        return 'flow'
    return 'unknown'


async def notify(dev_id, payload='', subtopic=''):
    mqtt_client = await get_mqtt_async_client()
    if not subtopic:
        subtopic = ''
    if subtopic and not subtopic.startswith('/'):
        subtopic = '/' + subtopic
    try:
        rv = await mqtt_client.publish(
            DEVICES_UDP_NOTIFY_TOPIC_TPL.format(dev_id) + subtopic,
            (payload or '').encode(),
            0)
        return rv
    except Exception as err:
        logger.exception('Error while notify:{}'.format(err))


def get_device_type_by_root_response(device_json_text):
    return 'unknown'


async def close_tcp_listener(connection):
    # here connection is a tuple of transport & protocol
    if not connection[0]:
        return False
    try:
        rv = connection[0].close()
        return rv
    except Exception as err:
        logger.exception(err)
    return False
