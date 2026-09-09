"""Opt-in installed check with a disposable account; never touches user databases.

Run with the installed Python and sudo. --update first installs the reviewed
checkout, preserving the SSH/Browser worker. Finish real database operations first.
"""
import argparse
import hashlib
import http.cookiejar
import json
import os
from pathlib import Path
import secrets
import shutil
import sqlite3
import ssl
import subprocess
import sys
import tomllib
import urllib.request

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--update',action='store_true')
    parser.add_argument('--child',action='store_true',help=argparse.SUPPRESS)
    args=parser.parse_args()
    if args.child:
        subprocess.run(['node','tests/upload_picker_ui.cjs'],cwd=ROOT,env={**os.environ,'NODE_PATH':'/tmp/win2k-browser-check/node_modules'},check=True)
        from mariadb_fixture import MariaDBFixture
        with MariaDBFixture() as database:
            subprocess.run(['node','tests/phpmyadmin_ui.cjs'],cwd=ROOT,env={**os.environ,'WIN2K_TEST_DB_PORT':str(database.port),'NODE_PATH':'/tmp/win2k-browser-check/node_modules'},check=True)
        return
    if os.geteuid()!=0:parser.error('Run with sudo for the installed CA, disposable account and cgroup verification.')
    if args.update:subprocess.run([str(ROOT/'scripts/update.sh')],cwd=ROOT,check=True)
    subprocess.run([str(ROOT/'scripts/doctor.sh')],cwd=ROOT,check=True)
    config=tomllib.loads(Path('/etc/pi2000web/config.toml').read_text())
    origin=config['network']['public_url']
    context=ssl.create_default_context(cafile='/var/lib/caddy/.local/share/caddy/pki/authorities/local/root.crt') if config['network']['tls']=='internal' else ssl.create_default_context()
    username='stability-'+secrets.token_hex(6);password=secrets.token_urlsafe(32);salt=secrets.token_hex(16)
    sys.path.insert(0,'/opt/win2k-admin')
    import app
    state=Path('/var/lib/win2k-admin');uid=None
    jar=http.cookiejar.CookieJar();opener=urllib.request.build_opener(urllib.request.HTTPSHandler(context=context),urllib.request.HTTPCookieProcessor(jar))
    def api(path,data=None):
        request=urllib.request.Request(origin+'/api'+path,data=json.dumps(data).encode() if data is not None else None,headers={'Origin':origin,'Content-Type':'application/json'})
        with opener.open(request,timeout=90) as response:return json.load(response)
    def db():
        conn=sqlite3.connect(state/'admin.sqlite3');conn.execute('PRAGMA foreign_keys=ON');return conn
    try:
        with db() as conn:
            uid=conn.execute('INSERT INTO users(username,salt,hash) VALUES (?,?,?)',(username,salt,app.password_hash(password,salt))).lastrowid
        api('/login',{'username':username,'password':password})
        health=api('/health');assert health['web']=='ok' and health['sessions']=='ok'
        info=api('/version');expected=json.loads(Path('/opt/win2k-admin/build-info.json').read_text());assert info==expected
        api('/browser/start',{})
        status=api('/browser/status');assert status.get('memory_hard_limit') is True,status
        group=Path('/sys/fs/cgroup/system.slice/win2k-sessions.service')/('browser-'+str(uid))
        for name,value in [('memory.max',1536*1024**2),('memory.high',1024**3),('memory.swap.max',256*1024**2)]:assert int((group/name).read_text())==value
        api('/browser/stop',{})
        print('PASS: trusted HTTPS, authenticated health/build and live Browser memory limits',flush=True)
        user=os.environ.get('SUDO_USER')
        if not user or user=='root':raise RuntimeError('Run from the development account with sudo so Chromium/MariaDB fixtures stay unprivileged.')
        subprocess.run(['runuser','-u',user,'--',str(ROOT/'.venv/bin/python'),str(Path(__file__).resolve()),'--child'],cwd=ROOT,env={**os.environ,'PI_TEST_ORIGIN':origin,'PI_TEST_USERNAME':username,'PI_TEST_PASSWORD':password},check=True)
        print('PASS: installed phpMyAdmin SQL/import/export and session isolation',flush=True)
    finally:
        if uid is not None:
            try:api('/browser/stop',{})
            except Exception:pass
            try:api('/logout',{})
            except Exception:pass
            with db() as conn:
                conn.execute('DELETE FROM login_sessions WHERE user_id=?',(uid,))
                conn.execute('DELETE FROM users WHERE id=? AND username=?',(uid,username))
            for base in ('browsers','files','git-workspaces'):
                path=state/base/str(uid)
                if path.is_dir():shutil.rmtree(path)
            print('Disposable verification account removed.',flush=True)

if __name__=='__main__':main()
