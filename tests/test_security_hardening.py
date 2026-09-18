"""Adversarial fixtures only: no installed accounts, files or services are touched."""
import asyncio
import gzip
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, AsyncMock
import test_server
import app
from browser_runtime import BrowserRuntime, BrowserUnavailable
from resource_limits import BROWSER_START_RESERVE

class BoundaryTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = test_server.ServerTests.asyncSetUp
    asyncTearDown = test_server.ServerTests.asyncTearDown
    create_account = test_server.ServerTests.create_account
    login_account = test_server.ServerTests.login_account

    async def test_compressed_request_is_rejected_before_application_parsing(self):
        body=gzip.compress(json.dumps({'username':'admin','password':self.password}).encode())
        response=await self.client.post('/api/login',headers={**self.origin,'Content-Encoding':'gzip','Content-Type':'application/json'},data=body)
        self.assertEqual(response.status,415)

    async def test_deep_json_and_wrong_field_types_fail_closed(self):
        for body in ('{"name":[],"kind":"folder"}', '{"name":"'+'a'*20+'","kind":"profile","host":{}}', '{"x":'+'['*1500+'0'+']'*1500+'}'):
            response=await self.client.post('/api/items',headers={**self.headers,'Content-Type':'application/json'},data=body)
            self.assertEqual(response.status,400)
        self.assertEqual((await self.client.get('/api/session',headers=self.headers)).status,200)

    async def test_login_sessions_are_bounded_per_account(self):
        # Existing sessions emulate a long-lived client repeatedly logging in.
        for i in range(24):app.SESSIONS['fixture-'+str(i)]={'user_id':1,'version':1,'expires':9999999999,'created':i}
        response=await self.client.post('/api/login',headers=self.origin,json={'username':'admin','password':self.password})
        self.assertEqual(response.status,200)
        self.assertLessEqual(sum(s['user_id']==1 for s in app.SESSIONS.values()),12)

class BrowserParentBoundary(unittest.IsolatedAsyncioTestCase):
    async def test_profile_symlink_cannot_truncate_host_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'bin').mkdir();(root/'bin/python').touch()
            profile=root/'browsers/1';profile.mkdir(parents=True)
            sentinel=root/'private-host-file';sentinel.write_text('private fixture must survive')
            (profile/'session.log').symlink_to(sentinel)
            runtime=BrowserRuntime(root,venv=root)
            with patch('browser_runtime.browser_security.check'),patch('browser_runtime.available_memory',return_value=BROWSER_START_RESERVE),patch('browser_runtime.asyncio.create_subprocess_exec',new_callable=AsyncMock,side_effect=OSError('fixture does not launch Chromium')):
                with self.assertRaises(BrowserUnavailable):await runtime.start(1,1)
            self.assertEqual(sentinel.read_text(),'private fixture must survive')

class ArchiveBoundary(unittest.TestCase):
    def test_raced_directory_cannot_escape_backup_root(self):
        import io, tarfile
        from safe_archive import add_private_tree
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);tree=root/'user';tree.mkdir();child=tree/'swapped';child.mkdir()
            (child/'ordinary').write_text('mine');private=root/'outside';private.mkdir();(private/'secret').write_text('other account fixture')
            original=os.open
            def race(name, flags, *args, **kwargs):
                if name=='swapped' and kwargs.get('dir_fd') is not None:
                    child.rename(tree/'original');child.symlink_to(private,target_is_directory=True)
                return original(name,flags,*args,**kwargs)
            output=io.BytesIO()
            with tarfile.open(fileobj=output,mode='w') as archive,patch('safe_archive.os.open',side_effect=race):
                add_private_tree(archive,tree,'home',lambda info:info)
            output.seek(0)
            with tarfile.open(fileobj=output) as archive:
                self.assertNotIn('home/swapped/secret',archive.getnames())
            self.assertNotIn(b'other account fixture',output.getvalue())

