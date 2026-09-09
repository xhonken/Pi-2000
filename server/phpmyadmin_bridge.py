"""Authenticated phpMyAdmin gateway over a private PHP-FPM Unix socket."""
import asyncio
import base64
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import secrets
import struct
import time
from aiohttp import web

ROOT = Path('/usr/share/phpmyadmin')
SOCKET = '/run/pi2000-phpmyadmin/php.sock'
LIMIT = 64 * 1024 * 1024
PHP_PATHS = {'index.php', 'js/messages.php'}
STATIC_SUFFIXES = {'.js', '.css', '.png', '.gif', '.jpg', '.svg', '.ico', '.woff', '.woff2', '.ttf', '.map', '.html'}

def record(kind, content=b''):
    return struct.pack('!BBHHBB', 1, kind, 1, len(content), 0, 0) + content

def params(values):
    result = bytearray()
    for key, value in values.items():
        a, b = key.encode(), str(value).encode()
        for n in (len(a), len(b)):
            result.extend(bytes([n]) if n < 128 else struct.pack('!I', n | 0x80000000))
        result.extend(a); result.extend(b)
    return bytes(result)

class PhpMyAdmin:
    def __init__(self, app, databases):
        self.app, self.databases, self.sessions = app, databases, {}
        self.limit = asyncio.Semaphore(1)

    async def lifecycle(self, app):
        async def clean():
            while True:
                await asyncio.sleep(30)
                self.prune()
        task = asyncio.create_task(clean())
        yield
        task.cancel()
        try: await task
        except asyncio.CancelledError: pass
        self.sessions.clear()

    def prune(self):
        now = time.monotonic()
        for key, session in list(self.sessions.items()):
            if session['expires'] < now or not self.app.session_valid(self.app.SESSIONS.get(session['token'])):
                del self.sessions[key]

    async def launch(self, request):
        self.prune()
        self.app.throttle('phpmyadmin-launch:'+str(request[self.app.USER]['id']),20,300)
        if not Path(SOCKET).exists():
            raise web.HTTPServiceUnavailable(text='phpMyAdmin is not installed. Run the Pi-2000 updater.')
        data = await self.app.read_json(request)
        profile, secret = self.databases.profile(request[self.app.USER]['id'], data.get('connection'))
        password = data.get('password')
        if password is None:
            password = self.databases.cipher.decrypt(secret.encode()).decode() if secret else ''
        if not isinstance(password, str) or len(password) > 1024:
            raise web.HTTPBadRequest(text='Invalid database password.')
        # Verify credentials and TLS before creating the embedded session.
        try:
            connection = await self.databases.open_connection(profile, password)
            connection.close()
        except Exception as exc:
            from pymysql import MySQLError
            if isinstance(exc, MySQLError):
                raise web.HTTPBadRequest(text='MariaDB rejected the connection: '+str(exc)) from None
            raise
        token = request[self.app.TOKEN]
        for key, session in list(self.sessions.items()):
            if session['token'] == token:
                if session.get('running'): raise web.HTTPConflict(text='A database request is running. Wait before switching connections.')
                del self.sessions[key]
        if len(self.sessions) >= 100:
            raise web.HTTPServiceUnavailable(text='Too many active database sessions.')
        key = secrets.token_hex(24)
        self.sessions[key] = dict(token=token, uid=request[self.app.USER]['id'],
            profile_id=data['connection'], fingerprint=hashlib.sha256(json.dumps([profile,secret]).encode()).hexdigest(),
            profile=profile, password=password, expires=time.monotonic()+1800)
        return web.json_response({'id':key, 'url':'/api/phpmyadmin/view/'+key+'/'})

    def session(self, request):
        self.prune()
        key = request.match_info['sid']
        session = self.sessions.get(key)
        if not session or session['token'] != request[self.app.TOKEN]:
            raise web.HTTPUnauthorized(text='Database session ended. Reconnect from MariaDB Manager.')
        profile, secret = self.databases.profile(session['uid'], session['profile_id'])
        if hashlib.sha256(json.dumps([profile,secret]).encode()).hexdigest() != session['fingerprint']:
            del self.sessions[key]
            raise web.HTTPUnauthorized(text='Connection settings changed. Reconnect.')
        session['expires'] = time.monotonic()+1800
        return key, session

    async def disconnect(self, request):
        key, session = self.session(request)
        if session.get('running'): raise web.HTTPConflict(text='A database request is running. Wait before disconnecting.')
        del self.sessions[key]
        return web.json_response({'disconnected':True})

    async def view(self, request):
        async with self.limit:
            return await self._view(request)

    async def _view(self, request):
        key, session = self.session(request)
        path = request.match_info.get('path') or 'index.php'
        if any(part in ('..', '.', '') for part in path.split('/')) or '\\' in path:
            raise web.HTTPNotFound()
        if path == 'pi2000.css':
            return web.FileResponse(Path(__file__).parent/'phpmyadmin'/'pi2000.css')
        if path not in PHP_PATHS:
            # Never serve PHP sources, configuration, libraries, setup or SQL files.
            if path.split('/')[0] not in ('js','themes','locale','doc') or Path(path).suffix not in STATIC_SUFFIXES:
                raise web.HTTPNotFound()
            file = ROOT/path
            if not file.is_file():
                raise web.HTTPNotFound()
            return web.FileResponse(file)
        if request.method not in ('GET','HEAD','POST'):
            raise web.HTTPMethodNotAllowed(request.method, ['GET','HEAD','POST'])
        body = bytearray()
        async for chunk in request.content.iter_chunked(65536):
            body.extend(chunk)
            if len(body) > LIMIT:
                raise web.HTTPRequestEntityTooLarge(max_size=LIMIT, actual_size=len(body))
        self.app.require_current(request)
        prefix = '/api/phpmyadmin/view/'+key+'/'
        settings = dict(session['profile'], password=session['password'], base=self.app.ORIGIN+prefix, sid=key)
        cookie = '; '.join(k+'='+v for k,v in request.cookies.items() if k.removeprefix('__Secure-').removesuffix('_https') in ('phpMyAdmin','pma_lang','pma_theme','pma_collation_connection'))
        values = dict(GATEWAY_INTERFACE='CGI/1.1', REQUEST_METHOD=request.method,
            SCRIPT_FILENAME=str(ROOT/path), SCRIPT_NAME=prefix+path,
            REQUEST_URI=prefix+path+('?' + request.query_string if request.query_string else ''),
            DOCUMENT_ROOT=str(ROOT), QUERY_STRING=request.query_string, SERVER_PROTOCOL='HTTP/1.1',
            SERVER_NAME=self.app.ORIGIN.split('://',1)[1], SERVER_PORT='443', HTTPS='on',
            REMOTE_ADDR='127.0.0.1', CONTENT_TYPE=request.content_type if not request.headers.get('Content-Type') else request.headers['Content-Type'],
            CONTENT_LENGTH=len(body), HTTP_COOKIE=cookie, HTTP_HOST=self.app.ORIGIN.split('://',1)[1],
            HTTP_USER_AGENT=request.headers.get('User-Agent',''), HTTP_ACCEPT=request.headers.get('Accept','*/*'),
            PI2000_BRIDGE=base64.b64encode(json.dumps(settings).encode()).decode())
        output = bytearray()
        async with asyncio.timeout(330):
            reader, writer = await asyncio.open_unix_connection(SOCKET)
            session['running'] = True
            try:
                writer.write(record(1, struct.pack('!HB5x',1,0)))
                encoded = params(values)
                for start in range(0,len(encoded),65535): writer.write(record(4, encoded[start:start+65535]))
                writer.write(record(4))
                for start in range(0,len(body),65535):
                    writer.write(record(5,body[start:start+65535])); await writer.drain()
                writer.write(record(5)); await writer.drain()
                while True:
                    version, kind, rid, size, padding, _ = struct.unpack('!BBHHBB', await reader.readexactly(8))
                    data = await reader.readexactly(size)
                    if padding: await reader.readexactly(padding)
                    if kind == 6:
                        output.extend(data)
                        if len(output)>128*1024*1024: raise web.HTTPBadGateway(text='Export exceeds 128 MiB. Export smaller selections.')
                    if kind == 3: break
            finally:
                session['running'] = False
                writer.close(); await writer.wait_closed()
        head, separator, content = output.partition(b'\r\n\r\n')
        if not separator: raise web.HTTPBadGateway(text='phpMyAdmin returned an invalid response.')
        response = web.Response(body=bytes(content))
        for line in head.decode('latin1').split('\r\n'):
            name, _, value = line.partition(':'); value=value.strip()
            if name.lower()=='status': response.set_status(int(value.split()[0]))
            elif name.lower() not in ('connection','transfer-encoding','content-length','x-powered-by'):
                response.headers.add(name,value)
        response.headers['Cache-Control']='no-store'
        return response
