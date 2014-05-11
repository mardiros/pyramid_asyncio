pyramid_asyncio
===============

A lib that override pyramid to build asyncio web application.

Basically, it change views to asyncio coroutine.


Getting Started
---------------

pyramid_asyncio add two directives to treat views as coroutine.

* config.add_coroutine_view()

This is a coroutine version of the ``config.add_view``.
pyramid_asyncio provide also a decorator ``coroutine_view_config`` which
is the view_config version for coroutine view.

* config.make_asyncio_app()

This create the wsgi app that work with the aiohttp gunicorn worker.
aiohttp.worker.AsyncGunicornWorker

config.make_wsgi_app() could not be used because the pyramid router
must be changed.


The simple way to create the pyramid app with asyncio is to use the
scaffold.

pyramid_asyncio comme with a scaffold that create a "hello world" application,
check it 

::

    pcreate -s aio_jinja2 helloworld

