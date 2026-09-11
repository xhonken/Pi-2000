#!/usr/bin/env python3
"""Explicit root-only integration test; never part of automatic unit discovery.
Uses a temporary web DB/registry and reserved disposable IDs above 900000.
Requires installed pi2000 PAM policy, groups and private terminal listener.
"""
import asyncio
import json
import os
from pathlib import Path
import pwd
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
import app
import account_service as b
import pam_auth
import asyncssh
from session_store import SessionStore

async def ssh(name,secret,port=2222):
    async with asyncssh.connect('127.0.0.1',port=port,username=name,password=secret,known_hosts=None) as conn:
        result=await conn.run('id -un; printf "%s\\n" "$HOME"; sudo -n true',check=False)
        assert result.stdout.splitlines()[:2]==[name,'/home/'+name],result.stdout
        assert result.exit_status!=0,'Unexpected sudo access'

if os.geteuid()!=0: raise SystemExit('Run explicitly as root.')
created=[]
try:
 with tempfile.TemporaryDirectory() as folder:
    app.STATE=Path(folder)/'web'; b.STATE=app.STATE; b.ROOT=Path(folder)/'registry'
    app.initialize(initial_password='fixture-creator-password')
    with app.db() as db:
        db.execute('DROP TRIGGER protect_admin_update')
        db.execute('UPDATE users SET id=900001 WHERE is_creator=1')
    app.initialize(); b.setup_registry()
    owner=b.user(900001);b.reserve(owner); created.append('pi2k_900001')
    b.authenticate(owner,'fixture-creator-password')
    assert pam_auth.check('pi2k_900001','fixture-creator-password')
    token=secrets.token_urlsafe(32); store=SessionStore(app.STATE/'admin.sqlite3')
    store[token]={'expires':time.time()+3600,'user_id':900001,'version':b.user(900001)['version']}
    users=[]
    for i in range(5):
        secret=secrets.token_urlsafe(24)
        result=b.dispatch({'operation':'create','token':token,'username':'fixture'+str(i),'password':secret})
        uid=result['id']; users.append(uid); managed=b.binding(uid);created.append(managed['name'])
        assert pam_auth.check(managed['name'],secret)
        assert pwd.getpwnam(managed['name']).pw_shell.endswith('nologin')
        assert Path(managed['home']).stat().st_mode&0o777==0o700
        try: asyncio.run(ssh(managed['name'],secret))
        except asyncssh.PermissionDenied: pass
        else: raise AssertionError('Ordinary user opened local terminal')
        b.dispatch({'operation':'update','token':token,'user_id':uid,'changes':{'role':'admin'}})
        asyncio.run(ssh(managed['name'],secret))
        try: asyncio.run(ssh(managed['name'],secret,22))
        except asyncssh.PermissionDenied: pass
        else: raise AssertionError('Managed user opened host SSH')
    assert len({b.binding(uid)['uid'] for uid in users})==5
    uid=users[0]; managed=b.binding(uid)
    b.dispatch({'operation':'update','token':token,'user_id':uid,'changes':{'active':False}})
    assert not pam_auth.check(managed['name'],'wrong-password')
    reset=secrets.token_urlsafe(24)
    b.dispatch({'operation':'reset','token':token,'user_id':uid,'password':reset})
    assert not pam_auth.check(managed['name'],reset),'Disabled PAM account accepted'
    b.dispatch({'operation':'update','token':token,'user_id':uid,'changes':{'active':True}})
    assert pam_auth.check(managed['name'],reset)
    own_token=secrets.token_urlsafe(32);store[own_token]={'expires':time.time()+3600,'user_id':uid,'version':b.user(uid)['version']}
    replacement=secrets.token_urlsafe(24)
    b.dispatch({'operation':'change_password','token':own_token,'current':reset,'password':replacement})
    assert not pam_auth.check(managed['name'],reset)
    assert pam_auth.check(managed['name'],replacement)
    assert not app.session_valid(store[own_token])
    before=b.fingerprint(managed)
    subprocess.run(['chpasswd'],input=(managed['name']+':'+secrets.token_urlsafe(24)+'\n').encode(),check=True)
    assert b.fingerprint(managed)!=before
    for op in ('delete','update','reset'):
        try:b.dispatch({'operation':op,'token':token,'user_id':900001,'confirm':'admin','changes':{'active':False},'password':replacement})
        except b.Denied as exc: assert exc.status==403
        else:raise AssertionError('Creator protection failed')
    try:b.dispatch({'operation':'delete','token':token,'user_id':uid,'confirm':'wrong'})
    except b.Denied:pass
    else:raise AssertionError('Missing delete confirmation')
    b.dispatch({'operation':'delete','token':token,'user_id':uid,'confirm':'fixture0'})
    assert not Path(managed['home']).exists()
    try:pwd.getpwnam(managed['name'])
    except KeyError:pass
    else:raise AssertionError('Deleted Linux identity remains')
    print('PASS: five separate UIDs/private homes; real PAM; ordinary-user denial; admin terminal; host SSH denial; no sudo; disable/reset/re-enable; password change; external password fingerprint; creator guard; confirmed deletion.')
finally:
 for name in created:
    try: p=pwd.getpwnam(name)
    except KeyError: continue
    assert name.startswith('pi2k_900') and p.pw_dir=='/home/'+name
    subprocess.run(['pkill','-KILL','-u',str(p.pw_uid)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    subprocess.run(['userdel',name],check=True)
    shutil.rmtree(p.pw_dir,ignore_errors=True)
