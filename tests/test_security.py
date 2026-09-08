import asyncio
import json
import unittest
from unittest.mock import patch
import test_server
import app

class SecurityTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=test_server.ServerTests.asyncSetUp
    asyncTearDown=test_server.ServerTests.asyncTearDown
    create_account=test_server.ServerTests.create_account
    login_account=test_server.ServerTests.login_account

    async def test_revoked_admin_cannot_finish_pending_mutations(self):
        uid=await self.create_account()
        await self.client.patch(f'/api/users/{uid}',headers=self.headers,json={'role':'admin'})
        alice=await self.login_account()
        for path,payload in [(f'/api/users/{uid}/storage',{'quota_mb':500}),('/api/items',{'kind':'folder','name':'after revoke'}),('/api/desktop',{'shortcuts':[],'color':'#008080'}),('/api/files/folders',{'name':'after revoke'})]:
            # Renew the test session for each independent in-flight revocation.
            alice=await self.login_account()
            started=asyncio.Event();release=asyncio.Event();raw=json.dumps(payload).encode()
            async def body():
                yield raw[:1];started.set();await release.wait();yield raw[1:]
            method='PATCH' if '/storage' in path else 'PUT' if path=='/api/desktop' else 'POST'
            task=asyncio.create_task(self.client.request(method,path,headers={**alice,'Content-Type':'application/json'},data=body()))
            await started.wait();await asyncio.sleep(.03)
            with app.db() as conn:conn.execute('UPDATE users SET version=version+1 WHERE id=?',(uid,))
            release.set();self.assertEqual((await task).status,401,path)
        with app.db() as conn:
            self.assertEqual(conn.execute('SELECT storage_quota FROM users WHERE id=?',(uid,)).fetchone()[0],52428800)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM files WHERE user_id=?',(uid,)).fetchone()[0],0)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM items WHERE user_id=?',(uid,)).fetchone()[0],0)

    async def test_account_throttle_survives_spoofed_source_rotation(self):
        for number in range(20):
            response=await self.client.post('/api/login',headers={**self.origin,'X-Forwarded-For':f'192.0.2.{number}'},json={'username':'admin','password':'incorrect'})
            self.assertEqual(response.status,401)
        response=await self.client.post('/api/login',headers={**self.origin,'X-Forwarded-For':'198.51.100.9'},json={'username':'ADMIN','password':'incorrect'})
        self.assertEqual(response.status,429)

    async def test_hash_concurrency_is_bounded(self):
        app.HASHING=2
        try:
            response=await self.client.post('/api/login',headers=self.origin,json={'username':'admin','password':self.password})
            self.assertEqual(response.status,429)
        finally:app.HASHING=0

    async def test_origin_and_private_responses(self):
        for path in ['/api/files','/api/users','/api/workspace','/api/desktop','/api/terminals','/api/health']:
            self.assertEqual((await self.client.get(path)).status,401)
        response=await self.client.post('/api/files/folders',headers={'Cookie':self.headers['Cookie'],'Origin':'https://attacker.example'},json={'name':'bad'})
        self.assertEqual(response.status,403)
        response=await self.client.post('/api/items',headers=self.headers,json=[])
        self.assertEqual(response.status,400)
        self.assertEqual(response.headers['Cache-Control'],'no-store')
