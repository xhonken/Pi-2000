"""Private MariaDB connections and bounded, asynchronous SQL workspaces.

No shell, SQLite browser, Unix sockets, option files or client-side file loading.
MariaDB's own grants govern SQL operations on the selected database server.
"""
import asyncio
import base64
import json
import secrets
import ssl
import time

import aiomysql
from cryptography.fernet import Fernet
from pymysql import MySQLError
from pymysql.constants import CLIENT
from pymysql.protocol import MysqlPacket
from aiohttp import web

MAX_ROWS = 1000
MAX_BYTES = 2 * 1024 * 1024


def identifier(value):
    if not isinstance(value, str) or not value or len(value) > 64 or '\0' in value:
        raise web.HTTPBadRequest(text='Enter a database object name of 1–64 characters.')
    return '`' + value.replace('`', '``') + '`'


def cell(value):
    if isinstance(value, int) and abs(value) > 9007199254740991:
        return str(value)
    if value is None or isinstance(value, (int, float, str)):
        return value
    if isinstance(value, bytes):
        return {'binary': base64.b64encode(value).decode()}
    return str(value)


class BoundedConnection(aiomysql.Connection):
    """Bound a remote server's packet before allocating its body."""
    async def _read_packet(self, packet_type=MysqlPacket):
        self._packet_bytes = 0
        return await super()._read_packet(packet_type)

    async def _read_bytes(self, count):
        self._packet_bytes = getattr(self, '_packet_bytes', 0) + count
        self._command_bytes = getattr(self, '_command_bytes', 0) + count
        if self._packet_bytes > MAX_BYTES or self._command_bytes > 8 * MAX_BYTES:
            self.close()
            raise ResultLimit()
        return await super()._read_bytes(count)

    async def query(self, sql, unbuffered=False):
        self._command_bytes = 0
        return await super().query(sql, unbuffered=unbuffered)

    async def next_result(self):
        # aiomysql 0.3.2 SSCursor inherits buffered nextset; keep every set streaming.
        await self._read_query_result(unbuffered=True)
        return self._affected_rows

    async def _request_authentication(self):
        if self._ssl_context and not self.server_capabilities & CLIENT.SSL:
            self.close()
            raise web.HTTPBadRequest(text='The server does not support TLS. No database password was sent.')
        return await super()._request_authentication()


