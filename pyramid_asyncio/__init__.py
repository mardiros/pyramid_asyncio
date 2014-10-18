"""
Get pyramid working with asyncio
"""
import asyncio
import importlib

from pyramid.settings import aslist
from pyramid.interfaces import ITweens

from .config import add_coroutine_view, make_asyncio_app, add_exit_handler
from .tweens import Tweens

def includeme(config):
    # Does not work as expected :/
    # config.registry.registerUtility(Tweens(), ITweens)

    config.add_directive('add_coroutine_view', add_coroutine_view)
    config.add_directive('make_asyncio_app', make_asyncio_app)
    config.add_directive('add_exit_handler', add_exit_handler)
