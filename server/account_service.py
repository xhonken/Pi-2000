#!/usr/bin/env python3
"""Root account broker. No arbitrary commands, OS names or paths over the socket.

A root-owned binding registry is authoritative for UID/home and creator identity.
Only root's offline CLI can link a pre-existing account. Passwords are transient.
"""
import argparse
import asyncio
from contextlib import contextmanager
import hashlib
import hmac
import json
import os
from pathlib import Path
import pwd
import secrets
import shutil
import socket
import sqlite3
import struct
import subprocess
import threading
import time
import pam_auth

ROOT = Path('/var/lib/pi2000-accounts')
STATE = Path('/var/lib/win2k-admin')
SOCKET = '/run/pi2000-accounts/control.sock'
LOCK = threading.RLock()

class Denied(Exception):
    def __init__(self, message, status=409): self.message=message; self.status=status

@contextmanager
def database(path):
    db=sqlite3.connect(path, timeout=30); db.row_factory=sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON'); db.execute('PRAGMA secure_delete=ON')
    try:
        with db: yield db
    finally: db.close()

def setup_registry():
    ROOT.mkdir(mode=0o700, exist_ok=True); ROOT.chmod(0o700)
    with database(ROOT/'accounts.sqlite3') as db:
        db.executescript('''CREATE TABLE IF NOT EXISTS bindings (
            web_id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, uid INTEGER UNIQUE,
            home TEXT NOT NULL, managed INTEGER NOT NULL, creator INTEGER NOT NULL DEFAULT 0,
            phase TEXT NOT NULL DEFAULT 'reserved', fingerprint TEXT NOT NULL DEFAULT '');
            CREATE UNIQUE INDEX IF NOT EXISTS one_creator ON bindings(creator) WHERE creator=1;
            CREATE TRIGGER IF NOT EXISTS creator_delete BEFORE DELETE ON bindings WHEN OLD.creator=1
            BEGIN SELECT RAISE(ABORT, 'Creator is protected'); END;
            CREATE TRIGGER IF NOT EXISTS creator_update BEFORE UPDATE ON bindings
            WHEN OLD.creator=1 AND (NEW.creator!=1 OR NEW.web_id!=OLD.web_id OR NEW.name!=OLD.name)
            BEGIN SELECT RAISE(ABORT, 'Creator is protected'); END;''')
    key=ROOT/'generation.key'
    if not key.exists():
        fd=os.open(key, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
        with os.fdopen(fd,'wb') as out: out.write(secrets.token_bytes(32))

def user(uid):
    if type(uid) is not int or uid <= 0: raise Denied('Invalid account.',403)
    with database(STATE/'admin.sqlite3') as db:
        row=db.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
    if not row: raise Denied('Account does not exist.',404)
    return dict(row)

def binding(uid):
    with database(ROOT/'accounts.sqlite3') as db:
        row=db.execute('SELECT * FROM bindings WHERE web_id=?',(uid,)).fetchone()
    return dict(row) if row else None

def identity(b):
    try: p=pwd.getpwnam(b['name'])
    except KeyError: raise Denied('The Linux account needs recovery by the OS administrator.')
    if p.pw_uid != b['uid'] or p.pw_dir != b['home'] or p.pw_uid < 1000 or p.pw_uid == 65534:
        raise Denied('Linux identity changed. OS administrator recovery is required.')
    return p

def run(*args, input=None, tolerate=False):
    result=subprocess.run(args, input=input, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
    if result.returncode and not tolerate: raise Denied('System account operation failed; retry or contact the OS administrator.')

def password(value, new=False):
    if not isinstance(value,str) or not (12 if new else 1) <= len(value) or len(value.encode()) > 512 or any(c in value for c in '\0\r\n'):
        raise Denied('Passwords must fit 512 UTF-8 bytes; new passwords need at least 12 characters.')
    return value

def fingerprint(b):
    identity(b)
    # Read only this identity's record, never disclose or duplicate its verifier.
    row=next((line for line in Path('/etc/shadow').read_text().splitlines() if line.split(':',1)[0]==b['name']), '')
    return hmac.new((ROOT/'generation.key').read_bytes(), row.encode(), hashlib.sha256).hexdigest()

def remember(b):
    with database(ROOT/'accounts.sqlite3') as db:
        db.execute('UPDATE bindings SET fingerprint=? WHERE web_id=?',(fingerprint(b),b['web_id']))

def invalidate(uid):
    with database(STATE/'admin.sqlite3') as db:
        db.execute('UPDATE users SET version=version+1 WHERE id=?',(uid,))

def actor(token):
    if not isinstance(token,str) or len(token)!=43: raise Denied('Log in again.',401)
    with database(STATE/'admin.sqlite3') as db:
        row=db.execute('SELECT data FROM login_sessions WHERE token=?',('sha256:'+hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
    if not row: raise Denied('Log in again.',401)
    session=json.loads(row['data']); u=user(session['user_id'])
    if session['expires']<time.time() or not u['active'] or u['version']!=session['version']: raise Denied('Log in again.',401)
    return u

def creator(u):
    b=binding(u['id'])
    return bool(b and b['creator'])

def manage(a,u):
    if a['role']!='admin' or creator(u) or (u['role']=='admin' and not creator(a)):
        raise Denied('You cannot manage this account.',403)

def policy(u,b):
    if not b['managed']: return
    identity(b)
    terminal=bool(u['active'] and u['role']=='admin')
    run('usermod','--shell','/bin/bash' if terminal else '/usr/sbin/nologin','--expiredate','' if u['active'] else '1970-01-02',b['name'])
    run('usermod','-a','-G','pi2000-terminal',b['name']) if terminal else run('gpasswd','-d',b['name'],'pi2000-terminal',tolerate=True)
    if not terminal:
        run('pkill','-KILL','-u',str(b['uid']),tolerate=True)
    remember(b)

def reserve(u):
    b=binding(u['id'])
    if b: return b
    name='pi2k_'+str(u['id']); home='/home/'+name
    try: pwd.getpwnam(name)
    except KeyError: pass
    else: raise Denied('Reserved Linux username already exists; no account was adopted.')
    if Path(home).exists() or Path(home).is_symlink(): raise Denied('Reserved home already exists; no data was changed.')
    with database(ROOT/'accounts.sqlite3') as db:
        db.execute('INSERT INTO bindings(web_id,name,home,managed,creator) VALUES (?,?,?,1,?)',(u['id'],name,home,int(u['is_creator'])))
    return binding(u['id'])

def provision(u,secret):
    password(secret,True); b=reserve(u)
    if b['phase']=='ready':
        if u['account_state']=='pending':
            identity(b)
            run('chpasswd',input=(b['name']+':'+secret+'\n').encode())
        if u['auth_backend']=='legacy':
            with database(STATE/'admin.sqlite3') as db: db.execute("UPDATE users SET auth_backend='pam',salt='',hash='',linux_username=?,account_state=CASE WHEN account_state='pending' THEN 'pending' ELSE 'ready' END,version=version+1 WHERE id=?",(b['name'],u['id']))
        return b
    if b['uid'] is None:
        # A crash after useradd intentionally requires root recovery: never adopt by name.
        try: pwd.getpwnam(b['name'])
        except KeyError: pass
        else: raise Denied('Interrupted account creation needs OS administrator recovery.')
        run('useradd','--create-home','--user-group','--shell','/usr/sbin/nologin','--groups','pi2000-users',b['name'])
        p=pwd.getpwnam(b['name']); Path(p.pw_dir).chmod(0o700)
        with database(ROOT/'accounts.sqlite3') as db: db.execute('UPDATE bindings SET uid=? WHERE web_id=?',(p.pw_uid,u['id']))
        b=binding(u['id'])
    identity(b)
    run('chpasswd',input=(b['name']+':'+secret+'\n').encode())
    policy(u,b)
    with database(ROOT/'accounts.sqlite3') as db: db.execute("UPDATE bindings SET phase='ready' WHERE web_id=?",(u['id'],))
    with database(STATE/'admin.sqlite3') as db:
        db.execute("UPDATE users SET auth_backend='pam',salt='',hash='',linux_username=?,account_state=CASE WHEN account_state='pending' THEN 'pending' ELSE 'ready' END,version=version+1 WHERE id=?",(b['name'],u['id']))
    remember(b)
    return binding(u['id'])

def authenticate(u,secret):
    password(secret)
    if not u['active']: raise Denied('Incorrect username or password.',401)
    b=binding(u['id'])
    if u['auth_backend']=='legacy':
        digest=hashlib.scrypt(secret.encode(),salt=bytes.fromhex(u['salt']),n=16384,r=8,p=1).hex()
        if not hmac.compare_digest(digest,u['hash']): raise Denied('Incorrect username or password.',401)
        b=provision(u,secret)
    if not b or b['phase']!='ready': raise Denied('Account provisioning is incomplete.')
    identity(b)
    if not pam_auth.check(b['name'],secret): raise Denied('Incorrect username or password, or Linux account unavailable.',401)
    if b['creator']: (STATE/'initial-password.txt').unlink(missing_ok=True)
    return b

def dispatch(data):
    with LOCK:
        op=data.get('operation')
        if op=='authenticate':
            u=user(data.get('user_id')); authenticate(u,data.get('password')); return {}
        a=actor(data.get('token'))
        if op=='change_password':
            b=authenticate(a,data.get('current'))
            if not b['managed']: raise Denied('Change this linked Linux account password locally with passwd.',403)
            if not pam_auth.check(b['name'],data.get('current'),password(data.get('password'),True)): raise Denied('The system rejected the new password.')
            remember(b); invalidate(a['id']); return {}
        if op=='create':
            if a['role']!='admin': raise Denied('Administrator permission required.',403)
            import re
            name=data.get('username'); secret=password(data.get('password'),True)
            if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z0-9_.-]{3,64}',name): raise Denied('Invalid username.')
            with database(STATE/'admin.sqlite3') as db:
                old=db.execute('SELECT * FROM users WHERE username=?',(name,)).fetchone()
                if old:
                    if old['account_state']!='pending': raise Denied('This username is already taken.')
                    uid=old['id']
                else:
                    uid=db.execute("INSERT INTO users(username,salt,hash,active,auth_backend,account_state) VALUES (?,'','',0,'pam','pending')",(name,)).lastrowid
            u=user(uid); provision(u,secret)
            policy({**user(uid),'active':1},binding(uid))
            with database(STATE/'admin.sqlite3') as db: db.execute("UPDATE users SET active=1,account_state='ready' WHERE id=?",(uid,))
            return {'id':uid}
        u=user(data.get('user_id')); b=binding(u['id']); manage(a,u)
        if op=='reset':
            if b and not b['managed']: raise Denied('Linked Linux passwords can only be reset by the OS administrator.',403)
            secret=password(data.get('password'),True)
            if not b or b['phase']!='ready': provision(u,secret)
            else:
                identity(b)
                if not pam_auth.check(b['name'],new_password=secret,account=False): raise Denied('System password reset failed.')
                remember(b); invalidate(u['id'])
            return {}
        if op=='update':
            changes=data.get('changes',{})
            if set(changes)=={'role'}:
                if not creator(a) or changes['role'] not in ('admin','user'): raise Denied('Only the creator can change roles.',403)
                column='role'; value=changes[column]
            elif set(changes)=={'active'} and type(changes['active']) is bool:
                column='active'; value=int(changes[column])
                if value and u['account_state']=='pending': raise Denied('Complete provisioning by creating this username again.')
            else: raise Denied('Invalid account update.')
            # Fail closed on interruption: revoke first; OS policy before enabling.
            invalidate(u['id'])
            intended={**u,column:value}
            if b: policy(intended,b)
            with database(STATE/'admin.sqlite3') as db: db.execute('UPDATE users SET '+column+'=? WHERE id=?',(value,u['id']))
            return {}
        if op=='delete':
            if data.get('confirm')!=u['username']: raise Denied('Type the exact username to permanently delete this account.')
            with database(STATE/'admin.sqlite3') as db: db.execute('UPDATE users SET active=0,version=version+1 WHERE id=?',(u['id'],))
            if b and b['managed'] and b['uid'] is None:
                try: pwd.getpwnam(b['name'])
                except KeyError: pass
                else: raise Denied('Recover the interrupted Linux identity before deleting it.')
                if Path(b['home']).exists() or Path(b['home']).is_symlink():
                    raise Denied('Inspect the reserved home before deleting this pending account.')
                with database(ROOT/'accounts.sqlite3') as db: db.execute('DELETE FROM bindings WHERE web_id=?',(u['id'],))
                b=None
            if b and b['managed']:
                try: identity(b)
                except Denied:
                    try: pwd.getpwnam(b['name'])
                    except KeyError:
                        if b['phase']!='deleting': raise
                    else: raise
                else: policy({**u,'active':0},b)
                home=Path(b['home'])
                if home!=Path('/home')/b['name'] or home.is_symlink(): raise Denied('Unsafe home path; OS administrator recovery required.')
                with database(ROOT/'accounts.sqlite3') as db: db.execute("UPDATE bindings SET phase='deleting' WHERE web_id=?",(u['id'],))
                try: pwd.getpwnam(b['name'])
                except KeyError: pass
                else: run('userdel',b['name'])
                if home.exists(): shutil.rmtree(home)
            if b:
                with database(ROOT/'accounts.sqlite3') as db: db.execute('DELETE FROM bindings WHERE web_id=?',(u['id'],))
            return {}
        raise Denied('Unsupported account operation.',403)

async def monitor():
    while True:
        await asyncio.sleep(5)
        def scan():
            with LOCK, database(ROOT/'accounts.sqlite3') as db:
                rows=[dict(r) for r in db.execute("SELECT * FROM bindings WHERE phase='ready'")]
                changed=[]
                for b in rows:
                    try: value=fingerprint(b)
                    except Denied: value='missing'
                    if value!=b['fingerprint']:
                        invalidate(b['web_id']); changed.append(b['web_id'])
                        db.execute('UPDATE bindings SET fingerprint=? WHERE web_id=?',(value,b['web_id']))
                return changed
        changed=await asyncio.to_thread(scan)
        if changed:
            import session_proxy
            for uid in changed:
                try: await session_proxy.control('/run/win2k-sessions/worker.sock','user',user_id=uid)
                except Exception: pass

async def serve():
    slots=asyncio.Semaphore(4)
    async def handle(reader,writer):
        try:
            peer=writer.get_extra_info('socket').getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12)
            if struct.unpack('3i',peer)[1] not in (0,pwd.getpwnam('win2k-admin').pw_uid): return
            if slots.locked(): raise Denied('Account service busy.',409)
            async with slots:
                data=json.loads(await asyncio.wait_for(reader.readline(),10))
                reply=await asyncio.to_thread(dispatch,data)
            response={'ok':True,**reply}
        except Denied as exc: response={'ok':False,'error':exc.message,'status':exc.status}
        except Exception: response={'ok':False,'error':'Account service operation failed. Contact the OS administrator.','status':409}
        try:
            writer.write(json.dumps(response).encode()+b'\n'); await writer.drain()
        finally: writer.close(); await writer.wait_closed()
    Path(SOCKET).unlink(missing_ok=True)
    server=await asyncio.start_unix_server(handle,path=SOCKET,limit=16384)
    os.chown(SOCKET,0,pwd.getpwnam('win2k-admin').pw_gid); os.chmod(SOCKET,0o660)
    watcher=asyncio.create_task(monitor())
    async with server: await server.serve_forever()

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('command',choices=['serve','link','recover']);parser.add_argument('--web-id',type=int);parser.add_argument('--linux-user'); args=parser.parse_args()
    if os.geteuid()!=0: parser.error('Run as root.')
    setup_registry()
    if args.command=='serve': asyncio.run(serve())
    elif args.command=='recover':
        b=binding(args.web_id); p=pwd.getpwnam(args.linux_user)
        if not b or not b['managed'] or b['phase']!='reserved' or b['uid'] is not None or b['name']!=p.pw_name or b['home']!=p.pw_dir or p.pw_uid<1000: parser.error('Not an interrupted reserved identity.')
        with database(ROOT/'accounts.sqlite3') as db: db.execute('UPDATE bindings SET uid=? WHERE web_id=?',(p.pw_uid,args.web_id))
        print('Reserved identity recovered. Retry creation or the legacy login to supply its password.')
    else:
        u=user(args.web_id); p=pwd.getpwnam(args.linux_user)
        if binding(u['id']) or p.pw_uid<1000 or p.pw_uid==65534: parser.error('Identity is already bound or is a system account.')
        with database(ROOT/'accounts.sqlite3') as db:
            db.execute("INSERT INTO bindings(web_id,name,uid,home,managed,creator,phase) VALUES (?,?,?,?,0,?,'ready')",(u['id'],p.pw_name,p.pw_uid,p.pw_dir,u['is_creator']))
        b=binding(u['id']); remember(b)
        with database(STATE/'admin.sqlite3') as db: db.execute("UPDATE users SET auth_backend='pam',salt='',hash='',linux_username=?,linux_managed=0,account_state='ready',version=version+1 WHERE id=?",(p.pw_name,u['id']))
        print('Linked existing Linux identity; password and OS permissions preserved.')
