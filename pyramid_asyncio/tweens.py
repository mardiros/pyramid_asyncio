import asyncio
import sys

from pyramid.interfaces import (
    IExceptionViewClassifier,
    IRequest,
    IView,
    )

from zope.interface import providedBy

from pyramid.config import tweens

from .aioinspect import is_generator


class Tweens(tweens.Tweens):

    def __call__(self, handler, registry):

        def handle_handler(handler):
            @asyncio.coroutine
            def handle_request(request):
                response = handler(request)
                if is_generator(response):
                    response = yield from response
                return response
            return handle_request

        if self.explicit:
            use = self.explicit
        else:
            use = self.implicit()

        for name, factory in use[::-1]:
            handler = factory(handler, registry)
        return handler

