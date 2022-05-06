import os

from . import views
from .extensions import db, migrate
from flask import Flask

from myhouse.settings import ProdConfig

app = Flask(__name__)

def create_app(config_object=ProdConfig):
    """An application factory, as explained here:
        http://flask.pocoo.org/docs/patterns/appfactories/

    :param config_object: The configuration object to use.
    """
    app = Flask(__name__)
    app.config.from_object(config_object)

    if config_object == ProdConfig and os.environ.get('DATABASE_URL'):
        app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']

    if not app.debug:
        import logging
        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler(app.config['LOG_FILE_NAME'])
        file_handler.setLevel(logging.WARNING)
        app.logger.addHandler(file_handler)

    register_extensions(app)
    register_blueprints(app)
    # register_errorhandlers(app)
    return app


def register_extensions(app):
    db.init_app(app)

    migrate.init_app(app, db)
    # session.init_app(app)
    return None


def register_blueprints(app):
    app.register_blueprint(views.blueprint)
    return None

