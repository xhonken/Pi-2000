import asyncio
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest

from aiohttp import web, WSMsgType
from aiohttp.test_utils import TestClient, TestServer
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'server'))
import app
from browser_runtime import BrowserRuntime


class FakeBrowsers:
    def __init__(self, sockets):
        self.sockets = sockets
        self.sessions = {}
        self.stopped = []

    async def start(self, user_id):
        entry = {'socket': self.sockets[user_id], 'process': SimpleNamespace(returncode=None)}
        self.sessions[user_id] = entry
        return entry

    async def stop(self, user_id, remove=False):
        self.sessions.pop(user_id, None)
        self.stopped.append((user_id, remove))

    async def shutdown(self):
        self.sessions.clear()


class BrowserTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        app.STATE = Path(self.temp.name)
        app.SESSIONS.clear()
        app.SOCKETS.clear()
        app.ATTEMPTS.clear()
        self.client = TestClient(TestServer(app.make_app()))
        await self.client.start_server()
        password = (app.STATE / 'initial-password.txt').read_text().strip()
        self.owner = await self.login('admin', password)
        response = await self.client.post('/api/users', headers=self.owner, json={'username':'alice', 'password':'alice-password-123'})
        self.alice_id = (await response.json())['id']
        self.alice = await self.login('alice', 'alice-password-123')
        self.upstream_app = web.Application()
        self.upstream_app.router.add_route('*', '/{path:.*}', self.upstream)
        self.runner = web.AppRunner(self.upstream_app)
        await self.runner.setup()
        sockets = {}
        for uid in (1, self.alice_id):
            path = app.STATE / f'{uid}.sock'
            await web.UnixSite(self.runner, str(path)).start()
            sockets[uid] = path
        app.BROWSERS = FakeBrowsers(sockets)

    async def asyncTearDown(self):
        await self.client.close()
        await self.runner.cleanup()
        self.temp.cleanup()

    async def login(self, username, password):
        response = await self.client.post('/api/login', headers={'Origin':app.ORIGIN}, json={'username':username,'password':password})
        self.assertEqual(response.status, 200)
        return {'Origin':app.ORIGIN, 'Cookie':f"{app.COOKIE}={response.cookies[app.COOKIE].value}"}

    async def upstream(self, request):
        if request.headers.get('Upgrade', '').lower() == 'websocket':
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            async for message in ws:
                if message.type == WSMsgType.TEXT:
                    await ws.send_str(message.data)
                elif message.type == WSMsgType.BINARY:
                    await ws.send_bytes(message.data)
            return ws
        return web.json_response({'socket':str(request.transport.get_extra_info('sockname')),
                                  'path':request.path, 'cookie':request.headers.get('Cookie'),
                                  'authorization':request.headers.get('Authorization'),
                                  'body':await request.text()})

    async def test_private_proxy_and_headers(self):
        self.assertEqual((await self.client.get('/api/browser/view/')).status, 401)
        self.assertEqual((await self.client.get('/api/browser/view/', headers=self.owner)).status, 503)
        self.assertEqual((await self.client.post('/api/browser/start', headers={'Cookie':self.owner['Cookie']})).status, 403)
        self.assertEqual((await self.client.post('/api/browser/start', headers=self.owner)).status, 200)
        self.assertEqual((await self.client.get('/api/browser/view/', headers=self.alice)).status, 503)
        await self.client.post('/api/browser/start', headers=self.alice)
        for uid, headers in ((1,self.owner),(self.alice_id,self.alice)):
            response = await self.client.post('/api/browser/view/upload?user_id=1', headers={**headers,'Authorization':'secret'}, data='my upload')
            result = await response.json()
            self.assertTrue(result['socket'].endswith(f'/{uid}.sock'))
            self.assertIsNone(result['cookie'])
            self.assertIsNone(result['authorization'])
            self.assertEqual(result['body'],'my upload')
            self.assertEqual(response.headers['X-Frame-Options'],'SAMEORIGIN')
            self.assertEqual(response.headers['Cache-Control'],'no-store')
        await self.client.post('/api/browser/stop', headers=self.alice)
        self.assertIn(1,app.BROWSERS.sessions)
        self.assertNotIn(self.alice_id,app.BROWSERS.sessions)

    async def test_stream_origin_logout_and_expiry(self):
        await self.client.post('/api/browser/start', headers=self.alice)
        response = await self.client.get('/api/browser/view/stream', headers={**self.alice,'Origin':'https://evil.invalid','Upgrade':'websocket'})
        self.assertEqual(response.status,403)
        ws = await self.client.ws_connect('/api/browser/view/stream', headers=self.alice)
        await ws.send_bytes(b'video/audio')
        self.assertEqual((await ws.receive(timeout=3)).data,b'video/audio')
        await self.client.post('/api/logout', headers=self.alice)
        self.assertIn((await ws.receive(timeout=3)).type,(WSMsgType.CLOSE,WSMsgType.CLOSED))
        self.assertIn(self.alice_id,app.BROWSERS.sessions)
        self.alice = await self.login('alice','alice-password-123')
        ws = await self.client.ws_connect('/api/browser/view/stream', headers=self.alice)
        token = self.alice['Cookie'].split('=',1)[1]
        app.SESSIONS[token]['expires'] = 0
        self.assertIn((await ws.receive(timeout=3)).type,(WSMsgType.CLOSE,WSMsgType.CLOSED))
        self.assertIn(self.alice_id,app.BROWSERS.sessions)

    async def test_delete_account_removes_browser_profile(self):
        await self.client.post('/api/browser/start', headers=self.alice)
        response = await self.client.delete(f'/api/users/{self.alice_id}',headers=self.owner)
        self.assertEqual(response.status,200)
        self.assertIn((self.alice_id,True),app.BROWSERS.stopped)
        self.assertNotIn(self.alice_id,app.BROWSERS.sessions)

    async def test_status_is_private_and_owner_only_gets_counts(self):
        await self.client.post('/api/browser/start', headers=self.owner)
        await self.client.post('/api/browser/start', headers=self.alice)
        response = await self.client.get('/api/runtime', headers=self.alice)
        data = await response.json()
        self.assertEqual([row['id'] for row in data['users']], [self.alice_id])
        response = await self.client.get('/api/runtime', headers=self.owner)
        data = await response.json()
        self.assertEqual(len(data['users']), 2)
        for row in data['users']:
            self.assertEqual(set(row), {'id','browsers','terminals'})
        response = await self.client.get('/api/health', headers=self.alice)
        self.assertNotIn('disk_free_bytes', await response.json())
        # Supplying another user ID cannot stop that user's browser.
        await self.client.post('/api/browser/stop', headers=self.alice, json={'user_id':1})
        self.assertIn(1, app.BROWSERS.sessions)

    @unittest.skipUnless(shutil.which('bwrap'), 'bubblewrap is required')
    async def test_browser_filesystem_isolation(self):
        profile = app.STATE / 'browsers/1'
        profile.mkdir(parents=True)
        (profile/'mine.txt').write_text('own-data')
        other = app.STATE/'browsers/2'
        other.mkdir()
        (other/'secret.txt').write_text('other-user-data')
        runtime = app.STATE/'runtime'
        runtime.mkdir()
        venv = app.STATE/'venv'
        venv.mkdir()
        manager = BrowserRuntime(app.STATE,venv=venv)
        command = manager.command(profile,runtime)
        command = command[:command.index('/usr/bin/dbus-run-session')] + ['/usr/bin/python3','-c',
            "import json, os; from pathlib import Path; "
            "policy=Path('/etc/chromium/policies/managed/adblock.json'); "
            "assert json.loads(policy.read_text())['ExtensionSettings']['ddkjiahejlhfcafbddmgiahcphecmpfh']['installation_mode']=='force_installed'; "
            "assert not os.access(policy,os.W_OK); assert Path('/home/browser/mine.txt').read_text()=='own-data'; "
            "assert not Path('/var/lib/win2k-admin').exists(); assert not Path('/root').exists(); "
            f"assert not Path({str(Path.home())!r}).exists(); "
            f"assert not Path({str(other)!r}).exists(); print('isolated')"]
        process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        out,err = await asyncio.wait_for(process.communicate(),10)
        self.assertEqual(process.returncode,0,err.decode())
        self.assertEqual(out.strip(),b'isolated')
