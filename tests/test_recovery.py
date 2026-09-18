from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
from recovery import Host, make_plan, apply_plan, replace_shadow

from installation import APPLICATION_ID, BACKUP_FORMAT

class FakeHost(Host):
    def __init__(self,root):
        self.root=root;self.users={'pi2000-admin':{'name':'pi2000-admin','uid':os.getuid(),'gid':os.getgid(),'home':'/var/lib/pi2000-admin','shell':'/usr/sbin/nologin','groups':[]}}
        self.groups={'pi2000-users':900,'pi2000-terminal':901};self.calls=[];self.busy=False;self.fail=False
        p=self.path('/etc/shadow');p.parent.mkdir(parents=True);p.write_text('unrelated:!:1:0:99999:7:::\n')
    def user(self,name):return dict(self.users[name]) if name in self.users else None
    def uid(self,uid):return next((n for n,u in self.users.items() if u['uid']==uid),None)
    def group(self,name):return self.groups.get(name)
    def gid(self,gid):return next((n for n,g in self.groups.items() if g==gid),None)
    def stopped(self):
        if self.busy:raise RuntimeError('services still active')
    def idle_users(self,names):pass
    def set_shadow(self,records):
        if self.fail:self.fail=False;raise RuntimeError('injected OS failure')
        self.path('/etc/shadow').write_text(replace_shadow(self.shadow(),records))
    def run(self,*args):
        self.calls.append(args);command=args[0]
        if command=='groupadd':self.groups[args[-1]]=int(args[args.index('--gid')+1])
        elif command=='useradd':
            n=args[-1];self.users[n]={'name':n,'uid':int(args[args.index('--uid')+1]),'gid':int(args[args.index('--gid')+1]),'home':args[args.index('--home-dir')+1],'shell':'/usr/sbin/nologin','groups':['pi2000-users']}
            with self.path('/etc/shadow').open('a') as f:f.write(n+':!:1:0:99999:7:::\n')
        elif command=='usermod':self.users[args[-1]]['shell']=args[args.index('--shell')+1]
        elif command=='gpasswd':
            groups=self.users[args[2]]['groups']
            if args[1]=='-a':groups.append(args[3])
            else:groups.remove(args[3])
        elif command=='userdel':self.users.pop(args[-1]);self.path('/etc/shadow').write_text(''.join(l+'\n' for l in self.shadow().splitlines() if l.split(':')[0]!=args[-1]))
        elif command=='groupdel':self.groups.pop(args[-1])

