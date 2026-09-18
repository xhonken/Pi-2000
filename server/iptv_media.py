"""Login-bound opaque media URLs, HLS rewriting and optional isolated TS conversion."""
import asyncio
from collections import OrderedDict
import os
from pathlib import Path
import re
import secrets
import signal
import time
from urllib.parse import urljoin, urlsplit
from aiohttp import web
from iptv_sources import url


def format_hint(target):
    path=urlsplit(target).path.lower()
    return 'hls' if '.m3u8' in path or path.endswith('.m3u') else 'file' if path.endswith(('.mp4','.m4v','.webm','.mov','.mp3','.m4a','.ogg','.wav')) else 'ts'


class Media:
    def __init__(self, library):
        self.library=library;self.app=library.app;self.sessions={};self.active={};self.converting=False

    async def lifecycle(self,application):
        async def clean():
            while True:
                await asyncio.sleep(30)
                now=time.monotonic()
                for sid,session in list(self.sessions.items()):
                    login=self.app.SESSIONS.get(session['token'])
                    if now-session['used']>120 or not login or login['expires']<time.time():
                        self.sessions.pop(sid,None)
        task=asyncio.create_task(clean())
        try:yield
        finally:
            task.cancel();await asyncio.gather(task,return_exceptions=True);self.sessions.clear()

    def drop(self, uid, source=None):
        for sid,session in list(self.sessions.items()):
            if session['uid']==uid and (source is None or session['source']==source):self.sessions.pop(sid,None)

    def target(self, session, target):
        target=url(target)
        if target in session['reverse']:
            rid=session['reverse'][target];session['reverse'].move_to_end(target)
        else:
            rid=secrets.token_hex(16);session['reverse'][target]=rid;session['targets'][rid]=target
            if len(session['targets'])>4096:
                _,old=session['reverse'].popitem(last=False);session['targets'].pop(old,None)
        return '/api/iptv/media/'+session['id']+'/'+rid

    def create(self, request, source, item, target, mode):
        now=time.monotonic()
        for sid,s in list(self.sessions.items()):
            if now-s['used']>120:self.sessions.pop(sid,None)
        uid=request[self.app.USER]['id'];token=request[self.app.TOKEN]
        # One player per browser login; another user's/login's player is untouched.
        for sid,s in list(self.sessions.items()):
            if s['token']==token:self.sessions.pop(sid,None)
        if len(self.sessions)>=12 or sum(s['uid']==uid for s in self.sessions.values())>=3:
            raise web.HTTPTooManyRequests(text='Close another IPTV player before starting this stream.')
        if mode not in ('original','audio','compatible'):raise web.HTTPBadRequest(text='Choose a playback mode.')
        kind=format_hint(target)
        if mode!='original' and kind=='hls':
            raise web.HTTPBadRequest(text='HLS uses the browser player. Compatibility conversion is available for direct TS and media-file streams.')
        if mode!='original' and not Path('/usr/bin/ffmpeg').is_file():
            raise web.HTTPServiceUnavailable(text='The Pi operator must install FFmpeg for compatibility playback.')
        session={'id':secrets.token_hex(16),'uid':uid,'token':token,'source':source['id'],'revision':source['revision'],
                 'targets':{},'reverse':OrderedDict(),'used':now,'mode':mode,'headers':item['secret'].get('headers',{}),'root':target}
        self.sessions[session['id']]=session
        return {'session':session['id'],'url':self.target(session,target),'format':kind if mode=='original' else 'ts','live':item['kind']=='live','name':item['name']}

    def current(self,request,session):
        self.app.require_current(request)
        if self.sessions.get(session['id']) is not session or session['token']!=request[self.app.TOKEN] or session['uid']!=request[self.app.USER]['id']:
            raise web.HTTPNotFound(text='Playback session expired. Reopen the channel.')
        source=self.library.source(session['uid'],session['source'])
        if source['revision']!=session['revision']:raise web.HTTPConflict(text='Playlist changed. Reopen the channel.')
        session['used']=time.monotonic()

    async def stop(self, request):
        sid=request.match_info['sid'];session=self.sessions.get(sid)
        if session:
            self.current(request,session);self.sessions.pop(sid,None)
        return web.json_response({'ok':True})

    def manifest(self, session, raw, base):
        try:value=raw.decode('utf-8-sig')
        except UnicodeError:raise web.HTTPBadGateway(text='Invalid HLS manifest.') from None
        lines=[]
        for line in value.splitlines():
            line=line.strip()
            if len(line)>16384:raise web.HTTPBadGateway(text='An HLS manifest line is too long.')
            if line.startswith(('#EXT-X-CONTENT-STEERING','#EXT-X-DEFINE')):
                raise web.HTTPBadGateway(text='This HLS manifest uses unsupported steering or URL variables.')
            if line and not line.startswith('#'):line=self.target(session,urljoin(base,line))
            elif line.startswith('#EXT'):
                line=re.sub(r'([\w-]*URI)="([^"]*)"',lambda m:m[1]+'="'+self.target(session,urljoin(base,m[2]))+'"',line)
            elif not line.startswith('#EXTM3U'):continue
            lines.append(line)
        return ('\n'.join(lines)+'\n').encode()

    async def handle(self,request):
        session=self.sessions.get(request.match_info['sid'])
        if not session:raise web.HTTPNotFound(text='Playback session expired. Reopen the channel.')
        self.current(request,session)
        target=session['targets'].get(request.match_info['resource'])
        if target is None:raise web.HTTPNotFound(text='Media resource expired. Reopen the channel.')
        uid=session['uid']
        if sum(self.active.values())>=20 or self.active.get(uid,0)>=6:raise web.HTTPTooManyRequests(text='Too many media downloads. Close another player.')
        self.active[uid]=self.active.get(uid,0)+1
        response=None
        try:
            headers=dict(session['headers'])
            value=request.headers.get('Range')
            if value:
                if not re.fullmatch(r'bytes=(?:\d{1,18}-\d{0,18}|-\d{1,18})',value):raise web.HTTPBadRequest(text='Invalid media byte range.')
                if session['mode']=='original':headers['Range']=value
            async with self.library.network.open(target,headers) as (upstream,final):
                self.current(request,session)
                first=await upstream.content.read(1024)
                mime=upstream.content_type.lower()
                if first.lstrip(b'\xef\xbb\xbf\r\n ').startswith(b'#EXTM3U'):
                    data=bytearray(first)
                    async for chunk in upstream.content.iter_chunked(65536):
                        data.extend(chunk)
                        if len(data)>1024**2:raise web.HTTPBadGateway(text='The HLS manifest exceeds 1 MB.')
                    self.current(request,session)
                    return web.Response(body=self.manifest(session,bytes(data),final),content_type='application/vnd.apple.mpegurl')
                if mime in ('text/html','application/xhtml+xml') or first.lstrip().lower().startswith((b'<!doctype html',b'<html')):
                    raise web.HTTPBadGateway(text='This entry is a web page, not a direct media stream. Use a direct HLS, TS or media-file URL.')
                if session['mode']!='original':
                    return await self.convert(request,session,upstream,first)
                # No upstream cookies, redirect URLs, CORS or arbitrary headers.
                allowed={k:v for k,v in upstream.headers.items() if k.lower() in ('content-length','content-range','accept-ranges')}
                safe_mime=mime if mime.startswith(('video/','audio/')) or mime in ('application/octet-stream','binary/octet-stream') else 'application/octet-stream'
                response=web.StreamResponse(status=upstream.status,headers={**allowed,'Content-Type':safe_mime})
                await response.prepare(request);await response.write(first)
                checked=time.monotonic()
                while True:
                    # Periodic auth checks also stop an idle/revoked upstream.
                    async with asyncio.timeout(20):chunk=await upstream.content.read(65536)
                    if time.monotonic()-checked>=1:self.current(request,session);checked=time.monotonic()
                    if not chunk:break
                    await response.write(chunk)
                await response.write_eof();return response
        except (web.HTTPException,ConnectionError,TimeoutError):
            if response is not None and response.prepared:
                response.force_close();return response
            raise
        finally:
            self.active[uid]-=1
            if not self.active[uid]:del self.active[uid]

    async def convert(self,request,session,upstream,first):
        if self.converting or self.library.importing:raise web.HTTPTooManyRequests(text='The Pi compatibility converter is busy. Use Original mode or wait for the other player.')
        self.converting=True;process=None;writer=None;response=None
        # The decoder has no host data, network or provider credentials. Its only
        # input is a pipe filled through the validated HTTP transport above.
        sandbox=['/usr/bin/bwrap','--unshare-all','--die-with-parent','--new-session','--ro-bind','/usr','/usr',
                 '--symlink','usr/bin','/bin','--symlink','usr/lib','/lib','--ro-bind-try','/lib64','/lib64','--proc','/proc','--dev','/dev','--tmpfs','/tmp','--dir','/etc','--ro-bind','/etc/alternatives','/etc/alternatives','--chdir','/tmp','--']
        codec=['-c:v','copy'] if session['mode']=='audio' else ['-c:v','libx264','-preset','ultrafast','-tune','zerolatency','-vf',r'scale=w=min(1280\,iw):h=min(720\,ih):force_original_aspect_ratio=decrease:force_divisible_by=2','-pix_fmt','yuv420p','-b:v','2500k','-maxrate','3000k','-bufsize','5000k','-g','50']
        # x86 Debian codec libraries need more virtual address space to initialize
        # libx264. Keep the measured Pi/arm64 budget and a bounded x86 budget.
        address_space=805306368 if os.uname().machine in ('x86_64','amd64') else 536870912
        command=['/usr/bin/prlimit','--as='+str(address_space),'--cpu=14400','--nofile=64','--',*sandbox,'/usr/bin/ffmpeg','-hide_banner','-loglevel','error','-nostdin','-filter_threads','1','-filter_complex_threads','1','-threads','2','-max_alloc','33554432','-protocol_whitelist','pipe','-probesize','1048576','-analyzeduration','3000000','-i','pipe:0','-map','0:v:0?','-map','0:a:0?','-sn','-dn',*codec,'-threads','2','-c:a','aac','-b:a','160k','-ac','2','-max_muxing_queue_size','512','-f','mpegts','pipe:1']
        try:
            process=await asyncio.create_subprocess_exec(*command,stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL,start_new_session=True,env={'PATH':'/usr/bin:/bin','HOME':'/tmp','LANG':'C','OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'2','MALLOC_ARENA_MAX':'2'})
            async def feed():
                process.stdin.write(first);await process.stdin.drain()
                async for chunk in upstream.content.iter_chunked(65536):
                    self.current(request,session);process.stdin.write(chunk);await process.stdin.drain()
                process.stdin.close()
            writer=asyncio.create_task(feed())
            async with asyncio.timeout(25):chunk=await process.stdout.read(65536)
            if not chunk:raise web.HTTPBadGateway(text='Conversion failed. The source may be unavailable, encrypted or require a seekable file. Try Original mode.')
            response=web.StreamResponse(headers={'Content-Type':'video/mp2t'})
            await response.prepare(request)
            async with asyncio.timeout(14400):
                while chunk:
                    self.current(request,session);await response.write(chunk)
                    async with asyncio.timeout(20):chunk=await process.stdout.read(65536)
            await response.write_eof();return response
        except (web.HTTPException,ConnectionError,TimeoutError):
            if response is not None and response.prepared:response.force_close();return response
            raise
        finally:
            if writer:
                writer.cancel();await asyncio.gather(writer,return_exceptions=True)
            if process:
                try:os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                await process.wait()
            self.converting=False
