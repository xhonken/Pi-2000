"""Git workspaces isolated from Pi-2000 code and private platform files."""
import asyncio
import base64
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import signal
from urllib.parse import urlsplit
from aiohttp import web

MAX_PROJECT = 64*1024*1024


class GitTools:
    def __init__(self,app):self.app=app;self.root=app.STATE/'git-workspaces';self.running=set()
    def initialize(self):
        self.root.mkdir(mode=0o700,exist_ok=True)
        with self.app.db() as db:db.execute('CREATE TABLE IF NOT EXISTS git_projects(id TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,name TEXT NOT NULL)')
    def project(self,uid,key):
        if not isinstance(key,str) or not re.fullmatch('[a-f0-9]{32}',key):raise web.HTTPNotFound(text='Select one of your Git projects.')
        with self.app.db() as db:row=db.execute('SELECT * FROM git_projects WHERE user_id=? AND id=?',(uid,key)).fetchone()
        if not row:raise web.HTTPNotFound(text='Git project not found.')
        return self.root/str(uid)/key
    def path(self,root,value):
        if not isinstance(value,str) or not value or len(value)>1024 or value.startswith('/') or any(p in ('..','.git') for p in Path(value).parts) or '\0' in value:raise web.HTTPBadRequest(text='Use a file path inside this project, outside .git.')
        path=root/value
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()) or '.git' in path.resolve().relative_to(root.resolve()).parts:raise web.HTTPBadRequest(text='Symbolic links and Git internals cannot be edited here.')
        return path
    def size(self,root):
        total=0;count=0
        for directory,folders,files in os.walk(root,followlinks=False):
            folders[:]=[n for n in folders if not (Path(directory)/n).is_symlink()]
            for filename in files:
                path=Path(directory)/filename
                if not path.is_symlink():total+=path.stat().st_size;count+=1
                if total>MAX_PROJECT or count>20000:return MAX_PROJECT+1
        return total
    def remote(self,value):
        if not isinstance(value,str) or len(value)>4096:raise web.HTTPBadRequest(text='Enter an HTTPS Git URL.')
        try:url=urlsplit(value);port=url.port
        except ValueError:raise web.HTTPBadRequest(text='Invalid Git URL.')
        if url.scheme!='https' or not url.hostname or url.username is not None or url.password is not None or url.query or url.fragment or any(c in value for c in '\r\n\0'):raise web.HTTPBadRequest(text='Use an HTTPS repository URL without embedded credentials or query parameters.')
        return value

    async def git(self,root,args,auth=None,remote=None):
        # The sandbox sees only system binaries/certificates and this project.
        # No /home, /opt, /srv, /var/lib, runtime socket or host /proc is mounted.
        sandbox=['/usr/bin/bwrap','--unshare-all','--share-net','--die-with-parent','--new-session','--ro-bind','/usr','/usr','--symlink','usr/bin','/bin','--symlink','usr/lib','/lib','--proc','/proc','--dev','/dev','--tmpfs','/tmp','--dir','/etc','--ro-bind','/etc/ssl/certs','/etc/ssl/certs','--ro-bind','/etc/resolv.conf','/etc/resolv.conf','--ro-bind','/etc/hosts','/etc/hosts','--bind',str(root),'/project','--chdir','/project']
        env={'PATH':'/usr/bin:/bin','HOME':'/tmp','LANG':'C.UTF-8','GIT_CONFIG_NOSYSTEM':'1','GIT_CONFIG_GLOBAL':'/dev/null','GIT_TERMINAL_PROMPT':'0','GIT_LFS_SKIP_SMUDGE':'1'}
        if auth and remote:
            username,password=auth.get('username',''),auth.get('password','')
            if not isinstance(username,str) or not isinstance(password,str) or len(username)>256 or len(password)>4096:raise web.HTTPBadRequest(text='Invalid Git credentials.')
            if password:
                env.update(GIT_CONFIG_COUNT='1',GIT_CONFIG_KEY_0='http.'+remote+'.extraHeader',GIT_CONFIG_VALUE_0='Authorization: Basic '+base64.b64encode((username+':'+password).encode()).decode())
        config=['--literal-pathspecs','-c','core.hooksPath=/dev/null','-c','core.fsmonitor=false','-c','core.pager=cat','-c','credential.helper=','-c','protocol.file.allow=never','-c','protocol.ext.allow=never','-c','protocol.ssh.allow=never','-c','protocol.http.allow=never','-c','http.followRedirects=false','-c','gc.auto=0','-c','core.quotePath=false']
        process=await asyncio.create_subprocess_exec('/usr/bin/prlimit','--cpu=45','--as=536870912','--fsize=67108864','--nofile=128','--',*sandbox,'--','/usr/bin/git',*config,*args,stdin=asyncio.subprocess.DEVNULL,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.STDOUT,env=env,start_new_session=True)
        async def read():
            result=bytearray()
            while True:
                chunk=await process.stdout.read(65536)
                if not chunk:return result.decode(errors='replace')
                result.extend(chunk)
                if len(result)>2*1024*1024:raise web.HTTPBadRequest(text='Git output exceeds 2 MB. Narrow the operation.')
        async def monitor():
            while process.returncode is None:
                await asyncio.sleep(.3)
                if await asyncio.to_thread(self.size,root)>MAX_PROJECT:raise web.HTTPConflict(text='The Git project exceeds 64 MB or 20,000 files. Remove files or use a smaller repository.')
        reader=asyncio.create_task(read());watcher=asyncio.create_task(monitor())
        try:
            async with asyncio.timeout(60):
                finished,_=await asyncio.wait((reader,watcher),return_when=asyncio.FIRST_COMPLETED)
                if watcher in finished:await watcher
                output=await reader;await process.wait()
            if process.returncode:raise web.HTTPBadRequest(text=output[-6000:] or 'Git failed within its resource limits.')
            return output
        except asyncio.TimeoutError:raise web.HTTPRequestTimeout(text='Git exceeded 60 seconds. Inspect project status before retrying.')
        finally:
            if process.returncode is None:
                try:os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                await process.wait()
            reader.cancel();watcher.cancel();await asyncio.gather(reader,watcher,return_exceptions=True)

    async def handle(self,request):
        uid=request[self.app.USER]['id'];raw=bytearray()
        async for chunk in request.content.iter_chunked(65536):
            raw.extend(chunk)
            if len(raw)>2*1024*1024:raise web.HTTPRequestEntityTooLarge(max_size=2*1024*1024,actual_size=len(raw))
        data=json.loads(raw);self.app.require_current(request)
        if not isinstance(data,dict):raise web.HTTPBadRequest(text='Enter a Git command.')
        action=data.get('action')
        if action=='list':
            with self.app.db() as db:return web.json_response({'projects':[dict(r) for r in db.execute('SELECT id,name FROM git_projects WHERE user_id=? ORDER BY name',(uid,))]})
        if uid in self.running or len(self.running)>=2:raise web.HTTPConflict(text='Another Git operation is running. Wait for it to finish.')
        self.running.add(uid);lock=None
        try:
            lock=(self.app.STATE/'files.lock').open('a')
            try:fcntl.flock(lock,fcntl.LOCK_SH|fcntl.LOCK_NB)
            except BlockingIOError:raise web.HTTPConflict(text='A backup or file operation is in progress. Try again shortly.')
            if action in ('init','clone'):
                project_name=data.get('name','')
                if not isinstance(project_name,str) or not 1<=len(project_name)<=100:raise web.HTTPBadRequest(text='Enter a project name of 1–100 characters.')
                with self.app.db() as db:
                    if db.execute('SELECT COUNT(*) FROM git_projects WHERE user_id=?',(uid,)).fetchone()[0]>=10:raise web.HTTPConflict(text='Create up to ten Git projects.')
                key=secrets.token_hex(16);root=self.root/str(uid)/key;root.mkdir(parents=True,mode=0o700)
                try:
                    if action=='init':output=await self.git(root,['init','--initial-branch=main'])
                    else:
                        remote=self.remote(data.get('url'));output=await self.git(root,['clone','--depth=1','--',remote,'.'],data.get('auth'),remote)
                    with self.app.db() as db:db.execute('INSERT INTO git_projects VALUES (?,?,?)',(key,uid,project_name))
                except BaseException:shutil.rmtree(root,ignore_errors=True);raise
                return web.json_response({'id':key,'output':output})
            key=data.get('project');root=self.project(uid,key)
            if action=='delete':
                shutil.rmtree(root)
                with self.app.db() as db:db.execute('DELETE FROM git_projects WHERE id=? AND user_id=?',(key,uid))
                return web.json_response({'ok':True})
            if action=='read':
                path=self.path(root,data.get('path'))
                if not path.is_file() or path.stat().st_size>1024*1024:raise web.HTTPBadRequest(text='Open a text file up to 1 MB.')
                raw=path.read_bytes()
                try:text=raw.decode('utf8')
                except UnicodeDecodeError:raise web.HTTPBadRequest(text='This file is not UTF-8 text.')
                return web.json_response({'text':text,'version':hashlib.sha256(raw).hexdigest()})
            if action=='write':
                path=self.path(root,data.get('path'));text=data.get('text')
                if not isinstance(text,str) or len(text.encode())>1024*1024:raise web.HTTPBadRequest(text='Edit text files up to 1 MB.')
                if path.exists() and (not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=data.get('version')):raise web.HTTPConflict(text='The project file changed. Open it again before saving.')
                if await asyncio.to_thread(self.size,root)+len(text.encode())>MAX_PROJECT:raise web.HTTPConflict(text='The project exceeds its 64 MB limit.')
                path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text);return web.json_response({'version':hashlib.sha256(text.encode()).hexdigest()})
            if action=='status':
                output=await self.git(root,['status','--short','--branch']);files=await self.git(root,['ls-files','--cached','--others','--exclude-standard','-z']);branches=await self.git(root,['branch','--format=%(refname:short)'])
                return web.json_response({'output':output,'files':list(dict.fromkeys(f for f in files.split('\0') if f))[:2000],'branches':branches.splitlines()})
            args=None;auth=None;remote=None
            if action=='diff':args=['diff','--no-ext-diff','--no-textconv']+(['--cached'] if data.get('staged') else [])
            elif action in ('stage','unstage'):
                paths=data.get('paths',[])
                if not isinstance(paths,list) or not 1<=len(paths)<=2000:raise web.HTTPBadRequest(text='Select files to stage or unstage.')
                for path in paths:self.path(root,path)
                if action=='stage':args=['add','--']+paths
                else:
                    try:await self.git(root,['rev-parse','--verify','HEAD']);args=['reset','HEAD','--']+paths
                    except web.HTTPBadRequest:args=['rm','--cached','--ignore-unmatch','--']+paths
            elif action=='commit':
                message=data.get('message','');author=data.get('author','');email=data.get('email','')
                if not all(isinstance(v,str) and v.strip() for v in (message,author,email)) or len(message)>10000 or len(author)>100 or len(email)>254 or any(c in author+email for c in '\r\n<>'):raise web.HTTPBadRequest(text='Enter a commit message, author name and email.')
                args=['-c','user.name='+author,'-c','user.email='+email,'-c','commit.gpgsign=false','commit','-m',message]
            elif action in ('branch','checkout'):
                branch=data.get('branch','')
                if not isinstance(branch,str) or not branch or branch.startswith('-') or len(branch)>200:raise web.HTTPBadRequest(text='Enter a branch name.')
                await self.git(root,['check-ref-format','--branch',branch]);args=['switch','-c',branch] if action=='branch' else ['switch','--',branch]
            elif action=='log':args=['log','-30','--date=iso','--format=%h %ad %an%n%s%n']
            elif action=='remote':
                remote=self.remote(data.get('url'));existing=await self.git(root,['remote']);args=['remote','set-url' if 'origin' in existing.splitlines() else 'add','origin',remote]
            elif action in ('pull','push','fetch'):
                remote=self.remote((await self.git(root,['remote','get-url','origin'])).strip());auth=data.get('auth');args={'pull':['pull','--ff-only','origin'],'fetch':['fetch','origin'],'push':['push','origin','HEAD']}[action]
            else:raise web.HTTPBadRequest(text='Unknown Git command.')
            output=await self.git(root,args,auth,remote);self.app.require_current(request)
            return web.json_response({'output':output or 'Completed.'})
        finally:
            if lock:lock.close()
            self.running.discard(uid)
