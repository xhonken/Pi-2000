import asyncio
import json
import sys
import tempfile
import unittest
from pathlib import Path
from aiohttp import web
from aiohttp.test_utils import TestClient,TestServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
import app
import api_client
from git_tools import GitTools


class DevelopmentTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();app.STATE=Path(self.temp.name);app.SESSIONS={};app.WORKER_SOCKET='';app.WORKER_MODE=False
        self.client=TestClient(TestServer(app.make_app()));await self.client.start_server()
        with app.db() as db:db.execute("INSERT INTO users (username,salt,hash) VALUES ('other','s','h')")
        app.SESSIONS['owner']={'user_id':1,'version':1,'expires':9999999999};app.SESSIONS['other']={'user_id':2,'version':1,'expires':9999999999};self.token='owner'
    async def asyncTearDown(self):await self.client.close();self.temp.cleanup()
    async def call(self,path,data=None,method='POST',status=200):
        response=await self.client.request(method,'/api/development/'+path,json=data,headers={'Origin':app.ORIGIN,'Cookie':app.COOKIE+'='+self.token});result=await response.json();self.assertEqual(response.status,status,result);return result

    async def test_syntax_errors_and_source_is_never_executed(self):
        sentinel=Path(self.temp.name)/'must-not-exist'
        cases=[('python','def broken(:',True),('python','return 1',True),('javascript','const = ;',True),('javascript-module','export const x = 1;',False),('json','{"x":}',True),('python',f'open({str(sentinel)!r},"w").write("executed")',False),('javascript',f'require("fs").writeFileSync({json.dumps(str(sentinel))},"executed");',False)]
        for language,source,errors in cases:
            result=await self.call('diagnostics',{'language':language,'source':source});self.assertEqual(bool(result['diagnostics']),errors,(language,result))
        self.assertFalse(sentinel.exists())

    async def test_api_collections_private_encrypted_and_platform_ports_blocked(self):
        saved=await self.call('requests',{'name':'Example','url':'https://example.com','method':'GET','headers':{'Authorization':'Bearer private-fixture-secret'},'body':''})
        with app.db() as db:encrypted=db.execute('SELECT data FROM api_requests').fetchone()[0];self.assertNotIn('private-fixture-secret',encrypted)
        self.token='other';self.assertEqual((await self.call('requests',method='GET'))['requests'],[]);await self.call('requests/'+saved['id'],method='DELETE',status=404);self.token='owner'
        for url in ('http://127.0.0.1:2019/config','http://127.0.0.1:8765/api/users','http://169.254.169.254/latest/meta-data','http://[::1]:2019/config'):
            await self.call('http',{'url':url},status=400)
        await self.call('http',{'url':'file:///etc/passwd'},status=400)
        await self.call('http',{'url':'http://example.com','headers':{'Host':'localhost'}},status=400)

    async def test_api_http_body_headers_no_ambient_cookie_and_no_redirects(self):
        async def echo(request):return web.json_response({'body':await request.text(),'cookie':request.headers.get('Cookie'),'auth':request.headers.get('Authorization')})
        async def redirect(request):raise web.HTTPFound('http://127.0.0.1:2019/config')
        echo_app=web.Application();echo_app.router.add_post('/echo',echo);echo_app.router.add_get('/redirect',redirect)
        server=TestServer(echo_app);await server.start_server();api_client.DEV_PORTS.add(server.port)
        try:
            result=await self.call('http',{'url':str(server.make_url('/echo')),'method':'POST','headers':{'Authorization':'Bearer fixture'},'body':'hello'})
            self.assertEqual(json.loads(result['body']),{'body':'hello','cookie':None,'auth':'Bearer fixture'})
            result=await self.call('http',{'url':str(server.make_url('/redirect'))});self.assertEqual(result['status'],302)
        finally:api_client.DEV_PORTS.discard(server.port);await server.close()

    async def test_git_isolation_commit_branch_and_file_concurrency(self):
        async def git(action,status=200,**data):return await self.call('git',{'action':action,**data},status=status)
        created=await git('init',name='Private fixture');project=created['id']
        await git('write',project=project,path='README.md',text='hello',version=None)
        read=await git('read',project=project,path='README.md');self.assertEqual(read['text'],'hello')
        await git('write',project=project,path='README.md',text='wrong',version='stale',status=409)
        await git('stage',project=project,paths=['README.md'])
        await git('commit',project=project,message='Initial commit',author='Fixture',email='fixture@example.test')
        await git('branch',project=project,branch='feature/example')
        await git('checkout',project=project,branch='main')
        result=await git('status',project=project);self.assertIn('README.md',result['files']);self.assertIn('feature/example',result['branches'])
        for path in ('../../admin.sqlite3','.git/config','/etc/passwd'):
            await git('read',project=project,path=path,status=400)
        root=app.STATE/'git-workspaces'/'1'/project
        (root/'escape').symlink_to(app.STATE/'admin.sqlite3')
        await git('read',project=project,path='escape',status=400)
        marker=Path(self.temp.name)/'forbidden-hook-output'
        hook=root/'.git/hooks/pre-commit';hook.write_text('#!/bin/sh\ntouch '+str(marker)+'\n');hook.chmod(0o700)
        await git('write',project=project,path='second.txt',text='second',version=None);await git('stage',project=project,paths=['second.txt']);await git('commit',project=project,message='No hooks',author='Fixture',email='fixture@example.test');self.assertFalse(marker.exists())
        manager=GitTools(app)
        output=await manager.git(root,['-c','alias.probe=!test ! -e '+str(app.STATE/'admin.sqlite3')+' && test ! -e /opt/win2k-admin/app.py && echo isolated','probe']);self.assertIn('isolated',output)
        self.token='other';self.assertEqual((await git('list'))['projects'],[]);await git('status',project=project,status=404);self.token='owner'
        await git('remote',project=project,url='file:///home/honken/Documents/win2k',status=400)
        await git('delete',project=project);self.assertFalse(root.exists())
