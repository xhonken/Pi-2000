"""Syntax diagnostics: parse user text without importing or executing it."""
import asyncio
import json
import re
from pathlib import Path
import sys
from aiohttp import web

PYTHON_CHECK = '''import ast,json,sys
source=sys.stdin.read()
try:
 compile(ast.parse(source,filename="editor.py"),"editor.py","exec")
 print(json.dumps({"diagnostics":[]}))
except SyntaxError as e:
 print(json.dumps({"diagnostics":[{"row":max(0,(e.lineno or 1)-1),"column":max(0,(e.offset or 1)-1),"text":e.msg,"type":"error"}]}))
'''


class Diagnostics:
    def __init__(self,app):self.app=app;self.running=set()

    async def handle(self,request):
        uid=request[self.app.USER]['id']
        if uid in self.running or len(self.running)>=2:raise web.HTTPTooManyRequests(text='A syntax check is already running. Try again shortly.')
        raw=bytearray()
        async for chunk in request.content.iter_chunked(65536):
            raw.extend(chunk)
            if len(raw)>1024*1024:raise web.HTTPRequestEntityTooLarge(max_size=1024*1024,actual_size=len(raw))
        data=json.loads(raw);self.app.require_current(request)
        if not isinstance(data,dict):raise web.HTTPBadRequest(text='Enter syntax check details.')
        source=data.get('source');language=data.get('language')
        if not isinstance(source,str) or len(source.encode())>256*1024:raise web.HTTPBadRequest(text='Syntax checking supports up to 256 KB.')
        if language=='python':command=[sys.executable,'-I','-c',PYTHON_CHECK]
        elif language in ('javascript','javascript-module'):command=['/usr/bin/node' if Path('/usr/bin/node').exists() else '/usr/local/bin/node','--check','--input-type='+('module' if language.endswith('module') else 'commonjs')]
        elif language=='json':
            try:json.loads(source);diagnostics=[]
            except json.JSONDecodeError as e:diagnostics=[{'row':e.lineno-1,'column':e.colno-1,'text':e.msg,'type':'error'}]
            return web.json_response({'diagnostics':diagnostics,'language':language})
        else:raise web.HTTPBadRequest(text='Choose Python, JavaScript, JavaScript module or JSON.')
        if uid in self.running or len(self.running)>=2:raise web.HTTPTooManyRequests(text='A syntax check is already running.')
        self.running.add(uid);process=None
        try:
            # Node reserves a large virtual address range; RSS remains bounded by
            # its heap limit and short runtime. Python receives an address limit.
            limit=['/usr/bin/prlimit','--cpu=3','--fsize=0','--nofile=64']
            if language=='python':limit.append('--as=268435456')
            else:command.insert(1,'--max-old-space-size=64')
            process=await asyncio.create_subprocess_exec(*limit,'--',*command,stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'},cwd='/tmp')
            async with asyncio.timeout(5):out,err=await process.communicate(source.encode())
            self.app.require_current(request)
            if language=='python' and process.returncode==0:return web.json_response({**json.loads(out),'language':language})
            if language.startswith('javascript'):
                if process.returncode==0:diagnostics=[]
                else:
                    error=err.decode(errors='replace');line=re.search(r'\[stdin\]:(\d+)',error);message=re.search(r'SyntaxError: (.+)',error)
                    if not message:raise web.HTTPBadRequest(text='The syntax checker could not parse this file within its resource limits.')
                    rows=error.splitlines();caret=next((row.find('^') for row in rows if '^' in row),0)
                    diagnostics=[{'row':int(line[1])-1 if line else 0,'column':max(0,caret),'text':message[1][:500],'type':'error'}]
                return web.json_response({'diagnostics':diagnostics,'language':language})
            raise web.HTTPBadRequest(text='The syntax checker reached its resource limit.')
        except asyncio.TimeoutError:raise web.HTTPRequestTimeout(text='Syntax checking exceeded five seconds.')
        finally:
            if process and process.returncode is None:process.kill();await process.wait()
            self.running.discard(uid)
