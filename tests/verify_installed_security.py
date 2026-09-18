#!/usr/bin/env python3
"""Opt-in installed HTTPS/PAM security check; creates/removes four test accounts.

Run with sudo and the installed Python environment. No real user data is opened.
The short-lived operator token and all generated passwords stay in memory only.
"""
import asyncio
import gzip
import json
import os
from pathlib import Path
import secrets
import ssl
import sys
import time
import tomllib

if os.geteuid() != 0:
    raise SystemExit('Run with sudo and /opt/pi2000-admin/venv/bin/python.')
sys.path.insert(0, '/opt/pi2000-admin')
import app
import browser_security
from session_store import SessionStore
from aiohttp import ClientSession, CookieJar, TCPConnector

async def main():
    origin = tomllib.loads(Path('/etc/pi2000web/config.toml').read_text())['network']['public_url']
    sessions = SessionStore(app.STATE/'admin.sqlite3')
    with app.db() as db:
        owner = dict(db.execute('SELECT id,version FROM users WHERE is_creator=1').fetchone())
    token = secrets.token_urlsafe(32)
    sessions[token] = {'expires':time.time()+1200, 'user_id':owner['id'], 'version':owner['version']}
    created, clients = [], []
    def client():
        value=ClientSession(connector=TCPConnector(ssl=ssl.create_default_context()),cookie_jar=CookieJar(unsafe=True),headers={'Origin':origin})
        clients.append(value);return value
    admin=client();admin.cookie_jar.update_cookies({app.COOKIE:token})
    async def call(client, method, path, status=200, **kwargs):
        async with client.request(method,origin+path,**kwargs) as response:
            assert response.status==status, (method,path,response.status,status)
            body=await response.read()
            return json.loads(body) if response.content_type=='application/json' else body
    try:
        anonymous=client()
        for path in ('/api/files','/api/workspace','/api/users','/api/vault'):
            async with anonymous.get(origin+path) as response:
                assert response.status==401
                assert response.headers.get('Cache-Control')=='no-store'
                assert response.headers.get('X-Content-Type-Options')=='nosniff'
        async with anonymous.get(origin) as response:
            assert response.status==200
            assert "frame-ancestors 'self'" in response.headers.get('Content-Security-Policy','')
            assert 'max-age=' in response.headers.get('Strict-Transport-Security','')
        await call(anonymous,'POST','/api/login',415,data=gzip.compress(b'{}'),headers={'Content-Encoding':'gzip'})
        print('PASS: anonymous boundaries, response headers and compressed-body rejection',flush=True)
        for i in range(4):
            name='security-check-'+secrets.token_hex(4);password=secrets.token_urlsafe(30)
            uid=(await call(admin,'POST','/api/users',201,json={'username':name,'password':password}))['id']
            user={'id':uid,'name':name};created.append(user)
            if i==0:await call(admin,'PATCH','/api/users/'+str(uid),json={'role':'admin'})
            user['client']=client()
            await call(user['client'],'POST','/api/login',json={'username':name,'password':password});password=None
            user['file']=(await call(user['client'],'POST','/api/files/upload?name=private-fixture.txt',201,data=('private test '+str(i)).encode()))['id']
            await call(user['client'],'POST','/api/items',400,json={'kind':'folder','name':[]})
        for user in created:
            for other in created:
                if user is other:continue
                await call(user['client'],'GET','/api/files/'+other['file']+'/download',404)
                await call(user['client'],'POST','/api/files/'+other['file']+'/trash',404,json={})
                await call(user['client'],'GET','/api/vault',403,headers={'X-Vault-Owner':str(other['id'])})
            await call(admin,'GET','/api/files/'+user['file']+'/download',404)
        print('PASS: four real PAM accounts, including another administrator, cannot read or alter foreign fixture files; owner cannot read them either',flush=True)
        try:browser_security.check()
        except RuntimeError:
            result=await call(created[0]['client'],'POST','/api/browser/start',503,json={})
            assert 'security update' in result.get('error','')
            print('PASS: installed API blocks Browser with the outdated engine',flush=True)
        else:print('PASS: installed Chromium meets the reviewed version floor (no Browser session started)',flush=True)
    finally:
        failures=[]
        try:
            for user in created:
                try:await call(admin,'DELETE','/api/users/'+str(user['id']),json={'confirm':user['name']})
                except Exception:failures.append(user['id'])
        finally:
            sessions.pop(token,None)
            await asyncio.gather(*(c.close() for c in clients))
        assert not failures, 'Disposable account cleanup failed; inspect generated fixture account IDs: '+str(failures)
        print('PASS: disposable accounts and operator token removed',flush=True)

asyncio.run(main())
