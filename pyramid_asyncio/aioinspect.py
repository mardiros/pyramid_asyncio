
import inspect
import asyncio


def is_generator(func):
    return isinstance(func, asyncio.Future) or inspect.isgenerator(func)
