# -*- coding: utf-8 -*-
"""Extensions module. Each extension is initialized in the app factory located
in app.py
"""
from os import path
from flask_sqlalchemy import SQLAlchemy
db = SQLAlchemy()

from flask_migrate import Migrate
migrate = Migrate(
    directory=path.join(path.dirname(path.abspath(__file__)), 'migrations'),
    compare_type=True
)

# if not is_production():
#     from flask_debugtoolbar import DebugToolbarExtension
#     debug_toolbar = DebugToolbarExtension()

# from flask_mail import Mail
# mail = Mail()


# from flask_session import Session
# session = Session()
