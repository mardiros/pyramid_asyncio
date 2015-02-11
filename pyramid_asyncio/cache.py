import asyncio

import simplejson as json
from pyramid.events import NewRequest

from .kvs import cache, serializer


class ApplicationCache(cache.ApplicationCache):

    @classmethod
    @asyncio.coroutine
    def connect(cls, settings):
        """ Call that method in the pyramid configuration phase.
        """
        
        kvs_cache = json.loads(settings['kvs.cache'])
        kvs_cache['kvs'] = 'aioredis'
        settings['kvs.cache'] = json.dumps(kvs_cache)
        super().connect(settings)
        cls.client._client = yield from cls.client._client

    @asyncio.coroutine
    def get(self, key, default=None):
        return (yield from self.client.get(key, default))

    @asyncio.coroutine
    def set(self, key, value, ttl=None):
        yield from self.client.set(key, value, ttl=None)

    @asyncio.coroutine
    def pop(self, key, default=None):
        try:
            ret = yield from self.get(key)
            yield from self.client.delete(key)
            return ret
        except KeyError:
            return default


def subscribe_cache(event):
    request = event.request
    request.set_property(ApplicationCache(request), 'cache', reify=True)


@asyncio.coroutine
def includeme(config):
    settings = config.registry.settings
    if 'kvs.cache' in settings:
        yield from ApplicationCache.connect(settings)
        config.add_subscriber(subscribe_cache, NewRequest)
