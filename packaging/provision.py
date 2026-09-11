#!/usr/bin/env python3
"""Root-only, retryable first-install account provisioning. Secrets arrive on stdin."""
import hashlib
import hmac
import json
import os
from pathlib import Path
import pwd
import re
import secrets
import subprocess
import sys
import pymysql
from cryptography.fernet import Fernet


def write_json(path, value, mode=0o600):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    temporary=path.with_suffix('.new');temporary.write_text(json.dumps(value)+'\n');temporary.chmod(mode);temporary.replace(path)


def check_password(value):
    if not isinstance(value,str) or not 12<=len(value) or len(value.encode())>512 or any(c in value for c in '\0\r\n'):
        raise ValueError('Enter and confirm a password of at least 12 characters and at most 512 UTF-8 bytes characters without control line breaks.')


def validate_linux(mode, username, password, port, owned=None):
    if mode=='Disabled':return
    if mode not in ('Existing account','Create account with sudo') or not re.fullmatch(r'[a-z_][a-z0-9_-]{0,31}',username):
        raise ValueError('Choose a valid Linux username and terminal mode.')
    if username in ('root','win2k-admin','pi2000-phpmyadmin') or not 1<=port<=65535:
        raise ValueError('Use a regular Linux login and a valid SSH port.')
    try:account=pwd.getpwnam(username)
    except KeyError:account=None
    if mode=='Existing account':
        if not account or account.pw_uid<1000 or account.pw_uid==65534 or account.pw_shell.endswith(('nologin','false')):
            raise ValueError('Local Terminal needs an existing regular Linux login account.')
    else:
        check_password(password)
        if account and (not owned or owned.get('linux_user')!=username or owned.get('linux_uid')!=account.pw_uid):
            raise ValueError('The requested Linux username already exists; choose Existing account or a different name.')


def provision_database(connection, state, save, password):
    name='pi2000_admin'
    with connection.cursor() as cur:
        if not state.get('database_reserved'):
            cur.execute('SELECT 1 FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=%s',(name,))
            database_exists=cur.fetchone()
            cur.execute('SELECT 1 FROM mysql.user WHERE User=%s',(name,))
            if database_exists or cur.fetchone():raise ValueError('pi2000_admin already exists in MariaDB. No existing database or account has been changed.')
            state['database_reserved']=True;save()
        if not state.get('database_ready'):
            digest='*'+hashlib.sha1(hashlib.sha1(password.encode()).digest()).hexdigest().upper()
            cur.execute('CREATE DATABASE IF NOT EXISTS `pi2000_admin` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
            cur.execute("CREATE USER IF NOT EXISTS 'pi2000_admin'@'127.0.0.1' IDENTIFIED BY PASSWORD %s",(digest,))
            cur.execute("GRANT ALL PRIVILEGES ON `pi2000_admin`.* TO 'pi2000_admin'@'127.0.0.1'")
            state['database_ready']=True;save()


def save_connection(app, password, state, save):
    from database_tools import DatabaseTools
    tools=DatabaseTools(app);tools.initialize()
    with app.db() as db:
        owner=db.execute("SELECT id FROM users WHERE is_creator=1").fetchone()['id']
        key=state.setdefault('connection_id',secrets.token_hex(16));save()
        profile={'name':'Local MariaDB','host':'127.0.0.1','port':3306,'username':'pi2000_admin','database':'pi2000_admin','tls':'disabled','ca':''}
        db.execute('INSERT OR IGNORE INTO database_connections(id,user_id,data,secret) VALUES (?,?,?,?)',
                   (key,owner,json.dumps(profile),tools.cipher.encrypt(password.encode()).decode()))


def main(payload):
    if os.geteuid()!=0:raise ValueError('Run setup with sudo.')
    password=payload['admin_password'];check_password(password)
    if not re.fullmatch(r'[A-Za-z0-9_.-]{3,64}',payload.get('creator_username') or 'admin'): raise ValueError('Choose a valid creator username.')
    state_dir=Path('/var/lib/pi2000web');state_dir.mkdir(exist_ok=True,mode=0o700)
    state_file=state_dir/'bootstrap-state.json';pending=state_dir/'bootstrap-pending.json'
    state=json.loads(state_file.read_text()) if state_file.exists() else {}
    save=lambda:write_json(state_file,state)
    if not state.get('complete'): write_json(pending,{'pending':True})
    sys.path.insert(0,'/opt/win2k-admin')
    import app
    import account_service as broker
    import account_install
    app.initialize(initial_password=password, initial_username=payload.get('creator_username') or 'admin')
    account_install.install()
    with app.db() as db: owner=dict(db.execute('SELECT * FROM users WHERE is_creator=1').fetchone())
    if owner['auth_backend']=='pam': broker.authenticate(owner,password)
    elif not hmac.compare_digest(owner['hash'],app.password_hash(password,owner['salt'])):
        raise ValueError('Enter the current creator password; setup never resets existing passwords.')
    write_json(pending,{'pending':True})
    if not state.get('complete'):
        salt=state.setdefault('password_salt',secrets.token_hex(16))
        digest=app.password_hash(password,salt)
        if state.get('password_hash') and not hmac.compare_digest(state['password_hash'],digest):raise ValueError('Retry setup with the original chosen administrator password.')
        state['password_hash']=digest;save()
        # Root authenticates over the local socket. No database root password is changed.
        with pymysql.connect(unix_socket='/run/mysqld/mysqld.sock',user='root',autocommit=True) as db:
            provision_database(db,state,save,password)
        app.initialize(initial_password=password)
        save_connection(app,password,state,save)
    broker.provision(owner,password)
    owner=pwd.getpwnam('win2k-admin')
    for path in app.STATE.iterdir():
        if path.is_file():os.chown(path,owner.pw_uid,owner.pw_gid)
    state['complete']=True;state.pop('password_hash',None);state.pop('password_salt',None);save();pending.unlink(missing_ok=True)
    print('Administrator, private Local MariaDB connection and Local Terminal setup complete.')


if __name__=='__main__':
    try:main(json.load(sys.stdin))
    except Exception as exc:
        # SQL/library exceptions can contain query or credential material.
        print(str(exc) if isinstance(exc,ValueError) else 'Account setup failed. Check local MariaDB/SSH availability and run sudo pi2000web setup again.',file=sys.stderr)
        sys.exit(1)
