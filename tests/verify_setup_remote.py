"""Opt-in installed owner-terminal/bootstrap check; passwords only through getpass."""
import argparse
import asyncio
import getpass
import http.cookiejar
import json
from pathlib import Path
import secrets
import ssl
import urllib.error
import urllib.request
import aiohttp


def main():
    p=argparse.ArgumentParser();p.add_argument('--origin',required=True);p.add_argument('--ca',required=True);p.add_argument('--linux-user',required=True);p.add_argument('--web-password-file',help='Read an existing protected bootstrap file instead of prompting');a=p.parse_args()
    password=Path(a.web_password_file).read_text().strip() if a.web_password_file else getpass.getpass('Web admin password: ');linux_password=getpass.getpass('Linux account password: ')
    context=ssl.create_default_context(cafile=a.ca);jar=http.cookiejar.CookieJar()
    opener=urllib.request.build_opener(urllib.request.HTTPSHandler(context=context),urllib.request.HTTPCookieProcessor(jar))
    def api(path,data=None,method=None,client=opener):
        request=urllib.request.Request(a.origin+'/api'+path,data=json.dumps(data).encode() if data is not None else None,method=method,headers={'Origin':a.origin,'Content-Type':'application/json'})
        with client.open(request,timeout=90) as response:return json.load(response)
    assert api('/login',{'username':'admin','password':password})['is_owner']
    profile=api('/local-terminal');assert profile['username']==a.linux_user and profile['host']=='127.0.0.1'
    connection=next(c for c in api('/databases/connections')['connections'] if c['name']=='Local MariaDB')
    assert connection['saved_password'] and connection['database']=='pi2000_admin'
    assert api('/databases/command',{'action':'test','connection':connection['id']})['ok']
    print('PASS installed owner login, OS mapping and encrypted Local MariaDB connection',flush=True)
    async def terminal():
        cookie='; '.join(c.name+'='+c.value for c in jar)
        async with aiohttp.ClientSession(headers={'Cookie':cookie,'Origin':a.origin}) as client:
            async with client.ws_connect(a.origin+'/api/terminal',ssl=context) as ws:
                await ws.send_json({'local':True,'password':linux_password,'cols':100,'rows':30})
                connected=await ws.receive_json(timeout=30);assert connected['type']=='connected',connected.get('message','Unexpected SSH response')
                tid=connected['id'];buffer=''
                async def until(marker):
                    nonlocal buffer
                    async with asyncio.timeout(30):
                        while marker not in buffer:
                            msg=await ws.receive()
                            if msg.type==aiohttp.WSMsgType.BINARY:buffer+=msg.data.decode(errors='replace')
                            elif msg.type in (aiohttp.WSMsgType.CLOSE,aiohttp.WSMsgType.CLOSED,aiohttp.WSMsgType.ERROR):raise RuntimeError('Terminal closed unexpectedly')
                        found=buffer;buffer='';return found
                try:
                    await ws.send_bytes(b"stty -echo; printf '\\nPI2000_USER:'; id -un; printf '\\nPI2000_READY\\n'\n")
                    output=await until('PI2000_READY\r\n');assert 'PI2000_USER:'+a.linux_user+'\r\n' in output
                    await ws.send_bytes(b"sudo -k; sudo -n true; printf '\\nPI2000_NOPASS:%s\\n' $?\n")
                    output=await until('PI2000_NOPASS:');
                    if not output.endswith('\n'):output+=await until('\n')
                    assert 'PI2000_NOPASS:0' not in output,'sudo unexpectedly accepted no password'
                    await ws.send_bytes(b"sudo -S -p 'PI2000_SUDO>' id -u\n")
                    await until('PI2000_SUDO>')
                    await ws.send_bytes((linux_password+'\n').encode())
                    output=await until('0\r\n');assert linux_password not in output
                    print('PASS Local Terminal executes as the selected Linux user; sudo requires its password and returns uid 0',flush=True)
                finally:api('/terminals/'+tid,method='DELETE')
    asyncio.run(terminal())
    ids=[]
    try:
        for role in ('user','admin'):
            name='setup-check-'+secrets.token_hex(4)
            item=api('/users',{'username':name,'password':password});uid=item['id'];ids.append(uid)
            if role=='admin':api('/users/'+str(uid),{'role':'admin'},method='PATCH')
            other=urllib.request.build_opener(urllib.request.HTTPSHandler(context=context),urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
            api('/login',{'username':name,'password':password},client=other)
            assert api('/databases/connections',client=other)['connections']==[]
            try:api('/local-terminal',client=other);raise AssertionError('Local Terminal exposed to another account')
            except urllib.error.HTTPError as exc:assert exc.code==403
            api('/logout',{},client=other)
        print('PASS installed ordinary-user and additional-administrator isolation',flush=True)
    finally:
        for uid in ids:api('/users/'+str(uid),method='DELETE')
        api('/logout',{})

if __name__=='__main__':main()
