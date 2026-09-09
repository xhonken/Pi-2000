"""Cross-account development lifecycle and restart/restore regression coverage."""
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from aiohttp.test_utils import TestClient, TestServer
import test_development_tools
import app
import build_info
from backup import snapshot, restore

class StabilizationTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=test_development_tools.DevelopmentTests.asyncSetUp
    asyncTearDown=test_development_tools.DevelopmentTests.asyncTearDown
    call=test_development_tools.DevelopmentTests.call
    async def test_two_regular_accounts_and_restore(self):
        with app.db() as db:
            db.execute("INSERT INTO users (username,salt,hash) VALUES ('third','s','h')")
        app.SESSIONS['third']={'user_id':3,'version':1,'expires':9999999999}
        self.token='other'
        request=await self.call('requests',{'name':'Private A','url':'https://example.com','headers':{'Authorization':'Bearer fixture-secret'}})
        project=await self.call('git',{'action':'init','name':'Private A'})
        await self.call('git',{'action':'write','project':project['id'],'path':'README.md','text':'private A','version':None})
        headers={'Origin':app.ORIGIN,'Cookie':app.COOKIE+'=other'}
        response=await self.client.put('/api/documents/draft-mariadb-workspace',headers=headers,json={'tabs':[{'name':'Query 1','sql':'SELECT 42'}],'active':0});self.assertEqual(response.status,200)
        self.token='third'
        self.assertEqual((await self.call('requests',method='GET'))['requests'],[])
        await self.call('requests/'+request['id'],{'name':'steal','url':'https://example.com'},method='PUT',status=404)
        await self.call('git',{'action':'read','project':project['id'],'path':'README.md'},status=404)
        response=await self.client.get('/api/documents/draft-mariadb-workspace',headers={'Cookie':app.COOKIE+'=third'});self.assertIsNone((await response.json())['data'])
        # Owner status must not grant access to another person's content either.
        self.token='owner';self.assertEqual((await self.call('requests',method='GET'))['requests'],[])
        await self.call('git',{'action':'status','project':project['id']},status=404)
        original=app.STATE
        with tempfile.TemporaryDirectory() as temp:
            temp=Path(temp);archive=await snapshot(original,temp/'backups','',None)
            restore(archive,temp/'restore')
            await self.client.close();app.STATE=temp/'restore/state';app.SESSIONS={}
            self.client=TestClient(TestServer(app.make_app()));await self.client.start_server()
            # Restored archives deliberately cannot revive old login tokens.
            await self.call('requests',method='GET',status=401)
            app.SESSIONS['restored']={'user_id':2,'version':1,'expires':9999999999};self.token='restored'
            self.assertEqual((await self.call('requests',method='GET'))['requests'][0]['headers']['Authorization'],'Bearer fixture-secret')
            self.assertEqual((await self.call('git',{'action':'read','project':project['id'],'path':'README.md'}))['text'],'private A')
            response=await self.client.get('/api/documents/draft-mariadb-workspace',headers={'Cookie':app.COOKIE+'=restored'});self.assertEqual((await response.json())['data']['tabs'][0]['sql'],'SELECT 42')
            with app.db() as db:
                self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok');self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])
            await self.client.close();app.STATE=original

    async def test_version_uses_installed_manifest_and_requires_login(self):
        with patch.object(build_info,'installed',return_value={'version':'0.1.0-alpha.3','revision':'abc123','modified':False,'build':'fixture'}):
            response=await self.client.get('/api/version');self.assertEqual(response.status,401)
            response=await self.client.get('/api/version',headers={'Cookie':app.COOKIE+'=other'})
            self.assertEqual((await response.json())['build'],'fixture');self.assertEqual(response.headers['Cache-Control'],'no-store')
