"""
This code is a big copy/paste of code from pyramid and change the
view in order to handle it as a coroutine
"""
import warnings
import asyncio
import inspect

from zope.interface import Interface, implementedBy, implementer
from zope.interface.interfaces import IInterface
from pyramid import renderers
from pyramid.config import Configurator as ConfiguratorBase, global_registries
from pyramid.config.views import (ViewDeriver as ViewDeriverBase,
                                  StaticURLInfo as StaticURLInfoBase,
                                  isexception,
                                  wraps_view,
                                  view_description)
from pyramid.config.util import DEFAULT_PHASH, MAX_ORDER
from pyramid.events import ApplicationCreated
from pyramid.util import action_method, viewdefaults
from pyramid.config.views import MultiView
from pyramid.security import NO_PERMISSION_REQUIRED
from pyramid.response import Response
from pyramid.compat import string_types, is_nonstr_iter
from pyramid.registry import predvalseq, Deferred
from pyramid.exceptions import ConfigurationError
from pyramid.interfaces import (IDefaultPermission, IRequest, IRouteRequest,
                                IView, ISecuredView, IMultiView,
                                IResponse,
                                IRendererFactory, IViewClassifier,
                                IExceptionResponse, IExceptionViewClassifier,
                                )
from pyramid.httpexceptions import HTTPForbidden
from .router import Router, add_exit_handler
from .request import RequestFactory
from .aioinspect import is_generator


