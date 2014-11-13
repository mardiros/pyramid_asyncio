import asyncio
from io import BytesIO

from zope.interface import implementer
from pyramid.interfaces import (
    IRequestFactory,
    IRequest,
    IAuthenticationPolicy,
    IAuthorizationPolicy,
    )

from pyramid.request import Request as BaseRequest
from pyramid.security import Allowed
from .aioinspect import is_generator


@implementer(IRequest)
class Request(BaseRequest):

    @asyncio.coroutine
    def _process_response_callbacks(self, response):
        callbacks = self.response_callbacks
        while callbacks:
            callback = callbacks.pop(0)
            callback_resp = callback(self, response)
            if is_generator(callback_resp):
                yield from callback_resp

    @asyncio.coroutine
    def _process_finished_callbacks(self):
        callbacks = self.finished_callbacks
        while callbacks:
            callback = callbacks.pop(0)
            callback_resp = callback(self)
            if is_generator(callback_resp):
                yield from callback_resp

    @asyncio.coroutine
    def has_permission(self, permission, context=None):
        if context is None:
            context = self.context
        reg = self.registry
        authn_policy = reg.queryUtility(IAuthenticationPolicy)
        if authn_policy is None:
            return Allowed('No authentication policy in use.')
        authz_policy = reg.queryUtility(IAuthorizationPolicy)
        if authz_policy is None:
            raise ValueError('Authentication policy registered without '
                             'authorization policy') # should never happen
        principals = authn_policy.effective_principals(self)
        if is_generator(principals):
            principals = yield from principals
        permits = authz_policy.permits(context, principals, permission)
        if is_generator(permits):
            permits = yield from permits
        return permits


@implementer(IRequestFactory)
class RequestFactory:
    """ A utility which generates a request """

    @asyncio.coroutine
    def __call__(self, environ):
        """ Return an object implementing IRequest, e.g. an instance
        of ``pyramid.request.Request``"""

        body = environ['wsgi.input'].read()
        if is_generator(body):
            # wsgi.input can be a generator depending of
            # the configuration of aiohttp
            body = yield from body 
        environ['wsgi.input'] = BytesIO(body)
        return Request(environ)

    @classmethod
    def blank(cls, path):
        """ Return an empty request object (see
        :meth:`pyramid.request.Request.blank`)"""
        return Request.blank(path)
