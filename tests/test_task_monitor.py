import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import test_server
import app
from task_monitor import TaskMonitor

class MonitorMath(unittest.TestCase):
    def test_cpu_excludes_guest_double_count_and_first_sample(self):
        self.assertIsNone(TaskMonitor.cpu_percent(None,[0]*10))
        self.assertEqual(TaskMonitor.cpu_percent([100,0,50,800,50,0,0,0,0,0],[140,0,60,840,60,0,0,0,40,0]),50)
        self.assertIsNone(TaskMonitor.cpu_percent([0]*10,[0]*10))

    def test_real_proc_sampling_and_safe_fields(self):
        with tempfile.TemporaryDirectory() as root:
            monitor=TaskMonitor(SimpleNamespace(STATE=Path(root)))
            first=monitor.sample();self.assertIsNone(first['cpu']['percent']);self.assertGreater(first['memory']['total'],0)
            second=monitor.sample();self.assertGreater(second['process_count'],0)
            self.assertTrue(all('cmdline' not in p and 'environ' not in p for p in second['processes']))
            disk=second['disk'];self.assertEqual(disk['used']+disk['free']+disk['reserved'],disk['total'])

class MonitorPrivacy(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=test_server.ServerTests.asyncSetUp
    asyncTearDown=test_server.ServerTests.asyncTearDown
    create_account=test_server.ServerTests.create_account
    login_account=test_server.ServerTests.login_account

    async def test_private_processes_quota_and_owner_only_server_view(self):
        await self.create_account();alice=await self.login_account()
        with app.db() as db:uid=db.execute("SELECT id FROM users WHERE username='alice'").fetchone()[0]
        monitor=next(route.handler.__self__ for route in self.client.server.app.router.routes() if route.resource.canonical=='/api/taskmanager')
        snapshot=monitor.sample()
        snapshot['processes']=[{'pid':101,'name':'own-browser','user_id':uid,'_ticks':9,'_start':1},{'pid':102,'name':'another-browser','user_id':1,'_ticks':1,'_start':1},{'pid':103,'name':'shared-service','user_id':None,'_ticks':1,'_start':1}]
        with patch.object(monitor,'sample',return_value=snapshot):
            monitor.cached=None
            r=await self.client.get('/api/taskmanager',headers=alice);self.assertEqual(r.status,200);data=await r.json()
            self.assertEqual(data['processes'],[{'pid':101,'name':'own-browser'}]);self.assertFalse(data['can_view_server']);self.assertEqual(data['storage']['quota'],50*1024**2)
            r=await self.client.get('/api/taskmanager?scope=server',headers=alice);self.assertEqual(r.status,403)
            r=await self.client.get('/api/taskmanager?scope=server',headers=self.headers);self.assertEqual(r.status,200);self.assertEqual(len((await r.json())['processes']),3)
            r=await self.client.post('/api/files/upload?name=private.txt',headers=alice,data=b'1234567');key=(await r.json())['id']
            await self.client.post('/api/files/'+key+'/trash',headers=alice,json={})
            data=await (await self.client.get('/api/taskmanager',headers=alice)).json();self.assertEqual(data['storage']['used'],7);self.assertEqual(data['storage']['trash'],7)
            own=await (await self.client.get('/api/taskmanager',headers=self.headers)).json();self.assertEqual(own['storage']['used'],0)
        self.assertEqual((await self.client.get('/api/taskmanager')).status,401)
