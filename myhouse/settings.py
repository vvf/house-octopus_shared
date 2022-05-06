import os

os_env = os.environ


class Config(object):
    SECRET_KEY = os_env.get('HOUSE_SECRET', 'VVFs House SecretKey:withohz5Iefodee3shohwae')  # TODO: Change me
    APP_DIR = os.path.abspath(os.path.dirname(__file__))  # This directory
    PROJECT_ROOT = os.path.abspath(os.path.join(APP_DIR, os.pardir))
    CACHE_TYPE = 'simple'  # Can be "memcached", "redis", etc.
    WEBPACK_MANIFEST_PATH = os.path.join(PROJECT_ROOT, 'myhouse', 'manifest.json')


class ProdConfig(Config):
    """Production configuration."""
    ENV = 'prod'
    DEBUG = False
    # SQLALCHEMY_DATABASE_URI = 'postgresql://myhouse:aiceeJ3i@localhost/myhouse'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///myhouse.sqlite'
    SQLALCHEMY_TRACK_MODIFICATIONS = True
    SESSION_FILE_DIR = os_env.get('FLASK_SESSION_DIR', 'flask-sessions')
    SESSION_TYPE = 'filesystem'
    LOG_FILE_NAME = os_env.get('LOG_FILE_NAME', 'logs/main-log.log')


switch_cfg_actions = (
    'Noop', 'Toggle this', 'Turn on this', 'Turn off this', 'Toggle all', 'Turn on all', 'Turn off all')