class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.stage=self.root/'stage';self.stage.mkdir();self.host=FakeHost(self.root/'host')
        state=self.stage/'state';state.mkdir()
        with closing(sqlite3.connect(state/'admin.sqlite3')) as db:
            db.execute(f'PRAGMA application_id={APPLICATION_ID}')
            db.executescript("CREATE TABLE users(id INTEGER PRIMARY KEY, role TEXT, active INTEGER); INSERT INTO users VALUES(1,'admin',1);")
        account=self.stage/'system-accounts';account.mkdir()
        with closing(sqlite3.connect(account/'accounts.sqlite3')) as db:
            db.executescript("CREATE TABLE bindings(web_id INTEGER PRIMARY KEY,name TEXT,uid INTEGER,home TEXT,managed INTEGER,creator INTEGER,phase TEXT,fingerprint TEXT); INSERT INTO bindings VALUES(1,'pi2k_1',21001,'/home/pi2k_1',1,1,'ready','fixture');")
        (account/'generation.key').write_text('fixture-only')
        (account/'shadow').write_text('pi2k_1:!:123:0:99999:7:::\n')
        (account/'identities.json').write_text(json.dumps([{'name':'pi2k_1','uid':21001,'gid':21001,'group':'pi2k_1'}]))
        home=account/'homes/pi2k_1';home.mkdir(parents=True);(home/'run.sh').write_text('#!/bin/sh\necho fixture\n')
        self.manifest={'format':BACKUP_FORMAT,'created':'fixture','metadata':{'system-accounts/homes/pi2k_1':{'uid':21001,'gid':21001,'mode':0o700},'system-accounts/homes/pi2k_1/run.sh':{'uid':21001,'gid':21001,'mode':0o750}}}
        live=self.host.path('/var/lib/pi2000-admin');live.mkdir(parents=True);(live/'old.txt').write_text('keep on rollback')
        self.chown=patch('recovery.os.chown');self.chown.start();self.addCleanup(self.chown.stop)
    def plan(self):return make_plan(self.stage,self.manifest,self.host,'fixture-digest')
    def test_create_identity_restore_home_modes_and_preserve_unrelated_accounts(self):
        plan=self.plan();self.assertEqual(plan['blockers'],[])
        backup=apply_plan(self.stage,self.manifest,plan,self.host)
        self.assertEqual(self.host.user('pi2k_1')['uid'],21001)
        self.assertEqual(self.host.user('pi2k_1')['shell'],'/bin/bash')
        self.assertEqual(self.host.path('/home/pi2k_1/run.sh').stat().st_mode&0o777,0o750)
        self.assertEqual((backup/'0/old.txt').read_text(),'keep on rollback')
        self.assertIn('unrelated:!:1:',self.host.shadow())
        self.assertIn('replace-intent',(backup/'journal.jsonl').read_text())
        self.assertEqual((backup/'previous-passwords.json').stat().st_mode&0o777,0o600)
        self.assertNotIn('fixture-only',json.dumps(plan))
        self.assertNotIn('pi2k_1:!',json.dumps(plan))
    def test_uid_conflict_and_foreign_home_owner_block(self):
        self.host.users['other']={'name':'other','uid':21001,'gid':21002,'home':'/home/other','shell':'/bin/bash','groups':[]}
        self.assertTrue(any('occupied' in v for v in self.plan()['blockers']))
        self.manifest['metadata']['system-accounts/homes/pi2k_1/run.sh']['uid']=21002
        self.assertTrue(any('ownership' in v for v in self.plan()['blockers']))
    def test_failure_rolls_back_state_homes_and_created_identity(self):
        self.host.fail=True
        with self.assertRaisesRegex(RuntimeError,'injected'):apply_plan(self.stage,self.manifest,self.plan(),self.host)
        self.assertEqual(self.host.path('/var/lib/pi2000-admin/old.txt').read_text(),'keep on rollback')
        self.assertIsNone(self.host.user('pi2k_1'));self.assertFalse(self.host.path('/home/pi2k_1').exists())
    def test_active_services_and_changed_target_refuse_before_modification(self):
        plan=self.plan();self.host.busy=True
        with self.assertRaisesRegex(RuntimeError,'active'):apply_plan(self.stage,self.manifest,plan,self.host)
        self.host.busy=False;self.host.groups['pi2k_1']=21002
        with self.assertRaisesRegex(RuntimeError,'changed'):apply_plan(self.stage,self.manifest,plan,self.host)
        self.assertEqual(self.host.calls,[])
    def test_linked_accounts_are_never_modified(self):
        with closing(sqlite3.connect(self.stage/'state/admin.sqlite3')) as db:
            db.execute("INSERT INTO users VALUES(2,'admin',1)");db.commit()
        with closing(sqlite3.connect(self.stage/'system-accounts/accounts.sqlite3')) as db:
            db.execute("INSERT INTO bindings VALUES(2,'linked',22001,'/home/linked',0,0,'ready','fixture')");db.commit()
        self.host.users['linked']={'name':'linked','uid':22001,'gid':22001,'home':'/home/linked','shell':'/bin/bash','groups':['sudo']}
        before=self.host.user('linked');apply_plan(self.stage,self.manifest,self.plan(),self.host)
        self.assertEqual(self.host.user('linked'),before)
        self.assertFalse(any('linked' in call for call in self.host.calls))

    def test_missing_metadata_and_shadow_block_recovery(self):
        del self.manifest['metadata']['system-accounts/homes/pi2k_1/run.sh']
        (self.stage/'system-accounts/shadow').unlink()
        blockers=self.plan()['blockers']
        self.assertTrue(any('Missing home ownership' in b for b in blockers))
        self.assertTrue(any('password recovery records' in b for b in blockers))

    def test_modified_plan_cannot_bypass_account_validation(self):
        plan=self.plan();plan['accounts'][0]['uid']=1
        with self.assertRaisesRegex(RuntimeError,'plan modified'):
            apply_plan(self.stage,self.manifest,plan,self.host)
        self.assertEqual(self.host.calls,[])

    def test_unknown_systemd_state_fails_closed(self):
        import subprocess
        host=Host()
        with patch('recovery.subprocess.run',return_value=subprocess.CompletedProcess([],1,'','unavailable')):
            with self.assertRaisesRegex(RuntimeError,'systemd state'):host.stopped()
