import asyncio
import logging
from collections import defaultdict

from zope.interface import implementer
from pyramid.interfaces import ISession, ISessionFactory

from .kvs import session, serializer


log = logging.getLogger(__name__)

@implementer(ISession)
class CookieSession(session.CookieSession):

    def __init__(self, request, client, key_name):
        self._dirty = False
        self.key_name = key_name
        self.client = client
        self.request = request

        self._session_key = self.get_session_key()
        self._session_data = None

    @asyncio.coroutine
    def load_session_data(self):
        self._session_data = defaultdict(defaultdict)

        if not self._session_key:
            log.warn('No session found')
            return

        stored_data = yield from self.client.get(self._session_key)
        if stored_data:
            self._session_data.update(stored_data)
        else:
            self.changed()

    def get_session_key(self):
        session_key = self.request.cookies.get(self.key_name)
        if not session_key:
            session_key = session._create_token()  # XXX private method called
        return session_key

    @asyncio.coroutine
    def save_session(self, request, response):
        if self._session_data is None:  # session invalidated
            self.client.delete(self._session_key)
            response.delete_cookie(self.key_name)
            return
        response.set_cookie(self.key_name, self._session_key,
                            self.client.ttl)
        yield from self.client.set(self._session_key, self._session_data)


@implementer(ISessionFactory)
class SessionFactory(object):
    session_class = CookieSession

    def __init__(self, settings):
        self.config = serializer('json').loads(settings['asyncio.session'])
        self.config.setdefault('key_prefix', 'session::')
        self.key_name = self.config.pop('key_name', 'session_id')
        self._client = None

    @asyncio.coroutine
    def __call__(self, request):
        if self._client is None:
            self.config['kvs'] = 'aioredis'
            self._client = kvs.KVS(**self.config)
            self._client._client = yield from self._client._client
        session = CookieSession(request, self._client, self.key_name)
        yield from session.load_session_data()
        return session
