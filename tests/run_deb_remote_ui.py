"""Opt-in checks on a package test Pi with a pre-created disposable user.

Password is read from the terminal, never from argv or a file. A disposable
MariaDB is reached through an SSH reverse forward, so the Pi needs no test DB.
"""
import argparse
import getpass
import http.cookiejar
import json
import os
from pathlib import Path
import ssl
import subprocess
import urllib.request
from mariadb_fixture import MariaDBFixture

ROOT=Path(__file__).resolve().parents[1]

def main():
 p=argparse.ArgumentParser();p.add_argument('--host',required=True);p.add_argument('--ssh-user',required=True);p.add_argument('--user',required=True);p.add_argument('--ca',required=True);p.add_argument('--control',required=True);p.add_argument('--skip-browser',action='store_true');p.add_argument('--inspect-browser',action='store_true');a=p.parse_args()
 secret=getpass.getpass('Disposable Pi test account password: ')
 origin='https://'+a.host;context=ssl.create_default_context(cafile=a.ca);jar=http.cookiejar.CookieJar();opener=urllib.request.build_opener(urllib.request.HTTPSHandler(context=context),urllib.request.HTTPCookieProcessor(jar))
 def api(path,data=None,method=None):
  request=urllib.request.Request(origin+'/api'+path,data=json.dumps(data).encode() if data is not None else None,method=method,headers={'Content-Type':'application/json','Origin':origin})
  with opener.open(request,timeout=90) as response:return json.load(response)
 user=api('/login',{'username':a.user,'password':secret})
 assert api('/health')['sessions']=='ok';info=api('/version');print('Installed version:',info['version'],flush=True)
 request=urllib.request.Request(origin+'/api/files/upload?parent=files&name=upgrade-preserved.txt',data=b'Package upgrade preservation fixture',headers={'Content-Type':'application/octet-stream','Origin':origin})
 existing=next((i for i in api('/files')['items'] if i['name']=='upgrade-preserved.txt'),None)
 if existing:
  with opener.open(origin+'/api/files/'+existing['id']+'/download') as response:assert response.read()==b'Package upgrade preservation fixture'
 else:
  with opener.open(request) as response:assert response.status==201
 print('PASS: trusted HTTPS login, session worker and persisted file',flush=True)
 if not a.skip_browser:
  try:
   api('/browser/start',{});status=api('/browser/status');assert status['state']=='running' and status['memory_hard_limit'] is True,status
   if a.inspect_browser:input('Browser is running for user '+str(user['id'])+'; inspect its cgroup as root, then press Enter: ')
   with opener.open(origin+'/api/browser/view/',timeout=30) as response:assert response.status==200
   print('PASS: installed Browser starts with hard memory enforcement and serves its stream client',flush=True)
  finally:api('/browser/stop',{})
 result=api('/development/diagnostics',{'language':'python','source':'def broken(:'});assert result['diagnostics']
 project=api('/development/git',{'action':'init','name':'Package validation'})['id']
 try:
  for command in ({'action':'write','path':'README.md','text':'package fixture','version':None},{'action':'stage','paths':['README.md']},{'action':'commit','message':'Package validation','author':'Fixture','email':'fixture@example.test'}):api('/development/git',dict(command,project=project))
 finally:api('/development/git',{'action':'delete','project':project})
 print('PASS: installed Git sandbox and syntax diagnostics',flush=True)
 env={**os.environ,'PI_TEST_ORIGIN':origin,'PI_TEST_USERNAME':a.user,'PI_TEST_PASSWORD':secret,'NODE_PATH':'/tmp/win2k-browser-check/node_modules'}
 try:
  subprocess.run(['node','tests/upload_picker_ui.cjs'],cwd=ROOT,env=env,check=True)
 finally:
  for item in api('/files')['items']:
   if item['name'] in ('picker-desktop.txt','picker-files.txt','picker-menu.txt'):
    api('/files/'+item['id']+'/trash',{});api('/files/'+item['id'],method='DELETE')
 with MariaDBFixture() as db:
  forward=f'127.0.0.1:18306:127.0.0.1:{db.port}'
  command=['ssh','-S',a.control,'-O']
  subprocess.run(command+['forward','-R',forward,a.ssh_user+'@'+a.host],check=True)
  try:subprocess.run(['node','tests/phpmyadmin_ui.cjs'],cwd=ROOT,env={**env,'WIN2K_TEST_DB_PORT':'18306'},check=True)
  finally:subprocess.run(command+['cancel','-R',forward,a.ssh_user+'@'+a.host],check=True)
 print('PASS: package functional checks complete',flush=True)
 api('/logout',{})
if __name__=='__main__':main()
