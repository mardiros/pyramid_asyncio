import asyncio

from gunicorn.workers.gaiohttp import AiohttpWorker as BaseWorker

class AiohttpWorker(BaseWorker):

    @asyncio.coroutine
    def _run(self):

        if hasattr(self.wsgi, 'open'):
            yield from self.wsgi.open()

        yield from super()._run()

    def handle_quit(self, sig, frame):
        self.alive = False

    handle_exit = handle_quit
