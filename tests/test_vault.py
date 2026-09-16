import asyncio
import base64
from contextlib import closing
import copy
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from aiohttp.test_utils import TestClient, TestServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
import app
from backup import snapshot, restore
from vault import KDF


def encoded(n,value):return base64.b64encode(bytes([value])*n).decode()
def envelope(size=48):return {'iv':encoded(12,3),'data':encoded(size,4)}
def fixture():return {'format':1,'id':'a'*32,'kdf':dict(KDF),'a':{'salt':encoded(16,1),'wrapped':envelope()},'b':{'salt':encoded(16,2),'wrapped':envelope()},'recovery':envelope(80),'index':envelope(32),'entries':{'b'*32:envelope()}}

class VaultTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        app.STATE=Path(self.temp.name);app.SESSIONS={};app.WORKER_SOCKET='';app.WORKER_MODE=False
        self.client=TestClient(TestServer(app.make_app()));await self.client.start_server()
        with app.db() as db:
            db.execute("INSERT INTO users(id,username,salt,hash,role) VALUES(2,'alice','s','h','user')")
            db.execute("INSERT INTO users(id,username,salt,hash,role) VALUES(3,'bob','s','h','admin')")
        for uid in (1,2,3):app.SESSIONS['fixture'+str(uid)]={'user_id':uid,'version':1,'expires':9999999999}
    async def asyncTearDown(self):await self.client.close()
    def headers(self,uid,revision=0):return {'Origin':app.ORIGIN,'Cookie':app.COOKIE+'=fixture'+str(uid),'X-Vault-Owner':str(uid),'If-Match':str(revision)}
    async def put(self,uid,data=None,revision=0):return await self.client.put('/api/vault',headers=self.headers(uid,revision),json=fixture() if data is None else data)
    async def test_strict_owner_scope_including_administrators(self):
        self.assertEqual((await self.put(2)).status,200)
        for uid in (1,3):
            response=await self.client.get('/api/vault',headers=self.headers(uid))
            self.assertIsNone((await response.json())['vault'])
            forged={**self.headers(uid),'X-Vault-Owner':'2'}
            self.assertEqual((await self.client.get('/api/vault',headers=forged)).status,403)
            self.assertEqual((await self.client.put('/api/vault',headers=forged,json=fixture())).status,403)
            self.assertEqual((await self.client.get('/api/vault?user_id=2',headers=self.headers(uid))).status,400)
            self.assertEqual((await self.client.get('/api/vault/2',headers=self.headers(uid))).status,404)
        self.assertEqual((await self.put(1)).status,200)
        with app.db() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM vaults').fetchone()[0],2)
    async def test_revision_conflicts_do_not_overwrite_data(self):
        self.assertEqual((await self.put(2)).status,200)
        changed=fixture();changed['id']='c'*32
        self.assertEqual((await self.put(2,changed)).status,409)
        result=await (await self.client.get('/api/vault',headers=self.headers(2))).json()
        self.assertEqual(result['vault']['id'],'a'*32)
        self.assertEqual((await self.put(2,changed,1)).status,200)
        status=await (await self.client.get('/api/vault/status',headers=self.headers(2))).json()
        self.assertEqual(status,{'owner':2,'revision':2})
    async def test_plaintext_fields_bad_kdf_and_invalid_cipher_rejected(self):
        for change in [lambda v:v.update(title='do not store'),lambda v:v.update(user_id=1),lambda v:v['kdf'].update(memory=1),lambda v:v['a'].update(salt='bad'),lambda v:v['entries'].update({'../escape':envelope()}),lambda v:v['entries'].update({'b'*32:{'iv':encoded(12,3),'data':'a secret'}})]:
            v=fixture();change(v);self.assertEqual((await self.put(2,v)).status,400)
        self.assertEqual((await self.client.get('/api/vault',headers=self.headers(2))).headers['Cache-Control'],'no-store')
        with app.db() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM vaults').fetchone()[0],0)
    async def test_quota_and_user_deletion_apply_to_vault(self):
        self.assertEqual((await self.put(2)).status,200)
        with app.db() as db:
            size=db.execute('SELECT size FROM vaults WHERE user_id=2').fetchone()[0]
            self.assertEqual(app.FILES.usage(db,2)['vault'],size)
            db.execute('UPDATE users SET storage_quota=100 WHERE id=2')
        self.assertEqual((await self.put(2,revision=1)).status,409)
        with app.db() as db:
            db.execute('DELETE FROM users WHERE id=2')
            self.assertEqual(db.execute('SELECT COUNT(*) FROM vaults').fetchone()[0],0)
    async def test_origin_and_revoked_session_during_body_read(self):
        headers=self.headers(2);headers.pop('Origin')
        self.assertEqual((await self.client.put('/api/vault',headers=headers,json=fixture())).status,403)
        async def chunks():
            raw=json.dumps(fixture()).encode();yield raw[:100];await asyncio.sleep(.05)
            with app.db() as db:db.execute('UPDATE users SET version=version+1 WHERE id=2')
            yield raw[100:]
        self.assertEqual((await self.client.put('/api/vault',headers=self.headers(2),data=chunks())).status,401)
        with app.db() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM vaults').fetchone()[0],0)
    async def test_backup_contains_only_encrypted_vault_and_restores_it(self):
        await self.put(2)
        archive=await snapshot(app.STATE,app.STATE/'backup','',None)
        stage=app.STATE/'restore';restore(archive,stage)
        with closing(sqlite3.connect(stage/'state/admin.sqlite3')) as db:
            record=db.execute('SELECT user_id,revision,data FROM vaults').fetchone()
            self.assertEqual(record[:2],(2,1));self.assertEqual(json.loads(record[2]),fixture())