@viewdefaults
@action_method
def add_coroutine_view(
    config,
    view=None,
    name="",
    for_=None,
    permission=None,
    request_type=None,
    route_name=None,
    request_method=None,
    request_param=None,
    containment=None,
    attr=None,
    renderer=None,
    wrapper=None,
    xhr=None,
    accept=None,
    header=None,
    path_info=None,
    custom_predicates=(),
    context=None,
    decorator=None,
    mapper=None,
    http_cache=None,
    match_param=None,
    check_csrf=None,
    **predicates):
    """ patched version of pyramid add_view that use asyncio coroutine """
    self = config
    if custom_predicates:
        warnings.warn(
            ('The "custom_predicates" argument to Configurator.add_view '
             'is deprecated as of Pyramid 1.5.  Use '
             '"config.add_view_predicate" and use the registered '
             'view predicate as a predicate argument to add_view instead. '
             'See "Adding A Third Party View, Route, or Subscriber '
             'Predicate" in the "Hooks" chapter of the documentation '
             'for more information.'),
            DeprecationWarning,
            stacklevel=4
            )

    view = self.maybe_dotted(view)
    # transform the view to a coroutine only in case it's really a coroutine
    if not asyncio.iscoroutinefunction(view) and is_generator(view):
        view = asyncio.coroutine(view)

    context = self.maybe_dotted(context)
    for_ = self.maybe_dotted(for_)
    containment = self.maybe_dotted(containment)
    mapper = self.maybe_dotted(mapper)

    def combine(*decorators):
        def decorated(view_callable):
            # reversed() is allows a more natural ordering in the api
            for decorator in reversed(decorators):
                view_callable = decorator(view_callable)
            return view_callable
        return decorated

    if is_nonstr_iter(decorator):
        decorator = combine(*map(self.maybe_dotted, decorator))
    else:
        decorator = self.maybe_dotted(decorator)

    if not view:
        if renderer:
            def view(context, request):
                return {}
        else:
            raise ConfigurationError('"view" was not specified and '
                                     'no "renderer" specified')

    if request_type is not None:
        request_type = self.maybe_dotted(request_type)
        if not IInterface.providedBy(request_type):
            raise ConfigurationError(
                'request_type must be an interface, not %s' % request_type)

    if context is None:
        context = for_

    r_context = context
    if r_context is None:
        r_context = Interface
    if not IInterface.providedBy(r_context):
        r_context = implementedBy(r_context)

    if isinstance(renderer, string_types):
        renderer = renderers.RendererHelper(
            name=renderer, package=self.package,
            registry = self.registry)

    if accept is not None:
        accept = accept.lower()

    introspectables = []
    pvals = predicates.copy()
    pvals.update(
        dict(
            xhr=xhr,
            request_method=request_method,
            path_info=path_info,
            request_param=request_param,
            header=header,
            accept=accept,
            containment=containment,
            request_type=request_type,
            match_param=match_param,
            check_csrf=check_csrf,
            custom=predvalseq(custom_predicates),
            )
        )

    def discrim_func():
        # We need to defer the discriminator until we know what the phash
        # is.  It can't be computed any sooner because thirdparty
        # predicates may not yet exist when add_view is called.
        order, preds, phash = predlist.make(self, **pvals)
        view_intr.update({'phash':phash, 'order':order, 'predicates':preds})
        return ('view', context, name, route_name, phash)

    discriminator = Deferred(discrim_func)

    if inspect.isclass(view) and attr:
        view_desc = 'method %r of %s' % (
            attr, self.object_description(view))
    else:
        view_desc = self.object_description(view)

    tmpl_intr = None

    view_intr = self.introspectable('views',
                                    discriminator,
                                    view_desc,
                                    'view')
    view_intr.update(
        dict(name=name,
             context=context,
             containment=containment,
             request_param=request_param,
             request_methods=request_method,
             route_name=route_name,
             attr=attr,
             xhr=xhr,
             accept=accept,
             header=header,
             path_info=path_info,
             match_param=match_param,
             check_csrf=check_csrf,
             callable=view,
             mapper=mapper,
             decorator=decorator,
             )
        )
    view_intr.update(**predicates)
    introspectables.append(view_intr)
    predlist = self.get_predlist('view')

    def register(permission=permission, renderer=renderer):
        # the discrim_func above is guaranteed to have been called already
        order = view_intr['order']
        preds = view_intr['predicates']
        phash = view_intr['phash']
        request_iface = IRequest
        if route_name is not None:
            request_iface = self.registry.queryUtility(IRouteRequest,
                                                       name=route_name)
            if request_iface is None:
                # route configuration should have already happened in
                # phase 2
                raise ConfigurationError(
                    'No route named %s found for view registration' %
                    route_name)

        if renderer is None:
            # use default renderer if one exists (reg'd in phase 1)
            if self.registry.queryUtility(IRendererFactory) is not None:
                renderer = renderers.RendererHelper(
                    name=None,
                    package=self.package,
                    registry=self.registry
                    )

        if permission is None:
            # intent: will be None if no default permission is registered
            # (reg'd in phase 1)
            permission = self.registry.queryUtility(IDefaultPermission)

        # added by discrim_func above during conflict resolving
        preds = view_intr['predicates']
        order = view_intr['order']
        phash = view_intr['phash']

        # __no_permission_required__ handled by _secure_view
        deriver = ViewDeriver(
            registry=self.registry,
            permission=permission,
            predicates=preds,
            attr=attr,
            renderer=renderer,
            wrapper_viewname=wrapper,
            viewname=name,
            accept=accept,
            order=order,
            phash=phash,
            package=self.package,
            mapper=mapper,
            decorator=decorator,
            http_cache=http_cache,
            )
        derived_view = deriver(view)
        derived_view.__discriminator__ = lambda *arg: discriminator
        # __discriminator__ is used by superdynamic systems
        # that require it for introspection after manual view lookup;
        # see also MultiView.__discriminator__
        view_intr['derived_callable'] = derived_view

        registered = self.registry.adapters.registered

        # A multiviews is a set of views which are registered for
        # exactly the same context type/request type/name triad.  Each
        # consituent view in a multiview differs only by the
        # predicates which it possesses.

        # To find a previously registered view for a context
        # type/request type/name triad, we need to use the
        # ``registered`` method of the adapter registry rather than
        # ``lookup``.  ``registered`` ignores interface inheritance
        # for the required and provided arguments, returning only a
        # view registered previously with the *exact* triad we pass
        # in.

        # We need to do this three times, because we use three
        # different interfaces as the ``provided`` interface while
        # doing registrations, and ``registered`` performs exact
        # matches on all the arguments it receives.

        old_view = None

        for view_type in (IView, ISecuredView, IMultiView):
            old_view = registered((IViewClassifier, request_iface,
                                   r_context), view_type, name)
            if old_view is not None:
                break

        isexc = isexception(context)

        def regclosure():
            if hasattr(derived_view, '__call_permissive__'):
                view_iface = ISecuredView
            else:
                view_iface = IView
            self.registry.registerAdapter(
                derived_view,
                (IViewClassifier, request_iface, context), view_iface, name
                )
            if isexc:
                self.registry.registerAdapter(
                    derived_view,
                    (IExceptionViewClassifier, request_iface, context),
                    view_iface, name)

        is_multiview = IMultiView.providedBy(old_view)
        old_phash = getattr(old_view, '__phash__', DEFAULT_PHASH)

        if old_view is None:
            # - No component was yet registered for any of our I*View
            #   interfaces exactly; this is the first view for this
            #   triad.
            regclosure()

        elif (not is_multiview) and (old_phash == phash):
            # - A single view component was previously registered with
            #   the same predicate hash as this view; this registration
            #   is therefore an override.
            regclosure()

        else:
            # - A view or multiview was already registered for this
            #   triad, and the new view is not an override.

            # XXX we could try to be more efficient here and register
            # a non-secured view for a multiview if none of the
            # multiview's consituent views have a permission
            # associated with them, but this code is getting pretty
            # rough already
            if is_multiview:
                multiview = old_view
            else:
                multiview = MultiView(name)
                old_accept = getattr(old_view, '__accept__', None)
                old_order = getattr(old_view, '__order__', MAX_ORDER)
                multiview.add(old_view, old_order, old_accept, old_phash)
            multiview.add(derived_view, order, accept, phash)
            for view_type in (IView, ISecuredView):
                # unregister any existing views
                self.registry.adapters.unregister(
                    (IViewClassifier, request_iface, r_context),
                    view_type, name=name)
                if isexc:
                    self.registry.adapters.unregister(
                        (IExceptionViewClassifier, request_iface,
                         r_context), view_type, name=name)
            self.registry.registerAdapter(
                multiview,
                (IViewClassifier, request_iface, context),
                IMultiView, name=name)
            if isexc:
                self.registry.registerAdapter(
                    multiview,
                    (IExceptionViewClassifier, request_iface, context),
                    IMultiView, name=name)
        renderer_type = getattr(renderer, 'type', None) # gard against None
        intrspc = self.introspector
        if (
            renderer_type is not None and
            tmpl_intr is not None and
            intrspc is not None and
            intrspc.get('renderer factories', renderer_type) is not None
            ):
            # allow failure of registered template factories to be deferred
            # until view execution, like other bad renderer factories; if
            # we tried to relate this to an existing renderer factory
            # without checking if it the factory actually existed, we'd end
            # up with a KeyError at startup time, which is inconsistent
            # with how other bad renderer registrations behave (they throw
            # a ValueError at view execution time)
            tmpl_intr.relate('renderer factories', renderer.type)

    if mapper:
        mapper_intr = self.introspectable(
            'view mappers',
            discriminator,
            'view mapper for %s' % view_desc,
            'view mapper'
            )
        mapper_intr['mapper'] = mapper
        mapper_intr.relate('views', discriminator)
        introspectables.append(mapper_intr)
    if route_name:
        view_intr.relate('routes', route_name) # see add_route
    if renderer is not None and renderer.name and '.' in renderer.name:
        # the renderer is a template
        tmpl_intr = self.introspectable(
            'templates',
            discriminator,
            renderer.name,
            'template'
            )
        tmpl_intr.relate('views', discriminator)
        tmpl_intr['name'] = renderer.name
        tmpl_intr['type'] = renderer.type
        tmpl_intr['renderer'] = renderer
        introspectables.append(tmpl_intr)
    if permission is not None:
        # if a permission exists, register a permission introspectable
        perm_intr = self.introspectable(
            'permissions',
            permission,
            permission,
            'permission'
            )
        perm_intr['value'] = permission
        perm_intr.relate('views', discriminator)
        introspectables.append(perm_intr)
    self.action(discriminator, register, introspectables=introspectables)


