"""
Get pyramid working with asyncio
"""
__version__ = '0.2'

from .config import includeme
from .view import coroutine_view_config
