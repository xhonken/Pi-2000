import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path
from aiohttp.test_utils import TestClient, TestServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
import app
from mariadb_fixture import MariaDBFixture
from database_tools import BoundedConnection, ResultLimit, identifier


class DatabaseTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.database = MariaDBFixture().__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.database.__exit__(None,None,None)

    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory()
        app.STATE=Path(self.temp.name);app.SESSIONS={};app.WORKER_SOCKET='';app.WORKER_MODE=False
        self.client=TestClient(TestServer(app.make_app()));await self.client.start_server()
        with app.db() as db:
            db.execute("INSERT INTO users (username,salt,hash) VALUES ('other','salt','hash')")
        app.SESSIONS['owner']={'user_id':1,'version':1,'expires':9999999999}
        app.SESSIONS['other']={'user_id':2,'version':1,'expires':9999999999}
        self.token='owner'
        self.profile=await self.call('/connections',{'name':'Disposable','host':'127.0.0.1','port':self.database.port,'username':'root','database':'','tls':'disabled','save_password':True,'password':''})

    async def asyncTearDown(self):
        await self.client.close();self.temp.cleanup()

    async def call(self,path,data=None,method='POST',status=200):
        response=await self.client.request(method,'/api/databases'+path,json=data,headers={'Origin':app.ORIGIN,'Cookie':app.COOKIE+'='+self.token})
        result=await response.json()
        self.assertEqual(response.status,status,result)
        return result

    async def connect(self):
        return (await self.call('/command',{'action':'connect','connection':self.profile['id']}))['session']

    async def test_private_profiles_encrypted_and_endpoint_change(self):
        self.assertNotIn('password',self.profile)
        with app.db() as db:
            secret=db.execute('SELECT secret FROM database_connections').fetchone()[0]
            self.assertTrue(secret.startswith('gAAAA'))
        self.token='other'
        self.assertEqual((await self.call('/connections',method='GET'))['connections'],[])
        await self.call('/connections/'+self.profile['id'],method='DELETE',status=404)
        await self.call('/command',{'action':'connect','connection':self.profile['id']},status=404)
        self.token='owner'
        changed=await self.call('/connections/'+self.profile['id'],{**self.profile,'host':'localhost','save_password':True},method='PUT')
        self.assertFalse(changed['saved_password'])

    async def test_sql_catalog_mutation_transactions_and_errors(self):
        sid=await self.connect()
        async def query(sql,status=200):return await self.call('/command',{'action':'query','session':sid,'sql':sql},status=status)
        await query('CREATE DATABASE IF NOT EXISTS test_manager; USE test_manager; DROP TABLE IF EXISTS sample; CREATE TABLE sample (id INT PRIMARY KEY, name VARCHAR(60)); INSERT INTO sample VALUES (1,"before")')
        await query('START TRANSACTION; UPDATE sample SET name="after" WHERE id=1; ROLLBACK')
        result=await query('SELECT * FROM sample; SELECT NULL AS empty, 9007199254740993 AS big_number')
        self.assertEqual(result['results'][0]['rows'],[[1,'before']])
        self.assertEqual(len(result['results']),2)
        self.assertEqual(result['results'][1]['rows'],[[None,'9007199254740993']])
        await query('SELECT * FROM missing_table',status=400)
        self.assertEqual((await query('SELECT 42'))['results'][0]['rows'],[[42]])
        result=await self.call('/command',{'action':'browse','session':sid,'database':'test_manager','table':'sample','offset':0})
        self.assertEqual(result['results'][0]['rows'],[[1,'before']])
        self.token='other'
        await self.call('/command',{'action':'query','session':sid,'sql':'SELECT 1'},status=404)
        self.token='owner'
        await self.call('/command',{'action':'disconnect','session':sid})
        await self.call('/command',{'action':'query','session':sid,'sql':'SELECT 1'},status=404)

    async def test_limits_tls_and_local_file_loading(self):
        tls=await self.call('/connections', {**self.profile,'name':'TLS required','tls':'verify'})
        await self.call('/command', {'action':'test','connection':tls['id']},status=400)
        verified=await self.call('/connections', {**self.profile,'name':'Verified TLS','tls':'verify','ca':self.database.ca})
        await self.call('/command', {'action':'test','connection':verified['id']})
        sid=await self.connect()
        await self.call('/command',{'action':'query','session':sid,'sql':"LOAD DATA LOCAL INFILE '/etc/passwd' INTO TABLE test_manager.sample"},status=400)
        await self.call('/command',{'action':'query','session':sid,'sql':"SELECT REPEAT('x', 3000000)"},status=413)
        await self.call('/command',{'action':'query','session':sid,'sql':'SELECT 1'},status=404)
        sid=await self.connect()
        await self.call('/command',{'action':'query','session':sid,'sql':'SELECT 1; SELECT seq FROM seq_1_to_1001'},status=400)
        await self.call('/command',{'action':'query','session':sid,'sql':'CREATE DATABASE IF NOT EXISTS cap_test; USE cap_test; SELECT seq FROM seq_1_to_1001'},status=413)

    async def test_wrong_password_has_actionable_message(self):
        result=await self.call('/command',{'action':'test','connection':self.profile['id'],'password':'deliberately-wrong-test-password'},status=400)
        self.assertIn('MariaDB rejected the login',result['error'])
        self.assertNotIn('deliberately-wrong-test-password',result['error'])

    async def test_cancel_and_reconnect(self):
        sid=await self.connect()
        task=asyncio.create_task(self.call('/command',{'action':'query','session':sid,'sql':'SELECT SLEEP(20)'},status=400))
        await asyncio.sleep(.2)
        result=await self.call('/command',{'action':'cancel','session':sid})
        self.assertTrue(result['disconnected'])
        # Server can return an SQL interruption error before the HTTP task is cancelled.
        await task
        await self.connect()

    def test_identifier_quoting(self):
        self.assertEqual(identifier('a`b'),'`a``b`')
