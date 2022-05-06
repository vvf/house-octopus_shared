import logging

from .app import create_app

from .settings import ProdConfig

from aiomisc.log import basic_config

basic_config(logging.INFO, buffered=True)

app = create_app(ProdConfig)
