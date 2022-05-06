#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os

from flask_migrate import MigrateCommand
from flask_script import Manager, Server, Shell
from flask_script.commands import Clean, ShowUrls

from myhouse.database import db
from myhouse.runner import app

HERE = os.path.abspath(os.path.dirname(__file__))
TEST_PATH = os.path.join(HERE, 'tests')

manager = Manager(app)

print(app.extensions['migrate'].configure_args)

def _make_context():
    """Return context dict for a shell session so you can access
    app, db, and the User model by default.
    """
    return {'app': app, 'db': db}


@manager.command
def start_listener():
    from myhouse.devices_listener import start_loop
    start_loop()


@manager.command
def sync_listen():
    from myhouse.udp_listener_sync import listener
    listener()


@manager.command
def wifi_tracker():
    import asyncio
    from wifi_tracker.tracker import main
    asyncio.run(main())


@manager.option('-D', '--debug', action="store_true", default=False)
@manager.command
def rules(**options):
    from myhouse.rules import start_loop
    start_loop(options.get('debug'))


manager.add_command('server', Server(host='0.0.0.0', port=5001))
manager.add_command('shell', Shell(make_context=_make_context))
manager.add_command('db', MigrateCommand)
manager.add_command("urls", ShowUrls())
manager.add_command("clean", Clean())

if __name__ == '__main__':
    manager.run()
