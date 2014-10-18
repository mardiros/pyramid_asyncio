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


def excview_tween_factory(handler, registry):
    """ a tween_factory that support coroutine """
    adapters = registry.adapters

    @asyncio.coroutine
    def excview_tween(request):
        attrs = request.__dict__
        try:
            response = yield from handler(request)
        except Exception as exc:
            # WARNING: do not assign the result of sys.exc_info() to a local
            # var here, doing so will cause a leak.  We used to actually
            # explicitly delete both "exception" and "exc_info" from ``attrs``
            # in a ``finally:`` clause below, but now we do not because these
            # attributes are useful to upstream tweens.  This actually still
            # apparently causes a reference cycle, but it is broken
            # successfully by the garbage collector (see
            # https://github.com/Pylons/pyramid/issues/1223).
            attrs['exc_info'] = sys.exc_info()
            attrs['exception'] = exc
            # clear old generated request.response, if any; it may
            # have been mutated by the view, and its state is not
            # sane (e.g. caching headers)
            if 'response' in attrs:
                del attrs['response']
            # we use .get instead of .__getitem__ below due to
            # https://github.com/Pylons/pyramid/issues/700
            request_iface = attrs.get('request_iface', IRequest)
            provides = providedBy(exc)
            for_ = (IExceptionViewClassifier, request_iface.combined, provides)
            view_callable = adapters.lookup(for_, IView, default=None)
            if view_callable is None:
                raise
            if asyncio.iscoroutinefunction(view_callable):
                response = yield from view_callable(exc, request)
            else:
                response = view_callable(exc, request)

        return response

    return excview_tween


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

