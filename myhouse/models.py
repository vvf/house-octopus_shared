# import sqlalchemy_utils
from sqlalchemy.dialects.postgresql import JSON
from myhouse.database import ReferenceCol, db, Model, SurrogatePK, Column


class Device(SurrogatePK, Model):
    __tablename__ = 'device'
    ip_address = Column(db.String(15), nullable=True)

    mac_address = Column(db.String(32), unique=True, index=True)
    device_type = Column(db.String(120), nullable=False)
    name = Column(db.String(120), nullable=False)
    settings = Column(JSON())
    # items_hints = Column(sqlalchemy_utils.types.json.JSONType())
    description = Column(db.Text)
    is_online = Column(db.Boolean, default=False)

    FIELDS_ALLOWED_TO_UPDATE = {'description', 'name', 'settings'}

    def check_and_update(self, info):
        keys_to_delete = set(info.keys()) - self.FIELDS_ALLOWED_TO_UPDATE
        for invalid_field in keys_to_delete:
            del info[invalid_field]
        self.update(**info)


# class DeviceEvents(SurrogatePK, Model):
#     __tablename__ = 'devices_events'
#     device_id = ReferenceCol('device')
#     device = db.relationship('Device', backref='events')
#     title = db.Column(db.String(120), nullable=False, default='')
#     details = Column(sqlalchemy_utils.types.json.JSONType())

class DeviceSchedule(SurrogatePK, Model):
    device_id = ReferenceCol('device')

    action = Column(db.String(120))
    payload = Column(db.Text)

    minutes = Column(db.Integer, nullable=True)
    hours = Column(db.Integer, nullable=True)
    mday = Column(db.Integer, nullable=True)
    month = Column(db.Integer, nullable=True)
    wday = Column(db.Integer, nullable=True)
    is_once = Column(db.Boolean, default=False, nullable=False)
    seconds = None

    def __init__(self, **kwargs):
        self.seconds = kwargs.get('seconds')
        if 'seconds' in kwargs:
            del kwargs['seconds']
        super(DeviceSchedule, self).__init__(**kwargs)


class WaterConsumption(SurrogatePK, Model):
    __tablename__ = 'water_consumption'
    device_id = ReferenceCol('device')
    start_time = db.Column(db.DateTime, nullable=False)
    finish_time = db.Column(db.DateTime, nullable=False)
    consumption = db.Column(db.Integer)


class TgUser(SurrogatePK, Model):
    __tablename__ = 'tg_user'
    tg_user_id = db.Column(db.String(50), nullable=False)
    is_admin = db.Column(db.Boolean(), nullable=False, default=False)
