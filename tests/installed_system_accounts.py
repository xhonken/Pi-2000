"""Explicit root-only installed HTTPS/PAM/terminal test with disposable accounts."""
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
from aiohttp import ClientSession, CookieJar, TCPConnector, WSMsgType
sys.path.insert(0,'/opt/win2k-admin')
import app
import account_service as broker
from session_store import SessionStore

async def main():
    if os.geteuid()!=0:raise RuntimeError('Run explicitly as root.')
    origin=tomllib.loads(Path('/etc/pi2000web/config.toml').read_text())['network']['public_url']
    tls=ssl.create_default_context(cafile='/var/lib/caddy/.local/share/caddy/pki/authorities/local/root.crt')
    with app.db() as db: owner=dict(db.execute('SELECT * FROM users WHERE is_creator=1').fetchone())
    token=secrets.token_urlsafe(32);sessions=SessionStore(app.STATE/'admin.sqlite3')
    sessions[token]={'expires':time.time()+600,'user_id':owner['id'],'version':owner['version']}
    created=[]
    async with ClientSession(connector=TCPConnector(ssl=tls),cookie_jar=CookieJar(unsafe=True),headers={'Origin':origin}) as admin, ClientSession(connector=TCPConnector(ssl=tls),cookie_jar=CookieJar(unsafe=True),headers={'Origin':origin}) as regular:
        admin.cookie_jar.update_cookies({app.COOKIE:token})
        async def request(client,method,path,data=None,status=200):
            async with client.request(method,origin+'/api'+path,json=data) as response:
                result=await response.json()
                assert response.status==status,(path,response.status,result)
                return result
        try:
            with app.db() as db: pending=db.execute("SELECT username FROM users WHERE username LIKE 'system-check-%' AND account_state='pending'").fetchone()
            name=pending['username'] if pending else 'system-check-'+secrets.token_hex(4);secret=secrets.token_urlsafe(24)
            uid=(await request(admin,'POST','/users',{'username':name,'password':secret},201))['id'];created.append((uid,name))
            login=await request(regular,'POST','/login',{'username':name,'password':secret})
            assert login['auth_backend']=='pam' and login['linux_username']=='pi2k_'+str(uid)
            await request(regular,'GET','/local-terminal',status=403)
            await request(regular,'GET','/users',status=403)
            await request(admin,'PATCH','/users/'+str(uid),{'role':'admin'})
            await request(regular,'POST','/login',{'username':name,'password':secret})
            profile=await request(regular,'GET','/local-terminal')
            payload=json.dumps({'origin':origin,'username':name,'password':secret,'linux_username':profile['username']}).encode()
            await asyncio.to_thread(subprocess.run,['runuser','-u','honken','--','env','NODE_PATH=/tmp/win2k-browser-check/node_modules','/usr/local/bin/node',str(Path(__file__).with_name('installed_accounts_ui.cjs'))],input=payload,check=True)
            assert profile['username']=='pi2k_'+str(uid) and profile['port']==2222
            if os.environ.get('PI2000_TEST_BACKUP')=='1':
                await asyncio.to_thread(subprocess.run,['systemctl','start','win2k-backup.service'],check=True)
                import tarfile
                archive=sorted(Path('/var/backups/win2k').glob('win2k-*.tar'))[-1]
                with tarfile.open(archive) as tar:
                    assert 'system-accounts/accounts.sqlite3' in tar.getnames()
                    assert 'system-accounts/homes/'+profile['username']+'/.profile' in tar.getnames()
                    shadow=tar.extractfile('system-accounts/shadow').read().decode()
                    assert profile['username']+':' in shadow and 'honken:' not in shadow
                print('PASS: root-only backup includes managed home/registry and excludes linked OS credentials; staging restore verified by backup service.')
            async with regular.ws_connect(origin+'/api/terminal') as ws:
                await ws.send_json({'local':True,'password':secret,'cols':80,'rows':24})
                connected=False; output=''; terminal_id=None
                for _ in range(20):
                    msg=await ws.receive(timeout=15)
                    if msg.type==WSMsgType.TEXT:
                        data=json.loads(msg.data)
                        assert data.get('type')!='error',data
                        if data.get('type')=='connected':
                            connected=True; terminal_id=data.get('id') or data.get('terminal');break
                assert connected,'Terminal did not connect'
                await ws.send_bytes(b'id -un\r')
                while profile['username'] not in output:
                    msg=await ws.receive(timeout=10)
                    if msg.type==WSMsgType.BINARY:output+=msg.data.decode(errors='replace')
                    elif msg.type==WSMsgType.TEXT:output+=msg.data
                assert profile['username'] in output
                # A Linux-side password change must invalidate cookie and live terminal.
                subprocess.run(['chpasswd'],input=(profile['username']+':'+secrets.token_urlsafe(24)+'\n').encode(),check=True)
                await asyncio.sleep(11)
                await request(regular,'GET','/session',status=401)
            runtime=await request(admin,'GET','/runtime')
            assert not any(row['id']==uid and row.get('terminals') for row in runtime['users']),runtime
            await request(admin,'DELETE','/users/'+str(uid),{'confirm':'incorrect'},409)
            await request(admin,'DELETE','/users/'+str(owner['id']),{'confirm':owner['username']},403)
            for uid,name in created:
                await request(admin,'DELETE','/users/'+str(uid),{'confirm':name})
                assert broker.binding(uid) is None
            created.clear()
            print('PASS: installed trusted HTTPS; broker provisioning; PAM web login; ordinary-user permissions; admin Local Terminal and actual Linux identity; external passwd revokes cookie and terminal; typed deletion; creator API protection.')
        finally:
            for uid,name in created:
                try:await request(admin,'DELETE','/users/'+str(uid),{'confirm':name})
                except Exception: print('Fixture cleanup required for web ID',uid)
            sessions.pop(token,None)

if __name__=='__main__':asyncio.run(main())