class AdmissionTests(unittest.IsolatedAsyncioTestCase):
    async def test_limits_are_per_account_and_released_on_error(self):
        from request_security import RequestBudget
        from contextlib import ExitStack
        from aiohttp import web
        budget=RequestBudget()
        with ExitStack() as stack:
            for _ in range(16):stack.enter_context(budget.slot(1))
            with self.assertRaises(web.HTTPTooManyRequests):
                with budget.slot(1):pass
            with budget.slot(2):self.assertEqual(budget.total,17)
        self.assertEqual((budget.total,budget.accounts),(0,{}))
        with self.assertRaises(RuntimeError):
            with budget.slot(1):raise RuntimeError('fixture')
        self.assertEqual((budget.total,budget.accounts),(0,{}))

    async def test_slow_stream_body_times_out(self):
        from request_security import body_chunks
        from types import SimpleNamespace
        from aiohttp import web
        original=asyncio.timeout
        class Stream:
            async def iter_chunked(self,n):
                yield b'first'
                await asyncio.sleep(10)
        with patch('request_security.asyncio.timeout',side_effect=lambda _:original(.01)):
            with self.assertRaises(web.HTTPRequestTimeout):
                async for _ in body_chunks(SimpleNamespace(content=Stream())):pass

class PhpSessionRace(unittest.IsolatedAsyncioTestCase):
    async def test_disconnected_or_changed_session_cannot_finish_slow_post(self):
        import test_phpmyadmin_bridge
        from aiohttp import web
        for change in ('disconnect','profile'):
            fixture=test_phpmyadmin_bridge.BridgeTests();fixture.setUp()
            fixture.app.require_current=lambda request:True
            request=test_phpmyadmin_bridge.Request(token='owner');request.method='POST'
            class Stream:
                async def iter_chunked(self,n):
                    yield b'fixture='
                    if change=='disconnect':fixture.bridge.sessions.clear()
                    else:fixture.db.profile.return_value=({'host':'changed'},'encrypted')
                    yield b'value'
            request.content=Stream()
            with patch('phpmyadmin_bridge.asyncio.open_unix_connection',new_callable=AsyncMock) as connect:
                with self.assertRaises(web.HTTPUnauthorized):await fixture.bridge._view(request)
                connect.assert_not_awaited()

