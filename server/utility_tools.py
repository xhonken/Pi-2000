"""Account-scoped network checks, ZIP inspection/extraction and bounded log reads."""
import asyncio
import ipaddress
import os
from pathlib import Path
import re
import secrets
import socket
import stat
import tempfile
import time
import zipfile
from aiohttp import web

MAX_ARCHIVE = 50 * 1024**2
MAX_EXPANDED = 100 * 1024**2
LOG_BYTES = 256 * 1024


def log_slice(body, start, size):
    # A tail may start in the middle of a UTF-8 character or line.
    if start and b'\n' in body: body = body.split(b'\n', 1)[1]
    if b'\0' in body: raise web.HTTPBadRequest(text='Select a text log, not a binary file.')
    text = body.decode('utf-8', errors='replace')
    return {'text': text, 'size': size, 'truncated': bool(start), 'bytes': len(body)}


class UtilityTools:
    def __init__(self, app):
        self.app = app
        self.network_running = set()
        self.archive_running = set()

    def initialize(self):
        with self.app.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS network_targets(id TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,name TEXT NOT NULL,host TEXT NOT NULL,port INTEGER NOT NULL)')

    @staticmethod
    def host(value):
        if not isinstance(value, str) or len(value) > 253 or not value or value.startswith('-'):
            raise web.HTTPBadRequest(text='Enter a host name or IP address, without a URL or command options.')
        try: return str(ipaddress.ip_address(value))
        except ValueError: pass
        if not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.?', value) or any(not label or len(label) > 63 for label in value.rstrip('.').split('.')):
            raise web.HTTPBadRequest(text='Enter a valid host name or IP address.')
        return value

    @staticmethod
    def port(value):
        if type(value) is not int or not 1 <= value <= 65535:
            raise web.HTTPBadRequest(text='Enter a TCP port between 1 and 65535.')
        return value

    async def network(self, request):
        a = self.app; data = await a.read_json(request); user = a.require_current(request); uid = user['id']
        action = data.get('action')
        if action == 'list':
            with a.db() as db:
                targets = [dict(r) for r in db.execute('SELECT id,name,host,port FROM network_targets WHERE user_id=? ORDER BY name', (uid,))]
                devices = [dict(r) for r in db.execute("SELECT name,host,port FROM items WHERE user_id=? AND kind='profile' ORDER BY name", (uid,))]
            return web.json_response({'targets': targets, 'devices': devices})
        if action == 'save':
            host = self.host(data.get('host')); port = self.port(data.get('port')); name = data.get('name')
            if not isinstance(name, str) or not 1 <= len(name.strip()) <= 100:
                raise web.HTTPBadRequest(text='Enter a target name up to 100 characters.')
            key = data.get('id')
            with a.db() as db:
                if key:
                    if not db.execute('UPDATE network_targets SET name=?,host=?,port=? WHERE id=? AND user_id=?', (name.strip(),host,port,key,uid)).rowcount:
                        raise web.HTTPNotFound(text='Target not found in your account.')
                else:
                    if db.execute('SELECT COUNT(*) FROM network_targets WHERE user_id=?',(uid,)).fetchone()[0] >= 100:
                        raise web.HTTPConflict(text='Each account supports 100 saved network targets.')
                    key = secrets.token_hex(16)
                    db.execute('INSERT INTO network_targets VALUES (?,?,?,?,?)',(key,uid,name.strip(),host,port))
            return web.json_response({'id': key})
        if action == 'delete':
            with a.db() as db:
                if not db.execute('DELETE FROM network_targets WHERE id=? AND user_id=?',(data.get('id'),uid)).rowcount:
                    raise web.HTTPNotFound(text='Target not found in your account.')
            return web.json_response({'ok': True})
        if action not in ('dns','ping','tcp'): raise web.HTTPBadRequest(text='Select a network test.')
        host = self.host(data.get('host')); port = self.port(data.get('port',80))
        if uid in self.network_running or len(self.network_running) >= 4:
            raise web.HTTPTooManyRequests(text='A network test is already running. Try again shortly.')
        self.network_running.add(uid)
        proc = None
        try:
            started = time.monotonic()
            async with asyncio.timeout(12):
                records = await asyncio.get_running_loop().getaddrinfo(host,port,type=socket.SOCK_STREAM)
                addresses = list(dict.fromkeys(r[4][0] for r in records))[:16]
                a.require_current(request)
                if action == 'dns': return web.json_response({'host':host,'addresses':addresses,'elapsed_ms':round((time.monotonic()-started)*1000,1)})
                usable = []
                for address in addresses:
                    ip = ipaddress.ip_address(address); ip = getattr(ip,'ipv4_mapped',None) or ip
                    if not (ip.is_unspecified or ip.is_multicast or (ip.is_reserved and not ip.is_loopback) or ip.is_link_local): usable.append(address)
                if not usable: raise web.HTTPBadRequest(text='Select a unicast host address. Multicast, unspecified and link-local targets are not supported.')
                address = next((v for v in usable if ':' not in v),usable[0])
                if action == 'ping':
                    binary = next((p for p in ('/usr/bin/ping','/bin/ping') if Path(p).is_file()),None)
                    if not binary: raise web.HTTPServiceUnavailable(text='Ping is not installed. The Pi operator can install iputils-ping.')
                    proc = await asyncio.create_subprocess_exec(binary,'-n','-c','3','-W','1','-w','4',address,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.STDOUT,env={'PATH':'/usr/bin:/bin','LANG':'C'})
                    output,_ = await proc.communicate(); a.require_current(request)
                    return web.json_response({'host':host,'address':address,'ok':proc.returncode==0,'output':output.decode(errors='replace')[:12000]})
                attempts=[]
                for address in usable[:4]:
                    begin=time.monotonic();writer=None
                    try:
                        async with asyncio.timeout(2): _,writer=await asyncio.open_connection(address,port)
                        attempts.append({'address':address,'ok':True,'elapsed_ms':round((time.monotonic()-begin)*1000,1)})
                        break
                    except (OSError,TimeoutError): attempts.append({'address':address,'ok':False,'elapsed_ms':round((time.monotonic()-begin)*1000,1)})
                    finally:
                        if writer:
                            writer.close()
                            try: await writer.wait_closed()
                            except OSError: pass
                a.require_current(request)
                return web.json_response({'host':host,'port':port,'ok':any(r['ok'] for r in attempts),'attempts':attempts})
        except socket.gaierror: raise web.HTTPBadRequest(text='The Pi could not resolve this host name. Check the name and DNS connection.')
        except TimeoutError: raise web.HTTPGatewayTimeout(text='The network test timed out.')
        finally:
            if proc and proc.returncode is None: proc.kill();await proc.wait()
            self.network_running.discard(uid)

    def source(self, uid, key):
        with self.app.db() as db:
            row = self.app.FILES.row(db,uid,key,'live')
            if row['kind'] != 'file': raise web.HTTPBadRequest(text='Select a file.')
        return row,self.app.FILES.blob(uid,row['content_key'] or row['id'])

    async def log(self, request):
        data=await self.app.read_json(request);user=self.app.require_current(request)
        row,path=self.source(user['id'],data.get('file'))
        try:
            with path.open('rb') as stream:
                size=os.fstat(stream.fileno()).st_size;start=max(0,size-LOG_BYTES);stream.seek(start);body=stream.read(LOG_BYTES)
        except FileNotFoundError: raise web.HTTPNotFound(text='The file changed or was removed. Open it again.')
        self.app.require_current(request)
        return web.json_response({'name':row['name'],**log_slice(body,start,size)})

    def entries(self, archive):
        rows=archive.infolist()
        if len(rows)>2000: raise web.HTTPBadRequest(text='ZIP archives support up to 2,000 entries.')
        names={};total=0;result=[]
        for index,info in enumerate(rows):
            raw=info.orig_filename
            if '\\' in raw or raw.startswith('/') or '\0' in raw or re.match(r'^[A-Za-z]:',raw):
                raise web.HTTPBadRequest(text='This ZIP contains an unsafe path.')
            parts=raw.rstrip('/').split('/')
            if not 1<=len(parts)<=20 or any(p in ('','.','..') for p in parts): raise web.HTTPBadRequest(text='This ZIP contains an unsafe or overly deep path.')
            parts=[self.app.FILES.name(p) for p in parts]
            mode=info.external_attr>>16
            if stat.S_IFMT(mode) not in (0,stat.S_IFREG,stat.S_IFDIR) or info.flag_bits&1 or info.compress_type not in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED):
                raise web.HTTPBadRequest(text='ZIP supports ordinary files/folders with Store or Deflate compression. Encrypted entries and links are not supported.')
            key='/'.join(parts).casefold()
            if key in names: raise web.HTTPBadRequest(text='This ZIP contains duplicate names, including case-insensitive duplicates.')
            names[key]=info.is_dir();total+=info.file_size
            if info.file_size>MAX_ARCHIVE or total>MAX_EXPANDED or info.file_size>max(1024**2,info.compress_size*200):
                raise web.HTTPBadRequest(text='The ZIP exceeds extraction limits (50 MB per file, 100 MB total, maximum expansion ratio 200).')
            result.append({'index':index,'name':'/'.join(parts),'parts':parts,'size':info.file_size,'compressed':info.compress_size,'folder':info.is_dir()})
        for row in result:
            for n in range(1,len(row['parts'])):
                if names.get('/'.join(row['parts'][:n]).casefold()) is False:
                    raise web.HTTPBadRequest(text='A ZIP path is used as both a file and a folder.')
        return result

    async def archive(self, request):
        a=self.app;data=await a.read_json(request);user=a.require_current(request);uid=user['id'];action=data.get('action')
        if action not in ('list','extract'): raise web.HTTPBadRequest(text='Select an archive action.')
        row,path=self.source(uid,data.get('file'));version=row['content_key'] or row['id']
        if row['size']>MAX_ARCHIVE: raise web.HTTPBadRequest(text='Select a ZIP file no larger than 50 MB.')
        if uid in self.archive_running or len(self.archive_running)>=2: raise web.HTTPTooManyRequests(text='Archive tools are busy. Try again shortly.')
        self.archive_running.add(uid)
        try:
            with zipfile.ZipFile(path) as archive:
                entries=self.entries(archive)
                if action=='list': return web.json_response({'name':row['name'],'version':version,'entries':[{k:v for k,v in r.items() if k!='parts'} for r in entries]})
                if data.get('version')!=version: raise web.HTTPConflict(text='The archive changed. Open it again before extracting.')
                selected=data.get('entries')
                if not isinstance(selected,list) or not selected or len(selected)>2000 or any(type(n) is not int or not 0<=n<len(entries) for n in selected):
                    raise web.HTTPBadRequest(text='Select one or more entries to extract.')
                selection=set(selected)
                chosen=[r for r in entries if r['index'] in selection or any(parent['folder'] and r['name'].startswith(parent['name']+'/') for parent in entries if parent['index'] in selection)]
                name=a.FILES.name(data.get('name'));parent=data.get('parent','files')
                total=sum(r['size'] for r in chosen)
                with a.db() as db:
                    a.FILES.parent(db,uid,parent);a.FILES.unique(db,uid,parent,name);usage=a.FILES.usage(db,uid)
                    if usage['used']+usage['reserved']+total>usage['quota']: raise web.HTTPConflict(text='The extracted files exceed your storage quota.')
                with a.FILES.mutation(),tempfile.TemporaryDirectory(prefix='archive-stage-',dir=a.STATE) as temp:
                    async with asyncio.timeout(60):
                        written=0
                        for item in chosen:
                            if item['folder']: continue
                            with archive.open(archive.infolist()[item['index']]) as source,open(Path(temp)/str(item['index']),'xb') as target:
                                os.chmod(target.name,0o600)
                                while chunk:=source.read(65536):
                                    written+=len(chunk)
                                    if written>total: raise web.HTTPBadRequest(text='The ZIP expanded beyond its declared size.')
                                    target.write(chunk);await asyncio.sleep(0);a.require_current(request)
                        a.require_current(request)
                        # One metadata transaction exposes the complete new folder.
                        # Blob names are random IDs, never archive-supplied paths.
                        moved=[]
                        try:
                            with a.db() as db:
                                db.execute('BEGIN IMMEDIATE');a.FILES.parent(db,uid,parent);a.FILES.unique(db,uid,parent,name)
                                usage=a.FILES.usage(db,uid)
                                if usage['used']+usage['reserved']+written>usage['quota']: raise web.HTTPConflict(text='The extracted files exceed your storage quota.')
                                folders={};rows=[]
                                def add(folder,name,kind,size=0):
                                    key=secrets.token_hex(16);rows.append((key,uid,folder,name,name.casefold(),kind,size,time.time()));return key
                                root=add(parent,name,'folder');folders['']=root
                                for item in chosen:
                                    parts=item['parts'];end=len(parts) if item['folder'] else len(parts)-1
                                    for n in range(1,end+1):
                                        key='/'.join(parts[:n]).casefold()
                                        if key not in folders: folders[key]=add(folders['/'.join(parts[:n-1]).casefold()],parts[n-1],'folder')
                                    if not item['folder']:
                                        key=add(folders['/'.join(parts[:-1]).casefold()],parts[-1],'file',item['size']);target=a.FILES.blob(uid,key);target.parent.mkdir(mode=0o700,exist_ok=True)
                                        os.replace(Path(temp)/str(item['index']),target);moved.append(target)
                                if db.execute('SELECT COUNT(*) FROM files WHERE user_id=?',(uid,)).fetchone()[0]+len(rows)>5000: raise web.HTTPConflict(text='Extraction exceeds the limit of 5,000 files and folders.')
                                db.executemany("INSERT INTO files(id,user_id,parent,name,name_key,kind,size,state,modified) VALUES(?,?,?,?,?,?,?,'live',?)",rows)
                        except BaseException:
                            for target in moved: target.unlink(missing_ok=True)
                            raise
                return web.json_response({'folder':root,'files':sum(not r['folder'] for r in chosen),'bytes':written})
        except (zipfile.BadZipFile,NotImplementedError,RuntimeError,EOFError) as exc:
            raise web.HTTPBadRequest(text='This ZIP cannot be read: '+str(exc))
        except FileNotFoundError: raise web.HTTPNotFound(text='The archive changed or was removed. Open it again.')
        except TimeoutError: raise web.HTTPGatewayTimeout(text='ZIP extraction exceeded its time limit.')
        finally:self.archive_running.discard(uid)
