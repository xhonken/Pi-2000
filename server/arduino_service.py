"""Arduino worker: separate memory budget, no OS-administration endpoint."""
import os
from aiohttp import web
import app
from arduino_workshop import ArduinoWorkshop
from session_store import SessionStore

app.initialize()
app.SESSIONS = SessionStore(app.STATE / 'admin.sqlite3')
app.WORKER_SOCKET = ''
worker = ArduinoWorkshop(app)
worker.initialize()
application = web.Application(middlewares=[app.guard])
application.router.add_post('/api/development/arduino', worker.handle)
application.cleanup_ctx.append(worker.lifecycle)
path = os.environ.get('WIN2K_ARDUINO_LISTEN', '/run/pi2000-arduino/worker.sock')
web.run_app(application, path=path, access_log=None)
