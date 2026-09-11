"""Disposable loopback-only fixture for the desktop UI smoke tests."""
import sys
import os
import tempfile
from pathlib import Path
from aiohttp import web

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'server'))
import app
import phpmyadmin_bridge
if os.environ.get("WIN2K_TEST_PMA_ROOT"):
    phpmyadmin_bridge.ROOT=Path(os.environ["WIN2K_TEST_PMA_ROOT"])
    phpmyadmin_bridge.SOCKET=os.environ["WIN2K_TEST_PMA_SOCKET"]
state=tempfile.TemporaryDirectory(prefix='win2k-ui-test-')
app.STATE=Path(state.name)
# Never read the real host Local Terminal configuration from a disposable fixture.
app.local_terminal.CONFIG=app.STATE/'local-terminal.json'
app.ORIGIN='http://127.0.0.1:18765'
application=app.make_app()
with app.db() as conn:
    salt='12'*16
    conn.execute("UPDATE users SET salt=?,hash=? WHERE username='admin'",(salt,app.password_hash('browser-test-password',salt)))
api_guard=app.guard
@web.middleware
async def guard(request,handler):
    if request.path.startswith('/api/'):return await api_guard(request,handler)
    return await handler(request)
application.middlewares.clear();application.middlewares.append(guard)
async def index(request):return web.FileResponse(ROOT/'index.html')
application.router.add_get('/',index)
application.router.add_static('/assets',ROOT/'assets')
application.router.add_static('/dist',ROOT/'dist')
if os.environ.get('WIN2K_TEST_SFTP_DIR'):
    import asyncssh
    from test_server import SSHServer
    async def sftp_fixture(application):
        remote=Path(os.environ['WIN2K_TEST_SFTP_DIR'])
        remote.mkdir(exist_ok=True)
        (remote/'hello.py').write_text('print("remote original")\n')
        (remote/'project').mkdir(exist_ok=True)
        key=asyncssh.generate_private_key('ssh-ed25519')
        server=await asyncssh.create_server(SSHServer,'127.0.0.1',0,server_host_keys=[key],sftp_factory=lambda ch:asyncssh.SFTPServer(ch,chroot=str(remote)))
        with app.db() as conn:
            conn.execute('INSERT INTO items (id,parent,kind,name,host,port,username,user_id) VALUES (?,?,?,?,?,?,?,?)',('test-remote',None,'profile','Testenhet','127.0.0.1',server.get_port(),'pi',1))
        yield
        server.close();await server.wait_closed()
    application.cleanup_ctx.append(sftp_fixture)
web.run_app(application,host='127.0.0.1',port=18765,access_log=None)
