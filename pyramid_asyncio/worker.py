import asyncio

from aiohttp.worker import AsyncGunicornWorker as BaseWorker


class AsyncGunicornWorker(BaseWorker):

    @asyncio.coroutine
    def _run(self):

        if hasattr(self.wsgi, 'open'):
            yield from self.wsgi.open()

        yield from super()._run()

    def handle_quit(self, sig, frame):
        self.alive = False

    handle_exit = handle_quit
