"""Namespace changes rehearsed on disposable trees; never stop real services."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
import system_migration as m
from deployment import digest,verify

ROOT=Path(__file__).resolve().parents[1]

class FakeHost(m.Host):
    def __init__(self,root):
        super().__init__(root);self.users={'win2k-admin':(987,987,'/var/lib/win2k-admin')};self.groups={'win2k-admin':987}
        self.active_units=set(m.UNITS);self.enabled_units=set(m.UNITS);self.commands=[];self.fail=False
    def account(self,name):return self.users.get(name)
    def group(self,name):return self.groups.get(name)
    def active(self,unit):return unit in self.active_units
    def enabled(self,unit):return unit in self.enabled_units
    def rename_account(self,reverse=False):
        old,new=('pi2000-admin','win2k-admin') if reverse else ('win2k-admin','pi2000-admin')
        if old in self.groups:self.groups[new]=self.groups.pop(old)
        if old in self.users:
            uid,gid,_=self.users.pop(old);self.users[new]=(uid,gid,'/var/lib/'+new)
    def run(self,*args):
        self.commands.append(args)
        if args[:2]==('systemctl','start'):
            if self.fail and args[2]=='pi2000-admin.service':self.fail=False;raise RuntimeError('injected startup failure')
            if args[2]!='win2k-backup.service':self.active_units.add(args[2])
        elif args[:2]==('systemctl','stop'):self.active_units.discard(args[2])
        elif args[:2]==('systemctl','enable'):self.enabled_units.add(args[2])
        elif args[:2]==('systemctl','disable'):self.enabled_units.discard(args[2])
        return ''
    def verify_live(self,source):
        verify(self.path('/opt/pi2000-admin'),'server');verify(self.path('/srv/pi2000'),'web')
        assert self.active_units=={m.renamed(u) for u in m.UNITS}
        assert not any('win2k' in u for u in self.active_units)


class MigrationTests(unittest.TestCase):
    def test_readiness_waits_for_http_auth_boundary(self):
        from urllib.error import HTTPError, URLError
        responses=[URLError('starting'),HTTPError('local',503,'starting',{},None),HTTPError('local',401,'unauthorized',{},None)]
        with patch.object(m,'urlopen',side_effect=responses) as request, patch.object(m.time,'sleep'):
            m.Host().wait_ready()
        self.assertEqual(request.call_count,3)

    def test_readiness_has_bounded_failure(self):
        with patch.object(m.time,'monotonic',side_effect=[0,0,61]), patch.object(m.time,'sleep'), patch.object(m,'urlopen',side_effect=m.URLError('starting')):
            with self.assertRaisesRegex(RuntimeError,'startup deadline'):m.Host().wait_ready()

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.host=FakeHost(self.temp.name);h=self.host
        for old in m.PATHS:h.path(old).mkdir(parents=True)
        for component,path in [('server','/opt/win2k-admin'),('web','/srv/win2k')]:
            p=h.path(path);f=p/'old.txt';f.write_text(component+' before')
            (p/('deployment-'+component+'.json')).write_text(json.dumps({'format':1,'component':component,'build':{},'files':{'old.txt':digest(f)}}))
            if component=='server':(p/'build-info.json').write_text('{}')
        p=h.path('/opt/win2k-admin/venv/bin/python');p.parent.mkdir(parents=True);p.write_text('keep runtime')
        p=h.path('/var/lib/win2k-admin/admin.sqlite3');p.write_bytes(b'private fixture, no schema migration');p.chmod(0o600);self.data_stat=p.stat()
        unitdir=h.path('/etc/systemd/system');unitdir.mkdir(parents=True)
        for unit in set(m.UNITS)|set(m.OLD_UNITS):
            (unitdir/unit).write_text('[Service]\nUser=win2k-admin\n')
        config={'network':{'public_url':'https://192.0.2.25','bind_address':'','tls':'internal'},'features':{'browser':True}}
        import runpy
        setup=runpy.run_path(str(ROOT/'scripts/setup.py'));caddy=setup['render'](config)['Caddyfile']
        for old,new in reversed(list(m.RENAMES.items())):caddy=caddy.replace(new,old)
        p=h.path('/etc/caddy/Caddyfile');p.parent.mkdir(parents=True);p.write_text(caddy)
        p=h.path('/etc/pi2000web/runtime.env');p.parent.mkdir(parents=True);p.write_text('WIN2K_ORIGIN=https://192.0.2.25\n')
        self.migration=m.Migration(ROOT,h)
    def test_read_only_plan(self):
        plan=self.migration.plan();self.assertEqual(plan['state'],'ready');self.assertEqual(plan['service_uid'],987);self.assertEqual(self.host.commands,[])
    def test_move_preserves_data_numeric_ownership_and_legacy_paths(self):
        result=self.migration.apply();self.assertEqual(result['state'],'complete')
        p=self.host.path('/var/lib/pi2000-admin/admin.sqlite3');self.assertEqual(p.read_bytes(),b'private fixture, no schema migration')
        self.assertEqual((p.stat().st_ino,p.stat().st_uid,p.stat().st_gid,p.stat().st_mode),(self.data_stat.st_ino,self.data_stat.st_uid,self.data_stat.st_gid,self.data_stat.st_mode))
        self.assertEqual(self.host.path('/var/lib/win2k-admin/admin.sqlite3').read_bytes(),p.read_bytes())
        self.assertEqual(self.host.account('pi2000-admin')[:2],(987,987));self.assertIsNone(self.host.account('win2k-admin'))
        self.assertEqual(self.migration.plan()['state'],'already migrated')
        self.assertEqual(self.host.path('/opt/pi2000-admin/venv/bin/python').read_text(),'keep runtime')
        self.assertNotIn('win2k',self.host.path('/etc/caddy/Caddyfile').read_text())
        self.assertTrue(all(not self.host.path('/etc/systemd/system/'+u).exists() for u in m.OLD_UNITS))
        self.assertEqual(self.host.enabled_units,{m.renamed(u) for u in m.UNITS})
    def test_failed_start_rolls_back_without_restoring_or_erasing_user_database(self):
        self.host.fail=True
        with self.assertRaisesRegex(RuntimeError,'previous code'):self.migration.apply()
        self.assertEqual(self.host.active_units,set(m.UNITS));self.assertEqual(self.host.enabled_units,set(m.UNITS))
        self.assertEqual(self.host.account('win2k-admin')[:2],(987,987));self.assertIsNone(self.host.account('pi2000-admin'))
        self.assertEqual(self.host.path('/opt/win2k-admin/old.txt').read_text(),'server before')
        self.assertEqual(self.host.path('/srv/win2k/old.txt').read_text(),'web before')
        self.assertEqual(self.host.path('/var/lib/win2k-admin/admin.sqlite3').stat().st_ino,self.data_stat.st_ino)
        self.assertEqual(json.loads((self.migration.backup/'migration.json').read_text())['state'],'rolled back')
    def test_conflicts_overrides_and_packaged_installations_fail_before_mutation(self):
        for name in ('/var/lib/pi2000-admin','/etc/systemd/system/win2k-sessions.service.d','/var/lib/pi2000web/package-managed'):
            p=self.host.path(name);p.mkdir(parents=True)
            with self.assertRaises(RuntimeError):self.migration.plan()
            p.rmdir()
        self.assertEqual(self.host.commands,[])
    def test_last_minute_busy_check_happens_before_any_stop(self):
        def changed():raise RuntimeError('became busy')
        with self.assertRaisesRegex(RuntimeError,'became busy'):self.migration.apply(changed)
        self.assertFalse(any(c[:2]==('systemctl','stop') for c in self.host.commands))
        self.assertIsNotNone(self.host.account('win2k-admin'))
    def test_kernel_process_names_in_child_only(self):
        code="from process_identity import identify; from pathlib import Path; identify('pi2000-api'); print(Path('/proc/self/comm').read_text().strip())"
        self.assertEqual(subprocess.check_output([sys.executable,'-c',code],env={**os.environ,'PYTHONPATH':str(ROOT/'server')},text=True).strip(),'pi2000-api')


class LeaseTests(unittest.IsolatedAsyncioTestCase):
    async def test_busy_worker_is_resumed_and_not_stopped(self):
        calls=[]
        async def control(socket,action,**kwargs):
            calls.append((socket,action));return {'runtime':{'protocol':1,'draining':True,'busy':True}}
        with patch.object(m,'control',control):
            with self.assertRaisesRegex(RuntimeError,'Live jobs'):
                async with m.workers():self.fail('must not apply')
        self.assertIn((m.SOCKETS[0],'resume'),calls)
    async def test_second_check_catches_new_work_and_releases_both_leases(self):
        draining=0;calls=[]
        async def control(socket,action,**kwargs):
            nonlocal draining
            calls.append((socket,action))
            if action=='drain':draining+=1
            return {'runtime':{'protocol':1,'draining':True,'busy':draining>2}}
        with patch.object(m,'control',control):
            with self.assertRaisesRegex(RuntimeError,'state changed'):
                async with m.workers() as check:await check()
        for socket in m.SOCKETS:self.assertIn((socket,'resume'),calls)
