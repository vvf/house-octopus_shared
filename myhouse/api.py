from flask import Blueprint
from flask_restful import Api

from myhouse.resources import DeviceCollection, DeviceItem

api_blueprint = Blueprint('api', __name__)
api = Api(api_blueprint, prefix='/api')

api.add_resource(DeviceCollection, '/devices', endpoint='device_collection')
api.add_resource(DeviceItem, '/devices/<int:device_id>', endpoint='device_item')