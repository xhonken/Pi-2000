"""Arduino worker: separate memory budget, no OS-administration endpoint."""
import os
from aiohttp import web
import app
from arduino_workshop import ArduinoWorkshop
from session_store import SessionStore
from runtime_health import RuntimeIdentity

app.initialize()
app.SESSIONS = SessionStore(app.STATE / 'admin.sqlite3')
app.WORKER_SOCKET = ''
worker = ArduinoWorkshop(app)
worker.initialize()
worker.process_state = RuntimeIdentity('arduino')
@web.middleware
async def guard(request, handler):
    if request.path == '/internal/control':
        return await handler(request)
    return await app.guard(request, handler)

async def maintenance(request):
    data = await request.json()
    worker.process_state.control(data)
    return web.json_response({'runtime': worker.process_state.report({
        'jobs': int(worker.busy), 'monitors': sum(m['state'] == 'open' for m in worker.monitors.values())})})

application = web.Application(middlewares=[guard], handler_args={'auto_decompress':False})
application[app.BUDGET] = app.RequestBudget()
application.on_response_prepare.append(app.response_headers)
application.router.add_post('/internal/control', maintenance)
application.router.add_post('/api/development/arduino', worker.handle)
application.cleanup_ctx.append(worker.lifecycle)
path = os.environ.get('WIN2K_ARDUINO_LISTEN', '/run/pi2000-arduino/worker.sock')
web.run_app(application, path=path, access_log=None)