class DatabaseTools:
    def __init__(self, app):
        self.app = app
        self.sessions = {}
        self.connecting = 0
        self.cipher = None

    def initialize(self):
        with self.app.db() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS database_connections (
                id TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                data TEXT NOT NULL, secret TEXT NOT NULL DEFAULT '')''')
        # A separate private key is included in the existing full state backup.
        path = self.app.STATE / 'database-credentials.key'
        try:
            with path.open('xb') as f:
                path.chmod(0o600)
                f.write(Fernet.generate_key())
        except FileExistsError:
            pass
        self.cipher = Fernet(path.read_bytes())

    def profile(self, uid, key):
        if not isinstance(key, str):
            raise web.HTTPNotFound(text='The database connection does not exist.')
        with self.app.db() as db:
            row = db.execute('SELECT * FROM database_connections WHERE user_id=? AND id=?', (uid, key)).fetchone()
        if not row:
            raise web.HTTPNotFound(text='The database connection does not exist.')
        return json.loads(row['data']), row['secret']

    async def connections(self, request):
        uid = request[self.app.USER]['id']
        key = request.match_info.get('id')
        if request.method == 'GET':
            with self.app.db() as db:
                rows = db.execute('SELECT * FROM database_connections WHERE user_id=? ORDER BY json_extract(data,\'$.name\')', (uid,)).fetchall()
            return web.json_response({'connections': [dict(json.loads(r['data']), id=r['id'], saved_password=bool(r['secret'])) for r in rows]})
        old, secret = self.profile(uid, key) if key else ({}, '')
        if request.method == 'DELETE':
            for sid, session in list(self.sessions.items()):
                if session['uid'] == uid and session['profile'] == key:
                    self.drop(sid)
            with self.app.db() as db:
                db.execute('DELETE FROM database_connections WHERE user_id=? AND id=?', (uid, key))
            return web.json_response({'ok': True})
        data = await self.app.read_json(request)
        profile = {}
        for name, maximum in [('name', 100), ('host', 253), ('username', 128), ('database', 64), ('ca', 8192)]:
            value = data.get(name, '')
            if not isinstance(value, str) or len(value) > maximum or '\0' in value:
                raise web.HTTPBadRequest(text='Check the connection details.')
            profile[name] = value.strip() if name != 'ca' else value
        if not all(profile[x] for x in ('name', 'host', 'username')) or any(c in profile['host'] for c in '/\\ \t\r\n'):
            raise web.HTTPBadRequest(text='Enter a name, TCP hostname or IP address, and database username.')
        port = data.get('port', 3306)
        if type(port) is not int or not 1 <= port <= 65535:
            raise web.HTTPBadRequest(text='Enter a port from 1 to 65535.')
        profile['port'] = port
        profile['tls'] = data.get('tls', 'verify')
        if profile['tls'] not in ('verify', 'disabled'):
            raise web.HTTPBadRequest(text='Choose verified TLS or an unencrypted connection.')
        password = data.get('password')
        if password is not None and (not isinstance(password, str) or len(password) > 1024):
            raise web.HTTPBadRequest(text='Invalid password.')
        # Changing the endpoint must never forward an old saved credential to a new host.
        changed = any(old.get(k) != profile[k] for k in ('host', 'port', 'username', 'tls', 'ca'))
        if changed:
            secret = ''
        if data.get('save_password') is True:
            if password is not None:
                secret = self.cipher.encrypt(password.encode()).decode()
        else:
            secret = ''
        with self.app.db() as db:
            if not key and db.execute('SELECT COUNT(*) FROM database_connections WHERE user_id=?', (uid,)).fetchone()[0] >= 100:
                raise web.HTTPConflict(text='You can save up to 100 database connections.')
            key = key or secrets.token_hex(16)
            db.execute('INSERT INTO database_connections VALUES (?,?,?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data,secret=excluded.secret', (key, uid, json.dumps(profile), secret))
        return web.json_response({'id': key, **profile, 'saved_password': bool(secret)})

    async def open_connection(self, profile, password):
        context = None
        if profile['tls'] == 'verify':
            context = ssl.create_default_context(cadata=profile['ca'] or None)
        connection = BoundedConnection(host=profile['host'], port=profile['port'],
            user=profile['username'], password=password, db=profile['database'] or None,
            charset='utf8mb4', autocommit=True, local_infile=False, ssl=context,
            connect_timeout=10, program_name='Pi-2000Web MariaDB Manager')
        await connection._connect()
        # aiomysql can otherwise silently connect without TLS to a server lacking SSL.
        if context and not connection._writer.transport.get_extra_info('ssl_object'):
            connection.close()
            raise web.HTTPBadRequest(text='The server did not establish a verified TLS connection.')
        return connection

    def drop(self, sid):
        session = self.sessions.pop(sid, None)
        if session:
            session['conn'].close()
            task = session.get('task')
            if task and task is not asyncio.current_task():
                task.cancel()
            session['password'] = ''

    def session(self, request, sid):
        session = self.sessions.get(sid)
        if not session or session['uid'] != request[self.app.USER]['id'] or session['token'] != request[self.app.TOKEN]:
            raise web.HTTPNotFound(text='The database session ended. Connect again; the saved connection is preserved.')
        session['used'] = time.monotonic()
        return session

    async def handle(self, request):
        raw = bytearray()
        async for chunk in request.content.iter_chunked(65536):
            raw.extend(chunk)
            if len(raw) > 2 * 1024 * 1024:
                raise web.HTTPRequestEntityTooLarge(max_size=2*1024*1024, actual_size=len(raw))
        self.app.require_current(request)
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise web.HTTPBadRequest(text='A JSON object is required.')
        action = data.get('action')
        session = None
        uid = request[self.app.USER]['id']
        try:
            if action in ('connect', 'test'):
                if self.connecting >= 2 or len(self.sessions) + self.connecting >= 12 or sum(s['uid'] == uid for s in self.sessions.values()) + self.connecting >= 4:
                    raise web.HTTPTooManyRequests(text='The database connection limit was reached. Disconnect an unused session.')
                profile, secret = self.profile(uid, data.get('connection'))
                password = data.get('password')
                if password is None:
                    password = self.cipher.decrypt(secret.encode()).decode() if secret else ''
                if not isinstance(password, str) or len(password) > 1024:
                    raise web.HTTPBadRequest(text='Invalid password.')
                self.connecting += 1
                conn = None
                try:
                    async with asyncio.timeout(15):
                        conn = await self.open_connection(profile, password)
                        self.app.require_current(request)
                        current_profile, _ = self.profile(uid, data['connection'])
                        if current_profile != profile:
                            raise web.HTTPConflict(text='The saved connection changed. Connect again.')
                        if action == 'test':
                            return web.json_response({'ok': True, 'version': conn.get_server_info()})
                        sid = secrets.token_hex(24)
                        self.sessions[sid] = {'uid': uid, 'token': request[self.app.TOKEN], 'conn': conn,
                            'profile': data['connection'], 'settings': profile, 'password': password,
                            'used': time.monotonic(), 'task': None}
                        result = {'session': sid, 'version': conn.get_server_info(), 'database': profile['database']}
                        conn = None
                        return web.json_response(result)
                finally:
                    self.connecting -= 1
                    if conn:
                        conn.close()
            sid = data.get('session')
            session = self.session(request, sid)
            if action == 'disconnect':
                self.drop(sid)
                return web.json_response({'ok': True})
            if action == 'cancel':
                task = session['task']
                if task:
                    # Kill only this login's busy connection, while its thread id is still owned.
                    control = None
                    try:
                        async with asyncio.timeout(12):
                            control = await self.open_connection(session['settings'], session['password'])
                            await control.kill(session['conn'].thread_id())
                    finally:
                        if control:
                            control.close()
                        self.drop(sid)
                return web.json_response({'ok': True, 'disconnected': bool(task)})
            if action not in ('query', 'catalog', 'objects', 'structure', 'browse', 'columns'):
                raise web.HTTPBadRequest(text='Unknown database command.')
            if session['task']:
                raise web.HTTPConflict(text='A command is already running in this session.')
            session['task'] = asyncio.current_task()
            started = time.monotonic()
            try:
                async with asyncio.timeout(60):
                    conn = session['conn']
                    parameters = None
                    if action == 'query':
                        sql = data.get('sql', '')
                        if not isinstance(sql, str) or not sql.strip() or len(sql.encode()) > 1024*1024:
                            raise web.HTTPBadRequest(text='Enter SQL up to 1 MB. Run larger imports in smaller batches.')
                    elif action == 'catalog':
                        sql = 'SHOW DATABASES'
                    elif action == 'objects':
                        identifier(data.get('database'))
                        sql = "SELECT TABLE_NAME AS Name, TABLE_TYPE AS Type FROM information_schema.TABLES WHERE TABLE_SCHEMA=%s ORDER BY TABLE_NAME"
                        parameters = (data['database'],)
                    elif action == 'columns':
                        sql = 'SHOW FULL COLUMNS FROM ' + identifier(data.get('database')) + '.' + identifier(data.get('table'))
                    elif action == 'structure':
                        sql = 'SHOW CREATE TABLE ' + identifier(data.get('database')) + '.' + identifier(data.get('table'))
                    else:
                        offset = data.get('offset', 0)
                        if type(offset) is not int or not 0 <= offset <= 10000000:
                            raise web.HTTPBadRequest(text='Invalid page offset.')
                        sql = 'SELECT * FROM ' + identifier(data.get('database')) + '.' + identifier(data.get('table')) + ' LIMIT 100 OFFSET ' + str(offset)
                    results = await self.execute(conn, sql, parameters)
                    current_database = await self.execute(conn, 'SELECT DATABASE()')
                    self.app.require_current(request)
                    return web.json_response({'results': results, 'database': current_database[0]['rows'][0][0], 'in_transaction': bool(conn.server_status & 1), 'autocommit': bool(conn.server_status & 2), 'elapsed_ms': round((time.monotonic()-started)*1000)})
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self.drop(sid)
                return web.json_response({'error': 'The command was interrupted and the connection closed. Reconnect and check the database before retrying writes.', 'disconnected': True}, status=409)
            except ResultLimit:
                self.drop(sid)
                return web.json_response({'error': 'The result exceeded 1,000 rows or 2 MB. The connection closed; use LIMIT or select fewer columns. Check any writes before retrying.', 'disconnected': True}, status=413)
            finally:
                session['task'] = None
                session['used'] = time.monotonic()
        except ResultLimit:
            return web.json_response({'error': 'The server response exceeded the 2 MB packet limit.'}, status=413)
        except MySQLError as exc:
            # SQL errors are returned only to the requesting owner; never logged with credentials/SQL.
            disconnected = bool(session and session['conn'].closed)
            if disconnected:
                self.drop(data['session'])
            detail = str(exc)[:1500]
            cause = exc
            while cause is not None:
                if isinstance(cause, ssl.SSLCertVerificationError):
                    detail = 'TLS certificate verification failed. Check the server hostname and CA certificate in Connection Properties.'
                    break
                cause = cause.__cause__
            if exc.args and exc.args[0] in (1045, 1698):
                detail = 'MariaDB rejected the login. Check the database username and password, and whether the account allows TCP connections from this Pi.'
            elif exc.args and exc.args[0] == 2003 and detail == str(exc)[:1500]:
                detail = 'Could not connect to MariaDB. Check the server address, port, network access and TLS settings in Connection Properties.'
            return web.json_response({'error': detail, 'disconnected': disconnected}, status=400)
        except (OSError, ssl.SSLError, asyncio.TimeoutError) as exc:
            return web.json_response({'error': 'The database connection failed. Check host, port, network and TLS certificate.'}, status=502)

    async def execute(self, conn, sql, parameters=None):
        results, size, count = [], 0, 0
        cursor = await conn.cursor(aiomysql.SSCursor)
        try:
            await cursor.execute(sql, parameters)
            while True:
                columns = [col[0] for col in cursor.description] if cursor.description else []
                rows = []
                if columns:
                    while True:
                        row = await cursor.fetchone()
                        if row is None:
                            break
                        converted = [cell(v) for v in row]
                        size += len(json.dumps(converted).encode())
                        count += 1
                        if count > MAX_ROWS or size > MAX_BYTES:
                            # Close before SSCursor.__aexit__ tries to drain an unbounded result.
                            conn.close()
                            raise ResultLimit()
                        rows.append(converted)
                results.append({'columns': columns, 'rows': rows, 'affected': cursor.rowcount if not columns else len(rows), 'insert_id': cursor.lastrowid})
                if not cursor._result.has_next:
                    break
                if len(results) >= 1000:
                    conn.close()
                    raise ResultLimit()
                await cursor.nextset()
        except MySQLError:
            raise
        except BaseException:
            conn.close()
            raise
        finally:
            if not conn.closed:
                await cursor.close()
        return results

    async def lifecycle(self, app):
        async def sweep():
            while True:
                await asyncio.sleep(15)
                for sid, session in list(self.sessions.items()):
                    if not self.app.session_valid(self.app.SESSIONS.get(session['token'])) or (not session['task'] and time.monotonic()-session['used'] > 1800):
                        self.drop(sid)
        task = asyncio.create_task(sweep())
        yield
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        for sid in list(self.sessions):
            self.drop(sid)


class ResultLimit(Exception):
    pass
