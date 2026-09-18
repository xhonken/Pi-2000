#!/usr/bin/env python3
"""Opt-in root harness: disposable PAM account, real HTTPS and public playback.

Playwright runs as the invoking desktop user, never as OS root. No existing
playlist/account content is read. Test credentials are sent over stdin only.
"""
import asyncio
import json
import os
from pathlib import Path
import secrets
import ssl
import subprocess
import sys
import time
import tomllib
from aiohttp import ClientSession,CookieJar,TCPConnector

if os.geteuid()!=0:raise SystemExit('Run with sudo and the installed Python environment.')
operator=os.environ.get('SUDO_USER')
if not operator or operator=='root':raise SystemExit('Invoke through sudo from the desktop OS account.')
sys.path.insert(0,'/opt/win2k-admin')
import app
from session_store import SessionStore

async def main():
    origin=tomllib.loads(Path('/etc/pi2000web/config.toml').read_text())['network']['public_url']
    root=Path(__file__).resolve().parents[1]
    sessions=SessionStore(app.STATE/'admin.sqlite3')
    with app.db() as db:owner=dict(db.execute('SELECT id,version FROM users WHERE is_creator=1').fetchone())
    token=secrets.token_urlsafe(32);sessions[token]={'user_id':owner['id'],'version':owner['version'],'expires':time.time()+1200}
    uid=None;name='media-check-'+secrets.token_hex(4);password=secrets.token_urlsafe(30)
    async with ClientSession(connector=TCPConnector(ssl=ssl.create_default_context()),cookie_jar=CookieJar(unsafe=True),headers={'Origin':origin}) as client:
        client.cookie_jar.update_cookies({app.COOKIE:token})
        try:
            async with client.get(origin) as response:
                assert response.status==200
                assert "media-src 'self' blob:" in response.headers.get('Content-Security-Policy','')
            async with client.post(origin+'/api/users',json={'username':name,'password':password}) as response:
                assert response.status==201;uid=(await response.json())['id']
            artifacts=root/'.test-results/installed-iptv'
            subprocess.run(['runuser','-u',operator,'--','mkdir','-p',str(artifacts)],check=True)
            await asyncio.to_thread(subprocess.run,['runuser','-u',operator,'--','node',str(root/'tests/installed_iptv_ui.cjs')],input=json.dumps({'origin':origin,'username':name,'password':password,'artifacts':str(artifacts)}).encode(),check=True,timeout=300)
        finally:
            try:
                if uid:
                    async with client.delete(origin+'/api/users/'+str(uid),json={'confirm':name}) as response:
                        assert response.status==200,'Remove disposable media-check account ID '+str(uid)
            finally:sessions.pop(token,None)
    print('PASS: installed disposable account, media sources and operator token removed')

asyncio.run(main())
