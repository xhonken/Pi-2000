import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path

import asyncssh
from aiohttp import WSMsgType
from aiohttp.test_utils import TestClient, TestServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'server'))
import app


class SSHServer(asyncssh.SSHServer):
    def begin_auth(self, username):
        return True
    def password_auth_supported(self):
        return True
    def validate_password(self, username, password):
        return username == 'pi' and password == 'ssh-test-password'


async def echo(process):
    process.stdout.write('READY\r\n')
    while True:
        try:
            data = await process.stdin.readline()
            if not data:
                break
            if data.strip() == 'background-job':
                await asyncio.sleep(0.15)
                process.stdout.write('BACKGROUND-JOB-COMPLETED\r\n')
            else:
                process.stdout.write('ECHO:' + data)
        except asyncssh.TerminalSizeChanged:
            continue


class ServerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        app.STATE = Path(self.tmp.name)
        app.SESSIONS.clear()
        app.SOCKETS.clear()
        app.ATTEMPTS.clear()
        self.client = TestClient(TestServer(app.make_app()))
        await self.client.start_server()
        self.password = (app.STATE / 'initial-password.txt').read_text().strip()
        self.origin = {'Origin': app.ORIGIN}
        response = await self.client.post('/api/login', headers=self.origin, json={'username':'admin','password':self.password})
        self.assertEqual(response.status, 200)
        self.token = response.cookies[app.COOKIE].value
        self.headers = {**self.origin, 'Cookie':f'{app.COOKIE}={self.token}'}
        self.key = asyncssh.generate_private_key('ssh-ed25519')
        self.ssh = await asyncssh.create_server(SSHServer, '127.0.0.1', 0, server_host_keys=[self.key], process_factory=echo, line_editor=False)
        self.port = self.ssh.get_port()

    async def asyncTearDown(self):
        await self.client.close()
        self.ssh.close()
        await self.ssh.wait_closed()
        self.tmp.cleanup()

    async def profile(self):
        response = await self.client.post('/api/items', headers=self.headers, json={'name':'Test Pi','kind':'profile','host':'127.0.0.1','port':self.port,'username':'pi'})
        self.assertEqual(response.status, 200)
        return (await response.json())['id']

    async def test_auth_and_origin(self):
        self.assertEqual((await self.client.get('/api/items')).status, 401)
        self.assertEqual((await self.client.post('/api/login', headers=self.origin, json={'username':'admin','password':''})).status, 401)
        self.assertEqual((await self.client.post('/api/items', headers={'Cookie':self.headers['Cookie']}, json={})).status, 403)
        response = await self.client.post('/api/password', headers=self.headers, json={'current':self.password,'password':'new-password-12345'})
        self.assertEqual(response.status, 200)
        self.assertFalse((app.STATE/'initial-password.txt').exists())
        response = await self.client.post('/api/login', headers=self.origin, json={'username':'admin','password':'new-password-12345'})
        self.assertEqual(response.status, 200)

    async def create_account(self, username='alice'):
        response = await self.client.post('/api/users', headers=self.headers, json={'username':username,'password':'alice-password-123'})
        self.assertEqual(response.status, 201)
        return (await response.json())['id']

    async def login_account(self, username='alice', password='alice-password-123'):
        response = await self.client.post('/api/login', headers=self.origin, json={'username':username,'password':password})
        self.assertEqual(response.status, 200)
        return {**self.origin, 'Cookie':f"{app.COOKIE}={response.cookies[app.COOKIE].value}"}

    async def test_user_lifecycle_and_permissions(self):
        uid = await self.create_account()
        headers = await self.login_account()
        self.assertEqual((await self.client.get('/api/users', headers=headers)).status, 403)
        self.assertEqual((await self.client.post('/api/users', headers=headers, json={})).status, 403)
        self.assertEqual((await self.client.patch(f'/api/users/{uid}', headers=headers, json={'active':False})).status, 403)
        self.assertEqual((await self.client.delete(f'/api/users/{uid}', headers=headers)).status, 403)
        self.assertEqual((await self.client.post(f'/api/users/{uid}/password', headers=headers, json={'password':'hacked-password'})).status, 403)
        self.assertEqual((await self.client.get('/api/items', headers=headers)).status, 200)
        duplicate = await self.client.post('/api/users', headers=self.headers, json={'username':'ALICE','password':'alice-password-123'})
        self.assertEqual(duplicate.status, 409)
        app.initialize()
        listing = await (await self.client.get('/api/users', headers=self.headers)).json()
        self.assertEqual(len(listing['users']), 2)
        self.assertNotIn('hash', listing['users'][0])
        ws = await self.client.ws_connect('/api/terminal', headers=headers)
        self.assertEqual((await self.client.patch(f'/api/users/{uid}', headers=self.headers, json={'active':False})).status, 200)
        self.assertIn((await ws.receive(timeout=5)).type, (WSMsgType.CLOSE, WSMsgType.CLOSED))
        self.assertEqual((await self.client.get('/api/session', headers=headers)).status, 401)
        self.assertEqual((await self.client.post('/api/login', headers=self.origin, json={'username':'alice','password':'alice-password-123'})).status, 401)
        self.assertEqual((await self.client.patch(f'/api/users/{uid}', headers=self.headers, json={'active':True})).status, 200)
        headers = await self.login_account()
        self.assertEqual((await self.client.post(f'/api/users/{uid}/password', headers=self.headers, json={'password':'reset-password-123'})).status, 200)
        self.assertEqual((await self.client.get('/api/session', headers=headers)).status, 401)
        headers = await self.login_account(password='reset-password-123')
        self.assertEqual((await self.client.delete(f'/api/users/{uid}', headers=self.headers)).status, 200)
        self.assertEqual((await self.client.get('/api/session', headers=headers)).status, 401)
        self.assertEqual((await self.client.get('/api/session', headers=self.headers)).status, 200)
        self.assertNotIn(b'reset-password-123', (app.STATE/'admin.sqlite3').read_bytes())

    async def test_admin_protection_and_own_password(self):
        admin = await (await self.client.get('/api/session', headers=self.headers)).json()
        uid = admin['id']
        self.assertEqual((await self.client.delete(f'/api/users/{uid}', headers=self.headers)).status, 403)
        self.assertEqual((await self.client.patch(f'/api/users/{uid}', headers=self.headers, json={'active':False})).status, 403)
        self.assertEqual((await self.client.post(f'/api/users/{uid}/password', headers=self.headers, json={'password':'reset-password-123'})).status, 403)
        await self.create_account()
        user_headers = await self.login_account()
        second_admin = await self.login_account('admin', self.password)
        response = await self.client.post('/api/password', headers=self.headers, json={'current':self.password,'password':'new-admin-password'})
        self.assertEqual(response.status, 200)
        self.assertEqual((await self.client.get('/api/session', headers=second_admin)).status, 401)
        self.assertEqual((await self.client.get('/api/session', headers=self.headers)).status, 200)
        self.assertEqual((await self.client.get('/api/session', headers=user_headers)).status, 200)
        self.assertEqual((await self.client.post('/api/password', headers=user_headers, json={'current':'wrong','password':'new-alice-password'})).status, 403)
        self.assertEqual((await self.client.post('/api/password', headers=user_headers, json={'current':'alice-password-123','password':'new-alice-password'})).status, 200)
        app.initialize()
        await self.login_account('admin', 'new-admin-password')
        await self.login_account('alice', 'new-alice-password')

    async def test_owner_controls_admin_roles(self):
        uid = await self.create_account()
        headers = await self.login_account()
        endpoint = f'/api/users/{uid}'
        self.assertEqual((await self.client.patch(endpoint, headers=headers, json={'role':'admin'})).status, 403)
        ws = await self.client.ws_connect('/api/terminal', headers=headers)
        self.assertEqual((await self.client.patch(endpoint, headers=self.headers, json={'role':'admin'})).status, 200)
        self.assertIn((await ws.receive(timeout=5)).type, (WSMsgType.CLOSE, WSMsgType.CLOSED))
        self.assertEqual((await self.client.get('/api/session', headers=headers)).status, 401)
        app.initialize()
        headers = await self.login_account()
        account = await (await self.client.get('/api/session', headers=headers)).json()
        self.assertEqual(account['role'], 'admin')
        self.assertFalse(account['is_owner'])
        self.assertEqual((await self.client.get('/api/users', headers=headers)).status, 200)
        other = await self.create_account('bob')
        self.assertEqual((await self.client.patch(f'/api/users/{other}', headers=headers, json={'active':False})).status, 200)
        self.assertEqual((await self.client.patch(f'/api/users/{other}', headers=headers, json={'role':'admin'})).status, 403)
        owner = await (await self.client.get('/api/session', headers=self.headers)).json()
        self.assertTrue(owner['is_owner'])
        self.assertEqual((await self.client.patch(f"/api/users/{owner['id']}", headers=self.headers, json={'role':'user'})).status, 403)
        self.assertEqual((await self.client.delete(f"/api/users/{owner['id']}", headers=headers)).status, 403)
        self.assertEqual((await self.client.patch(endpoint, headers=self.headers, json={'role':'owner'})).status, 400)
        self.assertEqual((await self.client.patch(endpoint, headers=self.headers, json={'role':'admin','active':True})).status, 400)
        self.assertEqual((await self.client.patch(endpoint, headers=self.headers, json={'role':'user'})).status, 200)
        self.assertEqual((await self.client.get('/api/users', headers=headers)).status, 401)
        headers = await self.login_account()
        self.assertEqual((await self.client.get('/api/users', headers=headers)).status, 403)
        self.assertEqual((await self.client.patch(endpoint, headers=self.headers, json={'role':'admin'})).status, 200)
        self.assertEqual((await self.client.patch(endpoint, headers=self.headers, json={'active':False})).status, 200)
        self.assertEqual((await self.client.delete(endpoint, headers=self.headers)).status, 200)

    async def test_legacy_migration(self):
        with app.db() as conn:
            admin = conn.execute("SELECT * FROM users WHERE role='admin'").fetchone()
            conn.execute('CREATE TABLE admin(id INTEGER PRIMARY KEY,salt TEXT,hash TEXT)')
            conn.execute('INSERT INTO admin VALUES(1,?,?)', (admin['salt'],admin['hash']))
            conn.execute('DROP TABLE users')
        app.initialize()
        app.initialize()
        await self.login_account('admin', self.password)
        with app.db() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM users').fetchone()[0], 1)
            self.assertIsNone(conn.execute("SELECT 1 FROM sqlite_master WHERE name='admin'").fetchone())

    async def test_private_content_and_role_changes(self):
        uid = await self.create_account()
        alice = await self.login_account()
        profile = await self.profile()
        folder = (await (await self.client.post('/api/items', headers=self.headers, json={'name':'Private', 'kind':'folder'})).json())['id']
        self.assertEqual((await (await self.client.get('/api/items', headers=alice)).json())['items'], [])
        payload = {'kind':'profile','name':'Other','host':'127.0.0.1','username':'pi','port':self.port}
        self.assertEqual((await self.client.put('/api/items/'+profile, headers=alice, json=payload)).status, 404)
        self.assertEqual((await self.client.delete('/api/items/'+profile, headers=alice)).status, 404)
        self.assertEqual((await self.client.post('/api/items', headers=alice, json={**payload, 'parent':folder})).status, 400)
        ws = await self.client.ws_connect('/api/terminal', headers=alice)
        await ws.send_json({'profile':profile, 'password':'ssh-test-password'})
        self.assertEqual((await ws.receive_json(timeout=5))['type'], 'error')
        await ws.close()
        response = await self.client.post('/api/items', headers=alice, json={**payload,'user_id':app.SESSIONS[self.token]['user_id']})
        self.assertEqual(response.status, 200)
        private_id = (await response.json())['id']
        self.assertEqual((await self.client.delete('/api/items/'+private_id, headers=self.headers)).status, 404)
        desktop = {'shortcuts':[{'id':'one','name':'Private link','url':'https://example.com','desktop':True,'start':True,'deleted':False}], 'color':'#008080'}
        self.assertEqual((await self.client.put('/api/desktop', headers=alice, json=desktop)).status, 200)
        self.assertIsNone(await (await self.client.get('/api/desktop', headers=self.headers)).json())
        app.initialize()
        self.assertEqual(await (await self.client.get('/api/desktop', headers=alice)).json(), desktop)
        await self.client.patch(f'/api/users/{uid}', headers=self.headers, json={'role':'admin'})
        alice = await self.login_account()
        own_items = (await (await self.client.get('/api/items', headers=alice)).json())['items']
        self.assertEqual([item['id'] for item in own_items], [private_id])
        self.assertEqual((await self.client.put('/api/items/'+profile, headers=alice, json=payload)).status, 404)
        self.assertEqual((await self.client.delete('/api/items/'+folder, headers=alice)).status, 404)
        # Trust accepted by one user must not be inherited by another.
        with app.db() as conn:
            conn.execute('INSERT INTO hostkeys VALUES (?,?,?,?)', ('127.0.0.1',self.port,self.key.export_public_key().decode().strip(),app.SESSIONS[self.token]['user_id']))
        ws = await self.client.ws_connect('/api/terminal', headers=alice)
        await ws.send_json({'profile':private_id,'password':'ssh-test-password'})
        self.assertEqual((await ws.receive_json(timeout=5))['type'], 'hostkey')
        await ws.send_json({'type':'trust','accept':True})
        self.assertEqual((await ws.receive_json(timeout=5))['type'], 'connected')
        await ws.close()
        await self.client.delete(f'/api/users/{uid}', headers=self.headers)
        with app.db() as conn:
            for table in ('items','hostkeys','desktops'):
                self.assertEqual(conn.execute(f'SELECT COUNT(*) FROM {table} WHERE user_id=?', (uid,)).fetchone()[0], 0)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM items').fetchone()[0], 2)

    async def test_background_job_survives_disconnect_and_new_login(self):
        profile = await self.profile()
        ws = await self.client.ws_connect('/api/terminal', headers=self.headers)
        await ws.send_json({'profile':profile,'password':'ssh-test-password'})
        self.assertEqual((await ws.receive_json(timeout=5))['type'], 'hostkey')
        await ws.send_json({'type':'trust','accept':True})
        connected = await ws.receive_json(timeout=5)
        terminal_id = connected['id']
        term = app.TERMINALS[terminal_id]
        self.assertEqual(connected['type'], 'connected')
        await ws.send_bytes(b'background-job\n')
        await ws.close()
        await self.client.post('/api/logout', headers=self.headers)
        async def wait_for_job():
            while b'BACKGROUND-JOB-COMPLETED' not in term.history:
                await asyncio.sleep(0.01)
        await asyncio.wait_for(wait_for_job(), 5)
        self.assertEqual(term.state, 'running')
        headers = await self.login_account('admin', self.password)
        listing = await (await self.client.get('/api/terminals', headers=headers)).json()
        self.assertEqual([t['id'] for t in listing['terminals']], [terminal_id])
        resumed = await self.client.ws_connect('/api/terminal', headers=headers)
        await resumed.send_json({'terminal':terminal_id})
        self.assertEqual((await resumed.receive_json(timeout=5))['id'], terminal_id)
        self.assertIn(b'BACKGROUND-JOB-COMPLETED', (await resumed.receive(timeout=5)).data)
        await resumed.send_bytes(b'still-the-same-shell\n')
        self.assertIn(b'ECHO:still-the-same-shell', (await resumed.receive(timeout=5)).data)
        await resumed.close()
        self.assertEqual((await self.client.delete('/api/terminals/'+terminal_id, headers=headers)).status, 200)
        self.assertEqual(term.state, 'ended')
        self.assertNotIn(terminal_id, app.TERMINALS)

    async def test_terminal_privacy_expiry_and_workspace(self):
        uid = await self.create_account()
        alice = await self.login_account()
        profile = await self.profile()
        with app.db() as conn:
            conn.execute('INSERT INTO hostkeys VALUES (?,?,?,?)',('127.0.0.1',self.port,self.key.export_public_key().decode().strip(),app.SESSIONS[self.token]['user_id']))
        ws = await self.client.ws_connect('/api/terminal', headers=self.headers)
        await ws.send_json({'profile':profile,'password':'ssh-test-password'})
        terminal_id = (await ws.receive_json(timeout=5))['id']
        self.assertEqual((await (await self.client.get('/api/terminals', headers=alice)).json())['terminals'], [])
        self.assertEqual((await self.client.delete('/api/terminals/'+terminal_id, headers=alice)).status, 404)
        foreign = await self.client.ws_connect('/api/terminal', headers=alice)
        await foreign.send_json({'terminal':terminal_id})
        self.assertEqual((await foreign.receive_json(timeout=5))['type'], 'error')
        await foreign.close()
        layout = {'windows':[{'type':'terminal-window','terminal':terminal_id,'folder':None,'left':15,'top':20,'width':800,'height':500,'hidden':True,'maximized':False}]}
        self.assertEqual((await self.client.put('/api/workspace', headers=self.headers, json=layout)).status, 200)
        self.assertEqual(await (await self.client.get('/api/workspace', headers=alice)).json(), {'windows':[]})
        app.initialize()
        self.assertEqual(await (await self.client.get('/api/workspace', headers=self.headers)).json(), layout)
        self.assertEqual((await self.client.put('/api/workspace', headers=self.headers, json={'windows':[{'type':'bad'}]})).status, 400)
        app.SESSIONS[self.token]['expires'] = 0
        self.assertEqual((await self.client.get('/api/session', headers=self.headers)).status, 401)
        self.assertEqual(app.TERMINALS[terminal_id].state, 'running')
        await ws.close()
        headers = await self.login_account('admin', self.password)
        self.assertEqual((await self.client.delete('/api/terminals/'+terminal_id, headers=headers)).status, 200)

    async def test_finished_terminal_history_and_bounds(self):
        term = app.PersistentTerminal(app.SESSIONS[self.token]['user_id'], {'id':'test'})
        term.append(b'x' * (app.TERMINAL_HISTORY_LIMIT + 10))
        self.assertEqual(len(term.history), app.TERMINAL_HISTORY_LIMIT)
        self.assertEqual(term.offset, 10)
        term.state = 'ended'
        app.TERMINALS[term.id] = term
        ws = await self.client.ws_connect('/api/terminal', headers=self.headers)
        await ws.send_json({'terminal':term.id})
        connected = await ws.receive_json(timeout=5)
        self.assertTrue(connected['truncated'])
        self.assertEqual(connected['state'], 'ended')
        self.assertEqual(len((await ws.receive(timeout=5)).data), app.TERMINAL_HISTORY_LIMIT)
        self.assertEqual((await ws.receive_json(timeout=5))['type'], 'ended')
        await ws.close()
        self.assertEqual((await self.client.delete('/api/terminals/'+term.id, headers=self.headers)).status, 200)

    async def test_shared_content_migration(self):
        uid = await self.create_account()
        with app.db() as conn:
            conn.execute('DROP TABLE items')
            conn.execute('DROP TABLE hostkeys')
            conn.execute('CREATE TABLE items (id TEXT PRIMARY KEY,parent TEXT,kind TEXT,name TEXT,host TEXT,port INTEGER,username TEXT)')
            conn.execute('CREATE TABLE hostkeys (host TEXT,port INTEGER,key TEXT,PRIMARY KEY(host,port))')
            conn.execute("INSERT INTO items VALUES ('folder',NULL,'folder','Old folder','',22,'')")
            conn.execute("INSERT INTO items VALUES ('profile','folder','profile','Old profile','host',22,'pi')")
            conn.execute("INSERT INTO hostkeys VALUES ('host',22,'trusted-key')")
        app.initialize()
        app.initialize()
        alice = await self.login_account()
        self.assertEqual((await (await self.client.get('/api/items', headers=alice)).json())['items'], [])
        rows = (await (await self.client.get('/api/items', headers=self.headers)).json())['items']
        self.assertEqual(len(rows), 2)
        self.assertEqual(next(row for row in rows if row['id']=='profile')['parent'], 'folder')
        with app.db() as conn:
            self.assertEqual(conn.execute('SELECT user_id FROM hostkeys').fetchone()[0], app.SESSIONS[self.token]['user_id'])
            self.assertEqual(conn.execute('PRAGMA foreign_key_check').fetchall(), [])

    async def test_folders_persistence_and_cycles(self):
        response = await self.client.post('/api/items', headers=self.headers, json={'name':'Pi','kind':'folder'})
        folder = (await response.json())['id']
        response = await self.client.post('/api/items', headers=self.headers, json={'name':'Child','kind':'folder','parent':folder})
        child = (await response.json())['id']
        response = await self.client.put('/api/items/'+folder, headers=self.headers, json={'name':'Pi','kind':'folder','parent':child})
        self.assertEqual(response.status, 400)
        self.assertEqual((await self.client.delete('/api/items/'+folder,headers=self.headers)).status,400)
        app.initialize()
        self.assertEqual(len((await (await self.client.get('/api/items',headers=self.headers)).json())['items']),2)
        self.assertEqual((await self.client.delete('/api/items/'+child,headers=self.headers)).status,200)
        self.assertEqual((await self.client.delete('/api/items/'+folder,headers=self.headers)).status,200)

    async def test_ssh_terminal_and_logout(self):
        profile = await self.profile()
        ws = await self.client.ws_connect('/api/terminal',headers=self.headers)
        await ws.send_json({'profile':profile,'password':'ssh-test-password','cols':90,'rows':30})
        challenge = await ws.receive_json(timeout=10)
        self.assertEqual(challenge['type'],'hostkey')
        self.assertEqual(challenge['fingerprint'],self.key.get_fingerprint('sha256'))
        await ws.send_json({'type':'trust','accept':True})
        self.assertEqual((await ws.receive_json(timeout=10))['type'],'connected')
        self.assertIn(b'READY',(await ws.receive(timeout=10)).data)
        await ws.send_json({'type':'resize','cols':120,'rows':40})
        await ws.send_bytes(b'hello\n')
        message = await ws.receive(timeout=10)
        self.assertEqual(message.type, WSMsgType.BINARY, message.data)
        self.assertIn(b'ECHO:hello', message.data)
        self.assertEqual((await self.client.post('/api/logout',headers=self.headers)).status,200)
        self.assertIn((await ws.receive(timeout=10)).type,(WSMsgType.CLOSE,WSMsgType.CLOSED))
        self.assertEqual((await self.client.get('/api/items',headers=self.headers)).status,401)
        with app.db() as conn:
            self.assertIsNotNone(conn.execute('SELECT key FROM hostkeys').fetchone())
        self.assertNotIn(b'ssh-test-password',(app.STATE/'admin.sqlite3').read_bytes())

    async def test_changed_host_key_is_rejected(self):
        profile = await self.profile()
        with app.db() as conn:
            other = asyncssh.generate_private_key('ssh-ed25519').export_public_key().decode().strip()
            conn.execute('INSERT INTO hostkeys VALUES (?,?,?,?)',('127.0.0.1',self.port,other,app.SESSIONS[self.token]['user_id']))
        ws = await self.client.ws_connect('/api/terminal',headers=self.headers)
        await ws.send_json({'profile':profile,'password':'ssh-test-password'})
        response=await ws.receive_json(timeout=10)
        self.assertEqual(response['type'],'error')
        self.assertIn('host key',response['message'])
        await ws.close()

    async def test_password_rejection_and_trusted_reconnect(self):
        profile = await self.profile()
        with app.db() as conn:
            conn.execute('INSERT INTO hostkeys VALUES (?,?,?,?)',('127.0.0.1',self.port,self.key.export_public_key().decode().strip(),app.SESSIONS[self.token]['user_id']))
        ws = await self.client.ws_connect('/api/terminal',headers=self.headers)
        await ws.send_json({'profile':profile,'password':'wrong'})
        self.assertEqual((await ws.receive_json(timeout=10))['type'],'error')
        await ws.close()
        ws = await self.client.ws_connect('/api/terminal',headers=self.headers)
        await ws.send_json({'profile':profile,'password':'ssh-test-password'})
        self.assertEqual((await ws.receive_json(timeout=10))['type'],'connected')
        await ws.close()


if __name__ == '__main__':
    unittest.main()
