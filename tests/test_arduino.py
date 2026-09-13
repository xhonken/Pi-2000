import asyncio
import json
import os
from pathlib import Path
import pty
import sys
import tempfile
import unittest
from unittest.mock import patch
from aiohttp.test_utils import TestClient, TestServer
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'server'))
import app
import arduino_workshop as ar


class ArduinoTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();app.STATE=Path(self.temp.name);app.SESSIONS={};app.WORKER_SOCKET='';app.WORKER_MODE=False
        self.cli=patch.object(ar,'CLI',Path('/usr/bin/true'));self.cli.start()
        self.socket=patch.object(ar,'SOCKET','');self.socket.start()
        application=app.make_app()
        self.worker=next(route.handler.__self__ for route in application.router.routes() if route.resource.canonical=='/api/development/arduino')
        self.client=TestClient(TestServer(application));await self.client.start_server()
        with app.db() as db:db.execute("INSERT INTO users(username,salt,hash) VALUES('other','s','h')")
        app.SESSIONS['owner']={'user_id':1,'version':1,'expires':9999999999};app.SESSIONS['other']={'user_id':2,'version':1,'expires':9999999999};self.token='owner'
    async def asyncTearDown(self):
        await self.client.close();self.cli.stop();self.socket.stop();self.temp.cleanup()
    async def call(self,action,status=200,**data):
        response=await self.client.post('/api/development/arduino',json={'action':action,**data},headers={'Origin':app.ORIGIN,'Cookie':app.COOKIE+'='+self.token})
        result=await response.json();self.assertEqual(response.status,status,result);return result
    async def project(self):
        result=await self.call('create',name='PrivateSketch',template='serial',fqbn='esp32:esp32:esp32')
        return await self.call('open',project=result['id'])
    async def wait_job(self):
        await asyncio.wait_for(self.worker.jobs[1]['task'],3)
        return (await self.call('status'))['job']
    async def test_project_ownership_revision_validation_and_roundtrip(self):
        p=await self.project();files={**p['files'],'display.h':'// display header\n'}
        saved=await self.call('save',project=p['id'],revision=1,name=p['name'],files=files,fqbn=p['fqbn'])
        self.assertEqual(saved['revision'],2)
        self.assertEqual((await self.call('open',project=p['id']))['files'],files)
        await self.call('save',status=409,project=p['id'],revision=1,name=p['name'],files=files,fqbn=p['fqbn'])
        await self.call('delete',status=409,project=p['id'],revision=1)
        self.token='other';self.assertEqual((await self.call('status'))['projects'],[])
        for action in ('open','delete','compile','save'):
            await self.call(action,status=404,project=p['id'],revision=2,name=p['name'],files=files,fqbn=p['fqbn'])
        self.token='owner'
        for name in ('../escape','/etc/passwd','bad name'):
            await self.call('create',status=400,name=name)
        for filename in ('../escape.h','/etc/passwd','build_opt.h/escape','platform.local.txt/escape'):
            await self.call('save',status=400,project=p['id'],revision=2,name=p['name'],files={**files,filename:'bad'})
        await self.call('delete',project=p['id'],revision=2)
        self.assertEqual((await self.call('status'))['projects'],[])
        with app.db() as db:
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])
    async def test_usb_authorization_port_validation_and_injection(self):
        self.token='other';p=await self.project()
        for action in ('ports','monitor_open','monitor_poll','monitor_send','upload'):
            await self.call(action,status=403,project=p['id'],revision=1,port='/dev/ttyACM0')
        self.token='owner'
        for port in ('/dev/mem','/etc/passwd','/dev/ttyAMA0','--port=x'):
            await self.call('monitor_open',status=400,port=port)
        for package in ('--git-url=https://evil','thing@1.0;command','../x'):
            await self.call('lib_install',status=400,package=package)
        await self.call('core_install',status=400,package='evil:platform')
        await self.call('library_search',status=400,query='--config-file=/etc/passwd')
        await self.call('board_details',status=400,fqbn='esp32:esp32:esp32;command')
    async def test_jobs_snapshot_errors_cancel_and_owner_scope(self):
        p=await self.project();calls=[]
        async def execute(uid,args,token,**kw):
            calls.append((args,kw))
            if args[0]=='compile':
                source=kw['work']/'sketch'/p['name']/(p['name']+'.ino')
                self.assertEqual(source.read_text(),p['files'][p['name']+'.ino'])
            kw['job']['output']+='verified output\n';return ''
        self.worker.execute=execute
        await self.call('compile',project=p['id'],revision=1)
        job=await self.wait_job();self.assertEqual(job['state'],'succeeded');self.assertIn('verified output',job['output'])
        self.token='other';self.assertIsNone((await self.call('status'))['job']);await self.call('cancel',status=404,job=job['id']);self.token='owner'
        async def slow(*args,**kwargs):await asyncio.sleep(100)
        self.worker.execute=slow
        await self.call('compile',project=p['id'],revision=1)
        await self.call('lib_install',status=409,package='ArduinoJson')
        await self.call('cancel',job=self.worker.jobs[1]['id'])
        self.assertEqual((await self.call('status'))['job']['state'],'cancelled');self.assertFalse(self.worker.busy)
        async def failure(*args,**kwargs):raise RuntimeError('fixture compile error')
        self.worker.execute=failure;await self.call('compile',project=p['id'],revision=1)
        self.assertEqual((await self.wait_job())['state'],'failed');self.assertFalse(self.worker.busy)
    async def test_upload_follows_successful_compile_and_closes_own_monitor(self):
        p=await self.project();calls=[]
        async def execute(uid,args,token,**kw):calls.append(args);return ''
        self.worker.execute=execute;self.worker.port=lambda x:'/dev/ttyUSB0';self.worker.port_identity=lambda x:(1,2,3)
        await self.call('upload',project=p['id'],revision=1,port='/dev/ttyUSB0')
        self.assertEqual((await self.wait_job())['state'],'succeeded');self.assertEqual([c[0] for c in calls],['compile','upload'])
        self.assertIn('/build',calls[-1])
        async def failure(*args,**kwargs):calls.append(args[1]);raise RuntimeError('compile failed')
        calls.clear();self.worker.execute=failure
        await self.call('upload',project=p['id'],revision=1,port='/dev/ttyUSB0')
        self.assertEqual((await self.wait_job())['state'],'failed');self.assertEqual(len(calls),1)
    async def test_real_serial_pty_output_input_exclusivity_and_revocation(self):
        master,slave=pty.openpty();path=os.ttyname(slave);os.set_blocking(master,False)
        self.worker.port=lambda x:path
        try:
            await self.call('monitor_open',port=path,baud=115200)
            os.write(master,b'ESP32 fixture hello\n');await asyncio.sleep(.1)
            self.assertIn('ESP32 fixture hello',(await self.call('monitor_poll'))['output'])
            await self.call('monitor_send',text='ping',ending='\r\n')
            self.assertEqual(os.read(master,100),b'ping\r\n')
            with app.db() as db:db.execute("UPDATE users SET role='admin' WHERE id=2")
            self.token='other';await self.call('monitor_open',status=409,port=path,baud=115200)
            self.token='owner';await self.call('monitor_clear');self.assertEqual((await self.call('monitor_poll'))['output'],'')
            with app.db() as db:db.execute('UPDATE users SET version=version+1 WHERE id=1')
            await asyncio.sleep(.1);self.assertEqual(self.worker.monitors[1]['state'],'closed')
        finally:os.close(master);os.close(slave)
    async def test_cache_cleanup_preserves_installed_packages_and_projects(self):
        p=await self.project();root=self.worker.runtime(1)
        (root/'data'/'keep').write_text('installed platform')
        (root/'user'/'keep').write_text('installed library')
        (root/'downloads'/'old').write_text('cached download')
        (root/'cache'/'old').write_text('cached build')
        await self.call('clean_cache')
        self.assertEqual((await self.wait_job())['state'],'succeeded')
        self.assertFalse((root/'downloads'/'old').exists());self.assertFalse((root/'cache'/'old').exists())
        self.assertTrue((root/'data'/'keep').exists());self.assertTrue((root/'user'/'keep').exists())
        self.assertEqual((await self.call('open',project=p['id']))['name'],p['name'])

    async def test_persisted_job_restart_and_account_cascade(self):
        await self.project()
        job={'id':'interrupted-fixture','action':'compile','state':'running','output':'Building...', 'started':1,'project':None}
        self.worker.persist_job(1,job)
        replacement=ar.ArduinoWorkshop(app);replacement.initialize()
        restored=replacement.job_view(1)
        self.assertEqual(restored['state'],'interrupted');self.assertIn('restarted',restored['output'])
        self.assertIsNone(replacement.job_view(2))
        # Use an ordinary disposable account for actual cascade deletion.
        replacement.persist_job(2,{**job,'state':'succeeded'})
        with app.db() as db:db.execute('DELETE FROM users WHERE id=2')
        self.assertIsNone(replacement.job_view(2))

    async def test_running_process_is_killed_when_login_revoked(self):
        self.worker.command=lambda *a,**kw: (['/usr/bin/python3','-c','import time;time.sleep(30)'],{'PATH':'/usr/bin:/bin'})
        task=asyncio.create_task(self.worker.execute(1,[], 'owner',timeout=5))
        await asyncio.sleep(.1);app.SESSIONS.pop('owner')
        with self.assertRaisesRegex(RuntimeError,'login or account'):
            await asyncio.wait_for(task,3)

    async def test_real_sandbox_blocks_platform_and_other_users(self):
        # Exercise the actual bwrap mount layout, replacing only the CLI command.
        root=self.worker.runtime(1);self.worker.runtime(2)
        cmd,env=self.worker.command(1,['version'])
        cut=cmd.index('--',cmd.index('/usr/bin/bwrap'))
        cmd=cmd[:cut+1]+['/usr/bin/python3','-c',"from pathlib import Path; assert not Path('/home').exists(); assert not Path('/opt/win2k-admin').exists(); assert not Path('/var/lib/win2k-admin').exists(); assert not Path('/dev/ttyUSB0').exists(); Path('/arduino/probe').write_text('private')"]
        proc=await asyncio.create_subprocess_exec(*cmd,env=env,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        out,err=await proc.communicate();self.assertEqual(proc.returncode,0,err);self.assertEqual((root/'probe').read_text(),'private')
        self.assertFalse((self.worker.root/'2'/'probe').exists())

if __name__=='__main__':unittest.main()
