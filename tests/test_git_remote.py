import unittest
"""Real HTTPS smart-Git round trips through authenticated development endpoints."""
import asyncio
import os
from pathlib import Path
import ssl
import subprocess
from unittest.mock import patch
from aiohttp import web
from aiohttp.test_utils import TestServer
import test_development_tools

class GitRemoteTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=test_development_tools.DevelopmentTests.asyncSetUp
    asyncTearDown=test_development_tools.DevelopmentTests.asyncTearDown
    call=test_development_tools.DevelopmentTests.call
    async def test_https_clone_fetch_pull_push_and_rejected_push(self):
        root=Path(self.temp.name)/'remote';root.mkdir()
        bare=root/'fixture.git'
        def git(*args):return subprocess.check_output(['git',*map(str,args)],stderr=subprocess.STDOUT)
        git('init','--bare','--initial-branch=main',bare);git('-C',bare,'config','http.receivepack','true')
        seed=root/'seed';git('clone',bare,seed);git('-C',seed,'config','user.name','Fixture');git('-C',seed,'config','user.email','fixture@example.test')
        (seed/'README.md').write_text('initial\n');git('-C',seed,'add','.');git('-C',seed,'commit','-m','Initial');git('-C',seed,'push','origin','main')
        cert=root/'cert.pem';key=root/'key.pem'
        subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1','-subj','/CN=127.0.0.1','-addext','subjectAltName=IP:127.0.0.1','-keyout',str(key),'-out',str(cert)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        async def backend(request):
            env={**os.environ,'GIT_PROJECT_ROOT':str(root),'GIT_HTTP_EXPORT_ALL':'1','PATH_INFO':request.path,'REQUEST_METHOD':request.method,'QUERY_STRING':request.query_string,'CONTENT_TYPE':request.headers.get('Content-Type',''),'REMOTE_USER':'fixture'}
            body=await request.read();env['CONTENT_LENGTH']=str(len(body))
            p=await asyncio.create_subprocess_exec('/usr/lib/git-core/git-http-backend',env=env,stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
            raw,err=await p.communicate(body);head,_,content=raw.partition(b'\r\n\r\n');headers={};status=200
            for line in head.decode().split('\r\n'):
                name,_,value=line.partition(':')
                if name.lower()=='status':status=int(value.strip().split()[0])
                else:headers[name]=value.strip()
            return web.Response(status=status,headers=headers,body=content)
        http=web.Application();http.router.add_route('*','/{path:.*}',backend);tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);tls.load_cert_chain(cert,key)
        server=TestServer(http);await server.start_server(ssl=tls)
        original=asyncio.create_subprocess_exec
        async def with_fixture_ca(*args,**kwargs):
            args=list(args)
            if args[0]=='/usr/bin/prlimit':
                # Test-only CA mount; production TLS verification remains enabled.
                i=args.index('--chdir');args[i:i]=['--ro-bind',str(cert),'/tmp/fixture.pem']
                i=args.index('/usr/bin/git');args[i+1:i+1]=['-c','http.sslCAInfo=/tmp/fixture.pem']
            return await original(*args,**kwargs)
        async def command(action,**data):return await self.call('git',{'action':action,**data})
        try:
            with patch('asyncio.create_subprocess_exec',side_effect=with_fixture_ca):
                created=await command('clone',name='HTTPS fixture',url=str(server.make_url('/fixture.git')).replace('http:','https:'));project=created['id']
                self.assertEqual((await command('read',project=project,path='README.md'))['text'],'initial\n')
                (seed/'remote.txt').write_text('from remote');git('-C',seed,'add','.');git('-C',seed,'commit','-m','Remote advance');git('-C',seed,'push','origin','main')
                await command('fetch',project=project);await command('pull',project=project)
                self.assertEqual((await command('read',project=project,path='remote.txt'))['text'],'from remote')
                await command('write',project=project,path='local.txt',text='from Pi API',version=None);await command('stage',project=project,paths=['local.txt']);await command('commit',project=project,message='Pi push',author='Fixture',email='fixture@example.test');await command('push',project=project)
                self.assertEqual(git('--git-dir',bare,'show','main:local.txt').decode(),'from Pi API')
                git('-C',seed,'pull','--ff-only');(seed/'diverge.txt').write_text('remote');git('-C',seed,'add','.');git('-C',seed,'commit','-m','Diverge');git('-C',seed,'push','origin','main')
                await command('write',project=project,path='another.txt',text='local',version=None);await command('stage',project=project,paths=['another.txt']);await command('commit',project=project,message='Local divergence',author='Fixture',email='fixture@example.test')
                rejected=await self.call('git',{'action':'push','project':project},status=400);self.assertIn('rejected',rejected['error'])
                self.assertEqual((await command('read',project=project,path='another.txt'))['text'],'local')
        finally:await server.close()
