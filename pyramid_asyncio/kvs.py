import asyncio

try:
    from asyncio_redis import Connection
    from pyramid_kvs import serializer, kvs, session, cache
    from pyramid_kvs.serializer import serializer
except ImportError:
    raise Exception("Packages asyncio_redis and pyramid_kvs required")


class AIORedis(kvs.KVS):

    @asyncio.coroutine
    def get(self, key, default=None):
        if key is None:
            return default
        ret = yield from self.raw_get(key)
        if ret is None:
            return default
        return self._serializer.loads(ret)

    @asyncio.coroutine
    def set(self, key, value, ttl=None):
        value = self._serializer.dumps(value)
        return (yield from self.raw_set(key, value, ttl or self.ttl))

    @asyncio.coroutine
    def delete(self, key):
        yield from self._client.delete([self._get_key(key)])

    @asyncio.coroutine
    def _create_client(self, **kwargs):
        return (yield from Connection.create(**kwargs))

    def _get_key(self, key):
        return super()._get_key(key).decode('utf-8')

    @asyncio.coroutine
    def raw_get(self, key, default=None):
        ret = yield from self._client.get(self._get_key(key))
        return default if ret is None else ret

    @asyncio.coroutine
    def raw_set(self, key, value, ttl):
        yield from self._client.setex(self._get_key(key), ttl,
                                      value)

    @asyncio.coroutine
    def incr(self, key):
        return (yield from self._client.incr(self._get_key(key)))


kvs._implementations['aioredis'] = AIORedis  # XXX Private access

