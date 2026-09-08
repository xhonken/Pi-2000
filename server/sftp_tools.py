"""Explicit per-request SFTP operations. Passwords are never persisted."""
import asyncio
import hashlib
import json
import posixpath
import secrets
import stat
import asyncssh
from aiohttp import web

class SFTPTools:
    def __init__(self,app):self.app=app;self.busy=0;self.editor_lock=asyncio.Lock()
    async def handle(self,request):
        a=self.app
        if request.path.endswith('/editor'):
            raw=bytearray()
            async for chunk in request.content.iter_chunked(65536):
                raw.extend(chunk)
                if len(raw)>7*1024**2:raise web.HTTPRequestEntityTooLarge(max_size=7*1024**2,actual_size=len(raw))
            a.require_current(request);data=json.loads(raw)
            if not isinstance(data,dict):raise web.HTTPBadRequest()
        else:data=await a.read_json(request)
        uid=request[a.USER]['id'];action=data.get('action')
        def ensure():
            a.require_current(request)
            if request.transport is None or request.transport.is_closing():raise web.HTTPBadRequest(text='The transfer was cancelled.')
        if action not in ('list','mkdir','send','receive','read','write'):raise web.HTTPBadRequest()
        password=data.get('password','');path=data.get('path','.')
        if not isinstance(password,str) or len(password)>1024 or not isinstance(path,str) or len(path)>2048 or '\x00' in path:raise web.HTTPBadRequest()
        with a.db() as db:
            row=db.execute("SELECT * FROM items WHERE id=? AND user_id=? AND kind='profile'",(data.get('profile'),uid)).fetchone()
            if not row:raise web.HTTPNotFound(text='The connection does not exist.')
            profile=dict(row);saved=db.execute('SELECT key FROM hostkeys WHERE user_id=? AND host=? AND port=?',(uid,profile['host'],profile['port'])).fetchone()
        if self.busy>=2:raise web.HTTPTooManyRequests(text='Two file transfers are already in progress. Try again shortly.')
        self.busy+=1;connection=None
        try:
            class Check(asyncssh.SSHClient):
                presented=None
                def validate_host_public_key(self,host,addr,port,key):
                    self.presented=key
                    return saved['key']==key.export_public_key().decode().strip() if saved else data.get('trust')==key.get_fingerprint('sha256')
            check=Check()
            try:
                connection=await asyncssh.connect(profile['host'],port=profile['port'],username=profile['username'],password=password,client_keys=[],agent_path=None,config=None,known_hosts=b'',client_factory=lambda:check,connect_timeout=15,login_timeout=20)
            except asyncssh.HostKeyNotVerifiable:
                if saved or not check.presented:raise web.HTTPConflict(text='The SSH host key does not match the saved key.')
                return web.json_response({'error':'Verify and accept the SSH host key.','fingerprint':check.presented.get_fingerprint('sha256')},status=409)
            ensure()
            if not saved:
                with a.db() as db:
                    db.execute('INSERT OR IGNORE INTO hostkeys VALUES (?,?,?,?)',(profile['host'],profile['port'],check.presented.export_public_key().decode().strip(),uid))
                    known=db.execute('SELECT key FROM hostkeys WHERE user_id=? AND host=? AND port=?',(uid,profile['host'],profile['port'])).fetchone()[0]
                    if known!=check.presented.export_public_key().decode().strip():raise web.HTTPConflict(text='The host key changed during the connection.')
            async with asyncio.timeout(120),connection.start_sftp_client() as sftp:
                if action=='list':
                    entries=[]
                    async for row in sftp.scandir(path):
                        if row.filename in ('.','..'):continue
                        entries.append({'name':row.filename,'folder':stat.S_ISDIR(row.attrs.permissions or 0),'size':row.attrs.size or 0})
                        if len(entries)>1000:raise web.HTTPBadRequest(text='The folder contains more than 1,000 items.')
                    return web.json_response({'path':await sftp.realpath(path),'items':entries})
                if action=='mkdir':
                    ensure();await sftp.mkdir(path);return web.json_response({'ok':True})
                if action in ('read','write'):
                    # Canonical paths keep opening a symlink from replacing the link itself.
                    async def read_text(target):
                        attrs=await sftp.lstat(target)
                        if attrs.size is None or attrs.size>1048576 or not stat.S_ISREG(attrs.permissions or 0):
                            raise web.HTTPBadRequest(text='Select a regular UTF-8 text file no larger than 1 MB. Reopen symbolic links through their target file.')
                        body=bytearray()
                        async with sftp.open(target,'rb') as remote:
                            while chunk:=await remote.read(65536):
                                ensure();body.extend(chunk)
                                if len(body)>1048576:raise web.HTTPBadRequest(text='The file is larger than 1 MB.')
                        try:text=body.decode('utf-8')
                        except UnicodeDecodeError:raise web.HTTPBadRequest(text='The file is not UTF-8. Use file transfer for binary files.')
                        if '\x00' in text:raise web.HTTPBadRequest(text='Binary files cannot be edited.')
                        return text,hashlib.sha256(body).hexdigest(),attrs
                    if action=='read':
                        target=await sftp.realpath(path);text,version,attrs=await read_text(target)
                        return web.json_response({'path':target,'name':posixpath.basename(target),'text':text,'version':version})
                    async with self.editor_lock:
                        text=data.get('text');expected=data.get('version')
                        try:encoded=text.encode('utf-8') if isinstance(text,str) else None
                        except UnicodeEncodeError:raise web.HTTPBadRequest(text='The text contains invalid Unicode characters.')
                        if encoded is None or b'\x00' in encoded or len(encoded)>1048576 or not isinstance(expected,str) or (expected and (len(expected)!=64 or any(c not in '0123456789abcdef' for c in expected))):
                            raise web.HTTPBadRequest(text='Invalid text or file version. Maximum 1 MB of UTF-8 text.')
                        target=posixpath.join(await sftp.realpath(posixpath.dirname(path) or '.'),posixpath.basename(path))
                        if posixpath.basename(path) in ('','.','..'):raise web.HTTPBadRequest()
                        attrs=None
                        async def check_version():
                            nonlocal attrs
                            try:_,actual,attrs=await read_text(target)
                            except asyncssh.SFTPNoSuchFile:
                                if expected:raise web.HTTPConflict(text='The file was deleted on the device. Save a copy instead.')
                                return
                            if not expected or actual!=expected:raise web.HTTPConflict(text='The file changed on the device. Your changes remain in the editor. Open the device version or save a copy.')
                        await check_version()
                        temporary=posixpath.join(posixpath.dirname(target),'.win2k-'+secrets.token_hex(16))
                        try:
                            async with sftp.open(temporary,'xb',attrs=asyncssh.SFTPAttrs(permissions=0o600)) as remote:
                                await remote.write(encoded)
                            # Recheck immediately before replacement. SFTP cannot provide a
                            # cross-client atomic compare-and-swap against outside editors.
                            ensure();await check_version()
                            if attrs:
                                await sftp.setstat(temporary,asyncssh.SFTPAttrs(uid=attrs.uid,gid=attrs.gid,permissions=stat.S_IMODE(attrs.permissions)))
                            ensure()
                            if expected:await sftp.posix_rename(temporary,target)
                            else:await sftp.rename(temporary,target)
                        finally:
                            try:await sftp.remove(temporary)
                            except asyncssh.SFTPError:pass
                        return web.json_response({'path':target,'version':hashlib.sha256(encoded).hexdigest()})
                limit=50*1024**2
                if action=='receive':
                    attrs=await sftp.stat(path)
                    if attrs.size is None or attrs.size>limit or not stat.S_ISREG(attrs.permissions or 0):raise web.HTTPBadRequest(text='Select a regular file no larger than 50 MB.')
                    body=bytearray()
                    async with sftp.open(path,'rb') as remote:
                        while chunk:=await remote.read(65536):
                            body.extend(chunk);ensure()
                            if len(body)>limit:raise web.HTTPBadRequest(text='The file is larger than 50 MB.')
                    ensure()
                    key=a.FILES.store_bytes(uid,data.get('parent','files'),posixpath.basename(path),body)
                    return web.json_response({'id':key})
                with a.db() as db:
                    row=a.FILES.row(db,uid,data.get('file'),'live')
                    if row['kind']!='file' or row['size']>limit:raise web.HTTPBadRequest(text='Select a file no larger than 50 MB.')
                    handle=a.FILES.blob(uid,row['content_key'] or row['id']).open('rb')
                temporary=posixpath.join(posixpath.dirname(path),'.win2k-'+secrets.token_hex(16))
                try:
                    async with sftp.open(temporary,'xb') as remote:
                        with handle:
                            while chunk:=handle.read(65536):ensure();await remote.write(chunk)
                    ensure()
                    if data.get('overwrite') is True:await sftp.posix_rename(temporary,path)
                    else:await sftp.rename(temporary,path)
                finally:
                    handle.close()
                    try:await sftp.remove(temporary)
                    except asyncssh.SFTPError:pass
                return web.json_response({'ok':True})
        except (TimeoutError,OSError):raise web.HTTPBadGateway(text='The SFTP connection was interrupted or timed out. Check the file on the device before trying again.')
        except asyncssh.PermissionDenied:raise web.HTTPForbidden(text='SFTP login failed.')
        except asyncssh.SFTPFileAlreadyExists:raise web.HTTPConflict(text='The destination file already exists. Select Overwrite explicitly to replace it.')
        except asyncssh.SFTPError as exc:raise web.HTTPBadRequest(text='SFTP: '+str(exc))
        except asyncssh.Error:raise web.HTTPBadGateway(text='SSH connection failed.')
        finally:
            if connection:connection.close();await connection.wait_closed()
            self.busy-=1
