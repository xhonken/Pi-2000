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
        result=await self.call('/command',{'action':'admin_search','session':sid,'database':'test_manager','term':'before'})
        self.assertEqual(result['results'][0]['rows'][0][0],'sample')
        result=await self.call('/command',{'action':'browse','session':sid,'database':'test_manager','table':'sample','filter':{'column':'name','operator':'contains','value':'before'},'sort':{'column':'id','direction':'DESC'}})
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

    async def test_admin_accounts_exact_database_grants_and_plan_scope(self):
        sid=await self.connect()
        async def cmd(action,**data): return await self.call('/command',{'action':action,'session':sid,**data})
        password="fixture'\\password"
        preview=await cmd('admin_preview',operation='create_user',user='managed_user',host='127.0.0.1',password=password,database='managed_data',create_database=True,charset='utf8mb4')
        self.assertNotIn(password,preview['sql']);self.assertIn('[password hidden]',preview['sql'])
        self.token='other'
        await self.call('/command',{'action':'admin_apply','session':sid,'plan':preview['plan']},status=404)
        self.token='owner'
        applied=await cmd('admin_apply',plan=preview['plan']);self.assertEqual(applied['completed'],3)
        await self.call('/command',{'action':'admin_apply','session':sid,'plan':preview['plan']},status=409)
        await cmd('query',sql='CREATE DATABASE managedXdata')
        profile=await self.call('/connections',{**self.profile,'name':'Restricted','username':'managed_user','password':password,'save_password':True,'database':'managed_data'})
        restricted=(await self.call('/command',{'action':'connect','connection':profile['id']}))['session']
        await self.call('/command',{'action':'query','session':restricted,'sql':'CREATE TABLE managed_data.ok (id INT)'})
        await self.call('/command',{'action':'query','session':restricted,'sql':'CREATE TABLE managedXdata.denied (id INT)'},status=400)
        await self.call('/command',{'action':'admin_list','session':restricted,'section':'accounts'},status=400)
        result=await cmd('admin_list',section='grants',user='managed_user',host='127.0.0.1')
        self.assertNotIn('IDENTIFIED BY PASSWORD',json.dumps(result))
        await cmd('query',sql="DROP USER 'managed_user'@'127.0.0.1'; DROP DATABASE managed_data; DROP DATABASE managedXdata")

    async def test_admin_schema_roles_and_partial_failure(self):
        sid=await self.connect()
        async def cmd(action,**data):return await self.call('/command',{'action':action,'session':sid,**data})
        async def apply(**data):
            preview=await cmd('admin_preview',**data)
            return await cmd('admin_apply',plan=preview['plan'])
        await apply(operation='create_database',database='designer')
        await apply(operation='create_table',database='designer',table='parent',columns=[{'name':'id','type':'INT','primary':True}])
        await apply(operation='create_table',database='designer',table='child',columns=[{'name':'id','type':'INT','primary':True},{'name':'parent_id','type':'INT','nullable':True}])
        await apply(operation='create_foreign_key',database='designer',table='child',constraint='fk_parent',columns=['parent_id'],reference_database='designer',reference_table='parent',reference_columns=['id'],on_delete='CASCADE')
        relations=await cmd('admin_list',section='relations',database='designer')
        self.assertEqual(relations['results'][0]['rows'][0][0],'fk_parent')
        await apply(operation='add_column',database='designer',table='parent',column={'name':"odd`column",'type':'VARCHAR','length':'30','default_mode':'value','default':"a'\\b"})
        await apply(operation='copy_table',database='designer',table='parent',new_name='copy',include_data=True)
        await apply(operation='create_role',role='designer_role')
        preview=await cmd('admin_preview',operation='create_user',user='partial_admin_test',host='localhost',password='fixture-secret',create_database=True,database='designer')
        failed=await self.call('/command',{'action':'admin_apply','session':sid,'plan':preview['plan']},status=400)
        self.assertIn('1 of 3 statements completed',failed['error']);self.assertNotIn('fixture-secret',failed['error'])
        await apply(operation='account_options',user='partial_admin_test',host='localhost',tls='SSL',lock='LOCK',expiry='NEVER',MAX_QUERIES_PER_HOUR=100)
        await apply(operation='grant',principal='role',user='designer_role',scope='database',database='designer',privileges=['SELECT'])
        await apply(operation='grant_role',role='designer_role',user='partial_admin_test',host='localhost')
        await cmd('query',sql="DROP DATABASE designer; DROP ROLE designer_role; DROP USER 'partial_admin_test'@'localhost'")

    async def test_admin_preview_does_not_execute_and_rejects_injection(self):
        sid=await self.connect()
        await self.call('/command',{'action':'admin_preview','session':sid,'operation':'create_database','database':'never_created'})
        result=await self.call('/command',{'action':'query','session':sid,'sql':"SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME='never_created'"})
        self.assertEqual(result['results'][0]['rows'],[])
        await self.call('/command',{'action':'admin_preview','session':sid,'operation':'create_database','database':'safe','charset':'utf8mb4; DROP DATABASE mysql'},status=400)
        await self.call('/command',{'action':'admin_preview','session':sid,'operation':'create_index','database':'safe','table':'t','index':'i','columns':['id'],'kind':'INDEX; DROP TABLE t'},status=400)

    async def test_database_export_restore_round_trip_and_transfer_isolation(self):
        sid=await self.connect()
        async def query(sql):return await self.call('/command',{'action':'query','session':sid,'sql':sql})
        await query('CREATE DATABASE transfer_test; USE transfer_test; CREATE TABLE items (id INT PRIMARY KEY, value VARCHAR(90), computed INT AS (id+1), bytes BLOB); INSERT INTO items (id,value,bytes) SELECT seq, CONCAT("row",seq), X\'0001FF\' FROM seq_1_to_1200')
        await query('CREATE FUNCTION transfer_test.add_one(value INT) RETURNS INT DETERMINISTIC NO SQL RETURN value+1')
        await query('CREATE VIEW transfer_test.first_view AS SELECT id, transfer_test.add_one(id) AS next_id FROM transfer_test.items; CREATE VIEW transfer_test.second_view AS SELECT * FROM transfer_test.first_view')
        await query('CREATE PROCEDURE transfer_test.count_items() BEGIN SELECT COUNT(*) FROM transfer_test.items; END')
        await query('CREATE TRIGGER transfer_test.keep_value BEFORE INSERT ON transfer_test.items FOR EACH ROW SET NEW.value=COALESCE(NEW.value,"default")')
        async def transfer(data,status=200):return await self.call('/transfer',data,status=status)
        async def finish(job):
            for _ in range(200):
                result=await transfer({'action':'status','job':job})
                if result['state']!='running':self.assertEqual(result['state'],'complete',result);return result
                await asyncio.sleep(.02)
            self.fail('Transfer timed out')
        job=(await transfer({'action':'export','session':sid,'database':'transfer_test'}))['job']
        self.token='other';await transfer({'action':'status','job':job},404);self.token='owner'
        result=await finish(job);self.assertEqual(result['rows'],1200)
        import base64
        offset=0;parts=[]
        while True:
            chunk=await transfer({'action':'read','job':job,'offset':offset});parts.append(base64.b64decode(chunk['data']));offset=chunk['offset']
            if chunk['done']:break
        sql=b''.join(parts).decode();self.assertIn('DELIMITER',sql);self.assertIn('completed successfully',sql)
        await transfer({'action':'close','job':job})
        await query('DROP DATABASE transfer_test; CREATE DATABASE transfer_test')
        job=(await transfer({'action':'restore','session':sid,'database':'transfer_test','sql':sql}))['job']
        await finish(job)
        result=await query('SELECT COUNT(*),SUM(computed),HEX(MAX(bytes)) FROM transfer_test.items; CALL transfer_test.count_items()')
        self.assertEqual(result['results'][0]['rows'],[[1200,'721800','0001FF']])
        self.assertEqual(result['results'][1]['rows'],[[1200]])
        self.assertEqual((await query('SELECT next_id FROM transfer_test.second_view WHERE id=1200'))['results'][0]['rows'],[[1201]])
        await query('DROP DATABASE transfer_test')
        await transfer({'action':'close','job':job})

    def test_sql_import_delimiters_quotes_comments_and_malformed_input(self):
        from database_transfer import statements
        sql="-- comment\nDELIMITER $$\nCREATE PROCEDURE p() BEGIN SELECT 'a;$$'; SELECT 2; END$$\nDELIMITER ;\nINSERT INTO t VALUES ('it\\\'s;fine'); # trailing\nSELECT 3;"
        result=list(statements(sql));self.assertEqual(len(result),3);self.assertIn('END',result[0]);self.assertIn('SELECT 3',result[2])
        with self.assertRaises(ValueError):list(statements("SELECT 'unclosed"))