class HttpAdmission(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = BoundaryTests.asyncSetUp
    asyncTearDown = BoundaryTests.asyncTearDown
    create_account = BoundaryTests.create_account
    login_account = BoundaryTests.login_account
    async def test_concurrent_slow_account_cannot_exhaust_other_accounts(self):
        from request_security import BUDGET
        await self.create_account();other=await self.login_account()
        release=asyncio.Event()
        async def body():
            yield b'{'
            await release.wait()
            yield b'}'
        pending=[asyncio.create_task(self.client.put('/api/workspace',headers={**self.headers,'Content-Type':'application/json'},data=body())) for _ in range(16)]
        try:
            for _ in range(100):
                if self.client.server.app[BUDGET].accounts.get(1)==16:break
                await asyncio.sleep(.01)
            self.assertEqual(self.client.server.app[BUDGET].accounts.get(1),16)
            response=await self.client.get('/api/session',headers=self.headers)
            self.assertEqual(response.status,429);self.assertEqual(response.headers.get('Retry-After'),'5')
            response=await self.client.get('/api/session',headers=other)
            self.assertEqual(response.status,200)
        finally:
            release.set();await asyncio.gather(*pending)
        self.assertEqual((await self.client.get('/api/session',headers=self.headers)).status,200)

class AccountMatrix(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = BoundaryTests.asyncSetUp
    asyncTearDown = BoundaryTests.asyncTearDown
    create_account = BoundaryTests.create_account
    login_account = BoundaryTests.login_account

    async def test_four_accounts_including_admins_cannot_read_or_mutate_foreign_objects(self):
        identities=[(1,self.headers)]
        for name in ('matrix-admin','matrix-alice','matrix-bob'):
            uid=await self.create_account(name)
            if name=='matrix-admin':
                self.assertEqual((await self.client.patch('/api/users/'+str(uid),headers=self.headers,json={'role':'admin'})).status,200)
            identities.append((uid,await self.login_account(name)))
        objects=[]
        for uid,headers in identities:
            async def create(path,data):
                r=await self.client.post(path,headers=headers,json=data)
                self.assertIn(r.status,(200,201));return await r.json()
            r=await self.client.post('/api/files/upload?name=fixture.txt',headers=headers,data=('private fixture '+str(uid)).encode());self.assertEqual(r.status,201);file=(await r.json())['id']
            profile=await create('/api/items',{'kind':'profile','name':'Private fixture','host':'example.test','username':'fixture'})
            api=await create('/api/development/requests',{'name':'Private fixture','url':'https://example.test'})
            database=await create('/api/databases/connections',{'name':'Private fixture','host':'example.test','username':'fixture'})
            project=await create('/api/development/arduino',{'action':'create','name':'Fixture'})
            self.assertEqual((await self.client.put('/api/documents/notes',headers=headers,json={'text':'private fixture '+str(uid)})).status,200)
            objects.append(dict(owner=uid,file=file,profile=profile['id'],api=api['id'],database=database['id'],project=project['id']))
        for uid,headers in identities:
            notes=await (await self.client.get('/api/documents/notes?user_id=1',headers=headers)).json()
            self.assertEqual(notes['data']['text'],'private fixture '+str(uid))
            for obj in objects:
                if obj['owner']==uid:continue
                cases=[('GET','/api/files/'+obj['file']+'/download',None),('GET','/api/files/'+obj['file']+'/content',None),('POST','/api/files/'+obj['file']+'/trash',{}),('PUT','/api/items/'+obj['profile'],{'kind':'profile','name':'Overwrite','host':'example.test','username':'fixture'}),('DELETE','/api/items/'+obj['profile'],None),('PUT','/api/development/requests/'+obj['api'],{'name':'Overwrite','url':'https://example.test'}),('DELETE','/api/development/requests/'+obj['api'],None),('PUT','/api/databases/connections/'+obj['database'],{}),('DELETE','/api/databases/connections/'+obj['database'],None),('POST','/api/development/arduino',{'action':'open','project':obj['project']})]
                for method,path,data in cases:
                    r=await self.client.request(method,path,headers=headers,json=data)
                    self.assertEqual(r.status,404,(uid,obj['owner'],method,path,await r.text()))
                r=await self.client.get('/api/vault',headers={**headers,'X-Vault-Owner':str(obj['owner'])});self.assertEqual(r.status,403)
        with app.db() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM files WHERE state='live'").fetchone()[0],4)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM items').fetchone()[0],4)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM api_requests').fetchone()[0],4)

class BrowserEnginePolicy(unittest.TestCase):
    def test_known_vulnerable_and_unknown_versions_are_blocked(self):
        from browser_security import supported
        for value in ('Chromium 152.0.7977.82','Chromium 153.0.8010.47','broken',''):
            self.assertFalse(supported(value),value)
        for value in ('Chromium 153.0.8010.52','Chromium 154.0.8040.1'):
            self.assertTrue(supported(value),value)

    def test_inspection_failure_blocks_start(self):
        import browser_security
        with patch.object(browser_security,'_inspect',side_effect=OSError('fixture')):
            with self.assertRaisesRegex(RuntimeError,'security update'):browser_security.check()

class AuditPrivacy(unittest.TestCase):
    def test_authentication_log_contains_no_request_secrets(self):
        from request_security import audit_response
        from types import SimpleNamespace
        request=SimpleNamespace(path='/api/users/2/password',method='POST',headers={'Cookie':'sensitive-fixture'},body='password-fixture')
        with self.assertLogs('pi2000.security',level='INFO') as logs:
            audit_response(request,SimpleNamespace(status=200),1)
        self.assertIn('actor=1 target=2 status=200',logs.output[0])
        self.assertNotIn('sensitive-fixture',logs.output[0]);self.assertNotIn('password-fixture',logs.output[0])