def make_asyncio_app(config):
    self = config
    self.set_request_factory(RequestFactory())
    self.commit()
    app = Router(self)

    # Allow tools like "pshell development.ini" to find the 'last'
    # registry configured.
    global_registries.add(self.registry)

    # Push the registry onto the stack in case any code that depends on
    # the registry threadlocal APIs used in listeners subscribed to the
    # IApplicationCreated event.
    self.manager.push({'registry':self.registry, 'request':None})
    try:
        self.registry.notify(ApplicationCreated(app))
    finally:
        self.manager.pop()

    return app



class ViewDeriver(ViewDeriverBase):

    @wraps_view
    def secured_view(self, view):
        permission = self.kw.get('permission')
        if permission == NO_PERMISSION_REQUIRED:
            # allow views registered within configurations that have a
            # default permission to explicitly override the default
            # permission, replacing it with no permission at all
            permission = None

        wrapped_view = view
        if self.authn_policy and self.authz_policy and (permission is not None):
            @asyncio.coroutine
            def _permitted(context, request):
                principals = self.authn_policy.effective_principals(request)
                if is_generator(principals):
                    principals = yield from principals
                return self.authz_policy.permits(context, principals,
                                                 permission)
            @asyncio.coroutine
            def _secured_view(context, request):
                result = yield from _permitted(context, request)
                if result:
                    return view(context, request)
                view_name = getattr(view, '__name__', view)
                msg = getattr(
                    request, 'authdebug_message',
                    'Unauthorized: %s failed permission check' % view_name)
                raise HTTPForbidden(msg, result=result)
            _secured_view.__call_permissive__ = view
            _secured_view.__permitted__ = _permitted
            _secured_view.__permission__ = permission
            wrapped_view = _secured_view

        return wrapped_view

    def _rendered_view(self, view, view_renderer):
        """ Render an async view """

        @asyncio.coroutine
        def rendered_view(context, request):

            renderer = view_renderer
            result = view(context, request)
            if is_generator(result):
                result = yield from result

            if result.__class__ is Response:  # potential common case
                response = result
            else:
                registry = self.registry
                # this must adapt, it can't do a simple interface check
                # (avoid trying to render webob responses)
                response = registry.queryAdapterOrSelf(result, IResponse)
                if response is None:
                    attrs = getattr(request, '__dict__', {})
                    if 'override_renderer' in attrs:
                        # renderer overridden by newrequest event or other
                        renderer_name = attrs.pop('override_renderer')
                        renderer = renderers.RendererHelper(
                            name=renderer_name,
                            package=self.kw.get('package'),
                            registry=registry)
                    if '__view__' in attrs:
                        view_inst = attrs.pop('__view__')
                    else:
                        view_inst = getattr(view, '__original_view__', view)
                    response = renderer.render_view(request, result, view_inst,
                                                    context)
            return response

        return rendered_view

    def _response_resolved_view(self, view):
        registry = self.registry

        def viewresult_to_response(context, request):

            result = yield from view(context, request)
            if result.__class__ is Response:  # common case
                response = result
            else:
                response = registry.queryAdapterOrSelf(result, IResponse)
                if response is None:
                    if result is None:
                        append = (' You may have forgotten to return a value '
                                  'from the view callable.')
                    elif isinstance(result, dict):
                        append = (' You may have forgotten to define a '
                                  'renderer in the view configuration.')
                    else:
                        append = ''

                    msg = ('Could not convert return value of the view '
                           'callable %s into a response object. '
                           'The value returned was %r.' + append)

                    raise ValueError(msg % (view_description(view), result))

            return response

        return viewresult_to_response


def includeme(config):
    # Does not work as expected :/
    # config.registry.registerUtility(Tweens(), ITweens)

    config.add_directive('add_coroutine_view', add_coroutine_view)
    config.add_directive('make_asyncio_app', make_asyncio_app)
    config.add_directive('add_exit_handler', add_exit_handler)
