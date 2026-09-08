import asyncio
from contextlib import contextmanager
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
import logging
import sys
from sftp_tools import SFTPTools
from task_monitor import TaskMonitor
import shutil
from session_store import SessionStore
import session_proxy
from pathlib import Path

import asyncssh
from aiohttp import web, WSMsgType, ClientSession, UnixConnector, ClientError
from yarl import URL
from browser_runtime import BrowserRuntime, BrowserUnavailable
from file_store import FileStore, FILE_USER
from personal_store import PersonalStore

STATE = Path(os.environ.get('WIN2K_STATE', '/var/lib/win2k-admin'))
ORIGIN = os.environ.get('WIN2K_ORIGIN', 'https://localhost')
COOKIE = '__Host-win2k'
TOKEN = web.RequestKey('token', str)
USER = web.RequestKey('user', dict)
SESSIONS = {}
SOCKETS = {}
ATTEMPTS = {}
HASHING = 0
TERMINALS = {}
BROWSERS = None
FILES = None
WORKER_MODE = os.environ.get('WIN2K_SESSION_WORKER') == '1'
WORKER_SOCKET = os.environ.get('WIN2K_WORKER_SOCKET', '') if not WORKER_MODE else ''
TERMINAL_HISTORY_LIMIT = 2 * 1024 * 1024


@contextmanager
def db():
    conn = sqlite3.connect(STATE / 'admin.sqlite3')
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def password_hash(password, salt):
    return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()


async def hash_password(password, salt):
    global HASHING
    if HASHING>=2: raise web.HTTPTooManyRequests(text='The login service is busy. Try again shortly.')
    HASHING+=1
    task=asyncio.create_task(asyncio.to_thread(password_hash,password,salt))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        # A disconnected client must not release its slot while scrypt still runs.
        await task
        raise
    finally: HASHING-=1


def initialize():
    STATE.mkdir(parents=True, exist_ok=True)
    with db() as conn:
        conn.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE COLLATE NOCASE,
            salt TEXT NOT NULL, hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user' CHECK(role IN ('admin','user')),
            active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
            version INTEGER NOT NULL DEFAULT 1);
        DROP TRIGGER IF EXISTS protect_admin_delete;
        DROP TRIGGER IF EXISTS protect_admin_update;
        CREATE TRIGGER protect_admin_delete BEFORE DELETE ON users
            WHEN OLD.username='admin' COLLATE NOCASE BEGIN SELECT RAISE(ABORT, 'Admin is protected'); END;
        CREATE TRIGGER IF NOT EXISTS protect_admin_update BEFORE UPDATE ON users
            WHEN OLD.username='admin' COLLATE NOCASE AND (NEW.role!='admin' OR NEW.active!=1 OR NEW.username!=OLD.username)
            BEGIN SELECT RAISE(ABORT, 'Admin is protected'); END;
        CREATE TABLE IF NOT EXISTS items (id TEXT PRIMARY KEY, parent TEXT, kind TEXT, name TEXT, host TEXT, port INTEGER, username TEXT);
        CREATE TABLE IF NOT EXISTS hostkeys (host TEXT, port INTEGER, key TEXT, PRIMARY KEY(host, port));
        ''')
        if 'storage_quota' not in {row['name'] for row in conn.execute('PRAGMA table_info(users)')}:
            conn.execute('ALTER TABLE users ADD COLUMN storage_quota INTEGER NOT NULL DEFAULT 52428800')
        legacy = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='admin'").fetchone()
        if legacy:
            admin = conn.execute('SELECT * FROM admin WHERE id=1').fetchone()
            if admin and not conn.execute("SELECT 1 FROM users WHERE role='admin'").fetchone():
                conn.execute("INSERT INTO users(username,salt,hash,role) VALUES ('admin',?,?,'admin')", (admin['salt'], admin['hash']))
            conn.execute('DROP TABLE admin')
        if not conn.execute("SELECT 1 FROM users WHERE role='admin'").fetchone():
            password = secrets.token_urlsafe(18)
            salt = secrets.token_hex(16)
            conn.execute("INSERT INTO users(username,salt,hash,role) VALUES ('admin',?,?,'admin')", (salt, password_hash(password, salt)))
            path = STATE / 'initial-password.txt'
            path.write_text(password + '\n')
            path.chmod(0o600)

        owner_id = conn.execute("SELECT id FROM users WHERE username='admin'").fetchone()['id']
        if 'user_id' not in {row['name'] for row in conn.execute('PRAGMA table_info(items)')}:
            conn.execute('ALTER TABLE items RENAME TO legacy_items')
            conn.execute('CREATE TABLE items (id TEXT PRIMARY KEY, parent TEXT, kind TEXT, name TEXT, host TEXT, port INTEGER, username TEXT, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE)')
            conn.execute('INSERT INTO items SELECT *,? FROM legacy_items', (owner_id,))
            conn.execute('DROP TABLE legacy_items')
        if 'user_id' not in {row['name'] for row in conn.execute('PRAGMA table_info(hostkeys)')}:
            conn.execute('ALTER TABLE hostkeys RENAME TO legacy_hostkeys')
            conn.execute('CREATE TABLE hostkeys (host TEXT, port INTEGER, key TEXT, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, PRIMARY KEY(user_id,host,port))')
            conn.execute('INSERT INTO hostkeys SELECT *,? FROM legacy_hostkeys', (owner_id,))
            conn.execute('DROP TABLE legacy_hostkeys')
        conn.execute('CREATE INDEX IF NOT EXISTS items_user ON items(user_id)')
        conn.execute('CREATE TABLE IF NOT EXISTS workspaces (user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE, data TEXT NOT NULL)')
        conn.execute('CREATE TABLE IF NOT EXISTS desktops (user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE, data TEXT NOT NULL)')


def is_owner(user):
    return user['username'].lower() == 'admin'


def public_user(user):
    return {**{key: user[key] for key in ('id', 'username', 'role', 'active', 'storage_quota')}, 'is_owner': is_owner(user)}


def session_valid(session):
    if not session or session['expires'] < time.time():
        return None
    with db() as conn:
        user = conn.execute('SELECT * FROM users WHERE id=? AND active=1', (session['user_id'],)).fetchone()
    return dict(user) if user and user['version'] == session['version'] else None


def error(message, status=400):
    return web.json_response({'error': message}, status=status)


def maintenance_active():
    try:
        return json.loads((STATE/'maintenance.json').read_text()).get('expires',0) > time.time()
    except (OSError, ValueError):
        return False


@web.middleware
async def guard(request, handler):
    if WORKER_MODE and request.path == '/internal/control':
        return await handler(request)
    if request.method not in ('GET', 'HEAD') or request.path == '/api/terminal':
        if request.headers.get('Origin') != ORIGIN:
            return error('Origin not allowed.', 403)
    if maintenance_active() and (request.method not in ('GET','HEAD') or request.path == '/api/terminal'):
        return error('A backup is in progress. Try again shortly.', 503)
    token = request.cookies.get(COOKIE, '')
    if isinstance(SESSIONS, SessionStore) and token and not re.fullmatch(r'[A-Za-z0-9_-]{43}', token):
        return error('Log in again.', 401)
    session = SESSIONS.get(token)
    if request.path != '/api/login':
        user = session_valid(session)
        if not user:
            await revoke(token)
            return error('Log in again.', 401)
        request[TOKEN] = token
        request[USER] = user
        if request.path.startswith('/api/users') and user['role'] != 'admin':
            return error('Only administrators can manage users.', 403)
    try:
        response = await handler(request)
    except web.HTTPException as exc:
        response = error(exc.text or exc.reason, exc.status)
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        response = error('Check the details and try again.')
    except (OSError, ClientError, asyncio.TimeoutError):
        logging.exception('Service operation failed: %s', request.path)
        response = error('The service is temporarily unavailable. Try again shortly.', 503)
    response.headers['Cache-Control'] = 'no-store'
    return response


def require_current(request):
    user=session_valid(SESSIONS.get(request[TOKEN]))
    if not user: raise web.HTTPUnauthorized(text='The account or login changed. Log in again.')
    request[USER]=user
    if request.path.startswith('/api/users') and user['role']!='admin':
        raise web.HTTPForbidden(text='Administrator permission is required.')
    return user


async def read_json(request):
    data=await request.json()
    if TOKEN in request: require_current(request)
    if not isinstance(data,dict): raise web.HTTPBadRequest(text='A JSON object is required.')
    return data


def throttle(key, limit, interval=300):
    now=time.time()
    # Bound memory even when callers continually invent new source/account keys.
    for old in list(ATTEMPTS):
        if not ATTEMPTS[old] or ATTEMPTS[old][-1]<=now-300: ATTEMPTS.pop(old,None)
    attempts=[t for t in ATTEMPTS.get(key,[]) if t>now-interval]
    if len(attempts)>=limit or (key not in ATTEMPTS and len(ATTEMPTS)>=4096):
        raise web.HTTPTooManyRequests(text='Too many attempts. Wait a moment and try again.')
    ATTEMPTS[key]=attempts+[now]


async def login(request):
    now = time.time()
    source=request.headers.get('X-Forwarded-For',request.remote or '')
    throttle('source:'+source,10)
    throttle('global-login',60,60)
    data = await read_json(request)
    username=data.get('username','')
    if isinstance(username,str): throttle('account:'+username.strip().casefold(),20)
    password = data.get('password', '')
    if not isinstance(password, str) or len(password) > 1024:
        return error('Incorrect username or password.', 401)
    username = data.get('username', '')
    if not isinstance(username, str):
        return error('Incorrect username or password.', 401)
    with db() as conn:
        user = conn.execute('SELECT * FROM users WHERE username=?', (username.strip(),)).fetchone()
    digest = await hash_password(password, user['salt'] if user else '00' * 16)
    if not user or not hmac.compare_digest(digest, user['hash']) or not user['active']:
        return error('Incorrect username or password.', 401)
    # Recheck after hashing: an administrator may have revoked this account meanwhile.
    with db() as conn:
        latest = conn.execute('SELECT active,version FROM users WHERE id=?', (user['id'],)).fetchone()
    if not latest or not latest['active'] or latest['version'] != user['version']:
        return error('Incorrect username or password.', 401)
    ATTEMPTS.pop('source:'+source, None)
    ATTEMPTS.pop('account:'+username.strip().casefold(), None)
    for token, session in list(SESSIONS.items()):
        if session['expires'] < now:
            await revoke(token)
    token = secrets.token_urlsafe(32)
    SESSIONS[token] = {'expires': now + 12 * 3600, 'user_id': user['id'], 'version': user['version'], 'created':now, 'agent':request.headers.get('User-Agent','')[:240]}
    response = web.json_response(public_user(user))
    response.set_cookie(COOKIE, token, secure=True, httponly=True, samesite='Strict', path='/', max_age=43200)
    return response


async def revoke(token):
    SESSIONS.pop(token, None)
    if WORKER_SOCKET:
        try:
            await session_proxy.control(WORKER_SOCKET, 'token', token=token)
        except (ClientError, OSError, asyncio.TimeoutError):
            pass  # The worker also polls the shared revocation state.
    await close_token_sockets(token)


async def close_token_sockets(token):
    keys = [key for key in SOCKETS if SessionStore.key(key) == SessionStore.key(token)]
    await asyncio.gather(*(ws.close(code=1008, message=b'Session ended')
        for key in keys for ws in list(SOCKETS.get(key, set()))), return_exceptions=True)


async def logout(request):
    await revoke(request[TOKEN])
    response = web.json_response({'ok': True})
    response.del_cookie(COOKIE, path='/', secure=True, httponly=True, samesite='Strict')
    return response


async def change_password(request):
    throttle('password:'+str(request[USER]['id']),10)
    data = await read_json(request)
    password = data.get('password', '')
    current = data.get('current', '')
    if not isinstance(password, str) or not 12 <= len(password) <= 1024 or not isinstance(current, str) or len(current) > 1024:
        return error('The new password must contain at least 12 characters.')
    user = request[USER]
    digest = await hash_password(current, user['salt'])
    if not hmac.compare_digest(digest, user['hash']):
        return error('The current password is incorrect.', 403)
    salt = secrets.token_hex(16)
    digest = await hash_password(password, salt)
    with db() as conn:
        changed = conn.execute('UPDATE users SET salt=?,hash=?,version=version+1 WHERE id=? AND version=? AND active=1', (salt, digest, user['id'], user['version']))
        if not changed.rowcount:
            return error('The account changed. Log in again.', 401)
    if is_owner(user):
        (STATE / 'initial-password.txt').unlink(missing_ok=True)
    if request[TOKEN] in SESSIONS:
        current_session = SESSIONS[request[TOKEN]]
        current_session['version'] = user['version'] + 1
        SESSIONS[request[TOKEN]] = current_session
    await revoke_user(user['id'], except_token=request[TOKEN])
    return web.json_response({'ok': True})


async def revoke_user(user_id, except_token=None):
    if WORKER_SOCKET:
        await session_proxy.control(WORKER_SOCKET, 'user', user_id=user_id)
    if BROWSERS:
        await BROWSERS.stop(user_id)
    for terminal_id, term in list(TERMINALS.items()):
        if term.user_id == user_id:
            await term.stop()
            TERMINALS.pop(terminal_id, None)
    for token, session in list(SESSIONS.items()):
        if session['user_id'] == user_id and SessionStore.key(token) != SessionStore.key(except_token or ''):
            await revoke(token)


async def personal_sessions(request):
    uid=request[USER]['id'];selected=request.match_info.get('id');rows=[]
    for key,session in list(SESSIONS.items()):
        if session['user_id']!=uid or not session_valid(session):continue
        identifier=hashlib.sha256(SessionStore.key(key).encode()).hexdigest()
        if request.method=='DELETE' and identifier==selected:
            await revoke(key);return web.json_response({'ok':True})
        rows.append({'id':identifier,'current':SessionStore.key(key)==SessionStore.key(request[TOKEN]),'expires':session['expires'],'created':session.get('created',session['expires']-43200),'agent':session.get('agent','Previous Login')})
    if request.method=='DELETE':raise web.HTTPNotFound()
    return web.json_response({'sessions':rows})


async def session_info(request):
    return web.json_response(public_user(request[USER]))


async def users(request):
    with db() as conn:
        return web.json_response({'users': [public_user(row) for row in conn.execute('SELECT * FROM users ORDER BY role,username COLLATE NOCASE')]})


async def create_user(request):
    data = await read_json(request)
    username, password = data.get('username', ''), data.get('password', '')
    if not isinstance(username, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{3,64}', username):
        return error('Usernames must contain 3–64 characters: letters a–z, digits, dots, hyphens or underscores.')
    if not isinstance(password, str) or not 12 <= len(password) <= 1024:
        return error('The password must contain 12–1024 characters.')
    salt = secrets.token_hex(16)
    digest = await hash_password(password, salt)
    if not session_valid(SESSIONS.get(request[TOKEN])):
        return error('Log in again.', 401)
    try:
        with db() as conn:
            cursor = conn.execute('INSERT INTO users(username,salt,hash) VALUES (?,?,?)', (username, salt, digest))
            user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        return error('This username is already taken.', 409)
    return web.json_response({'id': user_id}, status=201)


async def update_user(request):
    user_id = int(request.match_info['id'])
    data = await read_json(request)
    role_change = set(data) == {'role'}
    if role_change:
        if not is_owner(request[USER]):
            return error('Only the owner can change roles.', 403)
        if data['role'] not in ('admin', 'user'):
            return error('Select administrator or user.')
    elif set(data) != {'active'} or type(data['active']) is not bool:
        return error('Specify a role or whether the account should be enabled.')
    with db() as conn:
        user = conn.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
        if not user:
            return error('The user does not exist.', 404)
        if is_owner(user):
            return error('The owner account role and status cannot be changed.', 403)
        if user['role'] == 'admin' and not is_owner(request[USER]):
            return error('Only the owner can manage administrators.', 403)
        if role_change:
            conn.execute('UPDATE users SET role=?,version=version+1 WHERE id=?', (data['role'], user_id))
        else:
            conn.execute('UPDATE users SET active=?,version=version+1 WHERE id=?', (int(data['active']), user_id))
    await revoke_user(user_id)
    return web.json_response({'ok': True})


async def delete_user(request):
    user_id = int(request.match_info['id'])
    with db() as conn:
        user = conn.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
        if not user:
            return error('The user does not exist.', 404)
        if is_owner(user) or (user['role'] == 'admin' and not is_owner(request[USER])):
            return error('You cannot delete this administrator account.', 403)
        conn.execute('DELETE FROM users WHERE id=?', (user_id,))
    await revoke_user(user_id)
    await asyncio.to_thread(shutil.rmtree, STATE/'files'/str(user_id), True)
    if WORKER_SOCKET:
        await session_proxy.control(WORKER_SOCKET, 'remove', user_id=user_id)
    if BROWSERS:
        await BROWSERS.stop(user_id, remove=True)
    return web.json_response({'ok': True})


async def reset_password(request):
    user_id = int(request.match_info['id'])
    data = await read_json(request)
    password = data.get('password', '')
    if not isinstance(password, str) or not 12 <= len(password) <= 1024:
        return error('The password must contain 12–1024 characters.')
    salt = secrets.token_hex(16)
    digest = await hash_password(password, salt)
    if not session_valid(SESSIONS.get(request[TOKEN])):
        return error('Log in again.', 401)
    with db() as conn:
        user = conn.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
        if not user:
            return error('The user does not exist.', 404)
        if is_owner(user) or (user['role'] == 'admin' and not is_owner(request[USER])):
            return error('Use Change Password and enter your current password.', 403)
        conn.execute('UPDATE users SET salt=?,hash=?,version=version+1 WHERE id=?', (salt, digest, user_id))
    await revoke_user(user_id)
    return web.json_response({'ok': True})


async def desktop(request):
    user_id = request[USER]['id']
    with db() as conn:
        if request.method == 'GET':
            row = conn.execute('SELECT data FROM desktops WHERE user_id=?', (user_id,)).fetchone()
            return web.json_response(json.loads(row['data']) if row else None)
    payload=bytearray()
    async for chunk in request.content.iter_chunked(65536):
        payload.extend(chunk)
        if len(payload)>1024**2:
            return error('Desktop settings are too large.',413)
    require_current(request)
    try: data=json.loads(payload)
    except (ValueError,UnicodeDecodeError): return error('Invalid desktop settings.')
    if not isinstance(data, dict) or set(data) not in ({'shortcuts', 'color'}, {'shortcuts', 'color', 'positions'}):
        return error('Invalid desktop settings.')
    if data['color'] not in ('#3a6ea5', '#008080', '#2d4739') or not isinstance(data['shortcuts'], list):
        return error('Invalid desktop settings.')
    positions=data.get('positions',{})
    if not isinstance(positions,dict) or len(positions)>5200:
        return error('Invalid icon positions.')
    for key,point in positions.items():
        if (not isinstance(key,str) or len(key)>160 or not isinstance(point,list) or len(point)!=2
                or any(type(v) is not int or not 0<=v<=10000 for v in point)):
            return error('Invalid icon position.')
    for item in data['shortcuts']:
        if (not isinstance(item, dict) or set(item) != {'id', 'name', 'url', 'desktop', 'start', 'deleted'}
                or any(not isinstance(item[key], str) for key in ('id', 'name', 'url'))
                or not 1 <= len(item['name']) <= 80
                or not item['url'].startswith(('http://', 'https://'))
                or any(type(item[key]) is not bool for key in ('desktop', 'start', 'deleted'))):
            return error('Invalid shortcut.')
    with db() as conn:
        conn.execute('INSERT INTO desktops VALUES (?,?) ON CONFLICT(user_id) DO UPDATE SET data=excluded.data', (user_id, json.dumps(data)))
    return web.json_response({'ok': True})


async def items(request):
    with db() as conn:
        return web.json_response({'items': [dict(row) for row in conn.execute('SELECT * FROM items WHERE user_id=? ORDER BY kind,name COLLATE NOCASE', (request[USER]['id'],))]})


async def save_item(request):
    data = await read_json(request)
    user_id = request[USER]['id']
    item_id = request.match_info.get('id') or secrets.token_hex(12)
    name = data.get('name', '').strip()
    kind = data.get('kind')
    parent = data.get('parent') or None
    if kind not in ('folder', 'profile') or not 1 <= len(name) <= 80:
        return error('Enter a name of up to 80 characters.')
    host, username, port = '', '', 22
    if kind == 'profile':
        host = data.get('host', '').strip().lower()
        username = data.get('username', '').strip()
        port = int(data.get('port', 22))
        if not re.fullmatch(r'[a-zA-Z0-9_.:%-]{1,253}', host) or host.startswith('-') or not username or len(username) > 128 or any(ord(c) < 32 for c in username) or not 1 <= port <= 65535:
            return error('Enter a hostname/IP address, username and a port between 1 and 65535.')
    with db() as conn:
        existing = conn.execute('SELECT * FROM items WHERE id=? AND user_id=?', (item_id, user_id)).fetchone()
        if request.method == 'PUT' and not existing:
            return error('The profile or folder does not exist.', 404)
        if existing and existing['kind'] != kind:
            return error('The item type cannot be changed.')
        ancestor = parent
        seen = {item_id}
        while ancestor:
            if ancestor in seen:
                return error('A folder cannot be placed inside itself.')
            seen.add(ancestor)
            row = conn.execute('SELECT * FROM items WHERE id=? AND user_id=? AND kind="folder"', (ancestor, user_id)).fetchone()
            if not row:
                return error('The folder does not exist.')
            ancestor = row['parent']
        if existing:
            conn.execute('UPDATE items SET parent=?,name=?,host=?,port=?,username=? WHERE id=? AND user_id=?', (parent, name, host, port, username, item_id, user_id))
        else:
            if conn.execute('SELECT COUNT(*) FROM items WHERE user_id=?',(user_id,)).fetchone()[0]>=5000:
                return error('Maximum 5,000 folders and connections per account.',409)
            conn.execute('INSERT INTO items VALUES (?,?,?,?,?,?,?,?)', (item_id, parent, kind, name, host, port, username, user_id))
    return web.json_response({'id': item_id})


async def delete_item(request):
    with db() as conn:
        item_id = request.match_info['id']
        user_id = request[USER]['id']
        if not conn.execute('SELECT 1 FROM items WHERE id=? AND user_id=?', (item_id, user_id)).fetchone():
            return error('The profile or folder does not exist.', 404)
        if conn.execute('SELECT 1 FROM items WHERE parent=? AND user_id=?', (item_id, user_id)).fetchone():
            return error('The folder must be empty before it can be deleted.')
        conn.execute('DELETE FROM items WHERE id=? AND user_id=?', (item_id, user_id))
    return web.json_response({'ok': True})


class HostCheck(asyncssh.SSHClient):
    def __init__(self, expected):
        self.expected = expected
        self.presented = None

    def validate_host_public_key(self, host, addr, port, key):
        self.presented = key
        return self.expected == key.export_public_key().decode().strip()


class PersistentTerminal:
    def __init__(self, user_id, profile):
        self.id = secrets.token_hex(24)
        self.user_id = user_id
        self.profile = profile
        self.connection = None
        self.process = None
        self.task = None
        self.history = bytearray()
        self.offset = 0
        self.changed = asyncio.Event()
        self.state = 'starting'
        self.cols, self.rows = 80, 24
        self.ended_at = None

    def info(self):
        return {'id': self.id, 'profile': self.profile, 'state': self.state, 'cols': self.cols, 'rows': self.rows}

    def append(self, chunk):
        self.history.extend(chunk)
        if len(self.history) > TERMINAL_HISTORY_LIMIT:
            trim = len(self.history) - TERMINAL_HISTORY_LIMIT
            del self.history[:trim]
            self.offset += trim
        self.changed.set()
        self.changed = asyncio.Event()

    async def run(self):
        async def read(reader):
            while chunk := await reader.read(16384):
                self.append(chunk)
        try:
            await asyncio.gather(read(self.process.stdout), read(self.process.stderr))
        except (OSError, asyncssh.Error):
            self.append(b'\r\n[SSH connection lost]\r\n')
        finally:
            self.state = 'ended'
            self.ended_at = time.monotonic()
            self.changed.set()
            self.connection.close()
            await self.connection.wait_closed()

    async def stop(self):
        self.state = 'ended'
        self.changed.set()
        if self.connection:
            self.connection.close()
            await self.connection.wait_closed()
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)


async def terminal_list(request):
    return web.json_response({'terminals': [term.info() for term in TERMINALS.values()
                              if term.user_id == request[USER]['id'] and term.state != 'starting']})


async def terminal_delete(request):
    term = TERMINALS.get(request.match_info['id'])
    if not term or term.user_id != request[USER]['id']:
        return error('The terminal does not exist.', 404)
    TERMINALS.pop(term.id, None)
    await term.stop()
    return web.json_response({'ok': True})


async def workspace(request):
    user_id = request[USER]['id']
    if request.method == 'GET':
        with db() as conn:
            row = conn.execute('SELECT data FROM workspaces WHERE user_id=?', (user_id,)).fetchone()
        return web.json_response(json.loads(row['data']) if row else {'windows': []})
    data = await read_json(request)
    if not isinstance(data, dict) or set(data) != {'windows'} or not isinstance(data['windows'], list) or len(data['windows']) > 12:
        return error('Invalid window layout.')
    for window in data['windows']:
        if (not isinstance(window, dict) or window.get('type') not in ('explorer-window', 'users-window', 'terminal-window', 'browser-window', 'status-window', 'files-window', 'trash-window', 'editor-window', 'preview-window', 'search-window', 'activities-window', 'notes-window', 'preferences-window', 'sftp-window', 'cad-window', 'calculator-window', 'taskmanager-window')
                or any(type(window.get(key)) not in (int, float) or not -10000 <= window[key] <= 10000 for key in ('left', 'top', 'width', 'height'))
                or any(type(window.get(key)) is not bool for key in ('hidden', 'maximized'))
                or any(window.get(key) is not None and (not isinstance(window[key], str) or len(window[key]) > 128) for key in ('terminal', 'folder'))):
            return error('Invalid window layout.')
        if 'editorFiles' in window and (not isinstance(window['editorFiles'],list) or len(window['editorFiles'])>100 or any(not isinstance(key,str) or not re.fullmatch(r'[a-f0-9]{32}',key) for key in window['editorFiles'])):
            return error('Invalid editor tabs.')
    with db() as conn:
        conn.execute('INSERT INTO workspaces VALUES (?,?) ON CONFLICT(user_id) DO UPDATE SET data=excluded.data', (user_id, json.dumps(data)))
    return web.json_response({'ok': True})


async def attach_terminal(ws, term, token):
    await ws.send_json({'type': 'connected', **term.info(), 'truncated': term.offset > 0, 'replay_bytes': len(term.history)})

    async def output():
        cursor = term.offset
        while True:
            changed = term.changed
            if cursor < term.offset:
                await ws.send_json({'type': 'reset', 'truncated': True})
                cursor = term.offset
            chunk = bytes(term.history[cursor - term.offset:])
            if chunk:
                cursor += len(chunk)
                await ws.send_bytes(chunk)
            if term.state == 'ended':
                await ws.send_json({'type': 'ended'})
                return
            await changed.wait()

    async def input_stream():
        async for message in ws:
            if not session_valid(SESSIONS.get(token)):
                return
            if message.type == WSMsgType.BINARY and term.state == 'running':
                term.process.stdin.write(message.data)
                await term.process.stdin.drain()
            elif message.type == WSMsgType.TEXT and term.state == 'running':
                command = json.loads(message.data)
                if command.get('type') == 'resize':
                    term.cols = max(20, min(500, int(command['cols'])))
                    term.rows = max(5, min(200, int(command['rows'])))
                    term.process.change_terminal_size(term.cols, term.rows)

    async def expiry():
        while session_valid(SESSIONS.get(token)):
            await asyncio.sleep(1)

    tasks = [asyncio.create_task(output()), asyncio.create_task(input_stream()), asyncio.create_task(expiry())]
    try:
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def terminal(request):
    token = request[TOKEN]
    user_id = request[USER]['id']
    if len(SOCKETS.get(token, set())) >= 8:
        return error('Maximum eight terminals can be open at once.', 429)
    ws = web.WebSocketResponse(heartbeat=25, max_msg_size=65536)
    await ws.prepare(request)
    SOCKETS.setdefault(token, set()).add(ws)
    connection = None
    term = None
    try:
        data = await asyncio.wait_for(ws.receive_json(), 60)
        if not session_valid(SESSIONS.get(token)):
            return ws
        if data.get('terminal'):
            existing = TERMINALS.get(data['terminal'])
            if not existing or existing.user_id != user_id or existing.state == 'starting':
                await ws.send_json({'type': 'error', 'message': 'The terminal does not exist.', 'missing': True})
                return ws
            await attach_terminal(ws, existing, token)
            return ws
        if sum(t.user_id == user_id for t in TERMINALS.values()) >= 8:
            await ws.send_json({'type': 'error', 'message': 'Maximum eight terminals per account. Close a terminal first.'})
            return ws
        with db() as conn:
            row = conn.execute('SELECT * FROM items WHERE id=? AND user_id=? AND kind="profile"', (data.get('profile'), user_id)).fetchone()
            if not row:
                await ws.send_json({'type': 'error', 'message': 'The profile does not exist.'})
                return ws
            profile = dict(row)
            saved = conn.execute('SELECT key FROM hostkeys WHERE host=? AND port=? AND user_id=?', (profile['host'], profile['port'], user_id)).fetchone()
        term = PersistentTerminal(user_id, profile)
        TERMINALS[term.id] = term
        password = data.pop('password', '')
        if not isinstance(password, str) or len(password) > 1024:
            raise ValueError('Invalid password')
        expected = saved['key'] if saved else None
        for attempt in range(2):
            checker = HostCheck(expected)
            try:
                connection = await asyncssh.connect(profile['host'], port=profile['port'], username=profile['username'], password=password, client_keys=[], agent_path=None, config=None, known_hosts=b'', client_factory=lambda: checker, connect_timeout=20, login_timeout=30, keepalive_interval=30, keepalive_count_max=3)
                break
            except asyncssh.HostKeyNotVerifiable:
                if expected or not checker.presented or attempt:
                    await ws.send_json({'type': 'error', 'message': 'The device SSH host key does not match the saved key. The connection was blocked.'})
                    return ws
                await ws.send_json({'type': 'hostkey', 'host': profile['host'], 'port': profile['port'], 'fingerprint': checker.presented.get_fingerprint('sha256')})
                answer = await asyncio.wait_for(ws.receive_json(), 120)
                if answer.get('type') != 'trust' or answer.get('accept') is not True:
                    return ws
                expected = checker.presented.export_public_key().decode().strip()
                with db() as conn:
                    conn.execute('INSERT OR IGNORE INTO hostkeys VALUES (?,?,?,?)', (profile['host'], profile['port'], expected, user_id))
                    expected = conn.execute('SELECT key FROM hostkeys WHERE host=? AND port=? AND user_id=?', (profile['host'], profile['port'], user_id)).fetchone()['key']
        password = None
        if not session_valid(SESSIONS.get(token)) or term.id not in TERMINALS:
            return ws
        term.connection = connection
        term.cols = max(20, min(500, int(data.get('cols', 80))))
        term.rows = max(5, min(200, int(data.get('rows', 24))))
        term.process = await connection.create_process(term_type='xterm-256color', term_size=(term.cols, term.rows), encoding=None)
        if not session_valid(SESSIONS.get(token)) or term.id not in TERMINALS:
            return ws
        term.state = 'running'
        term.task = asyncio.create_task(term.run())
        connection = None  # The persistent terminal now owns the SSH connection.
        await attach_terminal(ws, term, token)
    except asyncssh.PermissionDenied:
        await ws.send_json({'type': 'error', 'message': 'SSH login failed. Check the username and password.'})
    except (asyncio.TimeoutError, OSError, asyncssh.Error):
        if not ws.closed:
            await ws.send_json({'type': 'error', 'message': 'Could not connect. Check the address, port and network, and ensure SSH is enabled.'})
    except (ValueError, TypeError, KeyError):
        if not ws.closed:
            await ws.send_json({'type': 'error', 'message': 'The connection was interrupted or the credentials were invalid.'})
    finally:
        if connection:
            connection.close()
            await connection.wait_closed()
        if term and term.state == 'starting':
            TERMINALS.pop(term.id, None)
        SOCKETS.get(token, set()).discard(ws)
        await ws.close()
    return ws


async def browser_start(request):
    try:
        await BROWSERS.start(request[USER]['id'])
    except BrowserUnavailable as exc:
        return error(str(exc), 503)
    if not session_valid(SESSIONS.get(request[TOKEN])):
        await BROWSERS.stop(request[USER]['id'])
        return error('Log in again.', 401)
    return web.json_response({'url': '/api/browser/view/'})


async def browser_stop(request):
    await BROWSERS.stop(request[USER]['id'])
    return web.json_response({'ok': True})


async def browser_proxy(request):
    entry = BROWSERS.sessions.get(request[USER]['id'])
    if not entry or entry['process'].returncode is not None:
        return error('Open Browser from the desktop to start your session.', 503)
    entry['last_seen'] = time.monotonic()
    websocket = request.headers.get('Upgrade', '').lower() == 'websocket'
    if websocket and request.headers.get('Origin') != ORIGIN:
        return error('Origin not allowed.', 403)
    connector = UnixConnector(path=str(entry['socket']))
    upstream_url = URL('http://localhost' + request.raw_path, encoded=True)
    token = request[TOKEN]
    try:
        async with ClientSession(connector=connector, auto_decompress=False) as client:
            if websocket:
                async with client.ws_connect(upstream_url, max_msg_size=32*1024*1024, heartbeat=25) as upstream:
                    ws = web.WebSocketResponse(max_msg_size=32*1024*1024, heartbeat=25)
                    await ws.prepare(request)
                    entry['clients'] = entry.get('clients', 0) + 1
                    SOCKETS.setdefault(token, set()).add(ws)
                    async def forward(source, target):
                        async for message in source:
                            if message.type == WSMsgType.BINARY:
                                await target.send_bytes(message.data)
                            elif message.type == WSMsgType.TEXT:
                                await target.send_str(message.data)
                            else:
                                break
                    async def check_session():
                        while session_valid(SESSIONS.get(token)):
                            await asyncio.sleep(1)
                    tasks = [asyncio.create_task(forward(ws, upstream)),
                             asyncio.create_task(forward(upstream, ws)), asyncio.create_task(check_session())]
                    try:
                        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                        for task in done:
                            task.result()
                    finally:
                        for task in tasks:
                            task.cancel()
                        await asyncio.gather(*tasks, return_exceptions=True)
                        entry['clients'] = max(0, entry.get('clients', 1) - 1)
                        entry['last_seen'] = time.monotonic()
                        SOCKETS.get(token, set()).discard(ws)
                        await ws.close()
                    return ws
            # Only protocol/content headers pass through. The user's application
            # cookie and authorization headers never enter the browser sandbox.
            headers = {key: value for key, value in request.headers.items()
                       if key.lower() in ('content-type', 'content-length', 'accept', 'range')}
            async with client.request(request.method, upstream_url, headers=headers,
                                      data=request.content, allow_redirects=False) as upstream:
                response_headers = {key: value for key, value in upstream.headers.items()
                                    if key.lower() in ('content-type', 'content-length', 'content-encoding',
                                                       'content-disposition', 'content-range', 'accept-ranges', 'location')}
                response_headers.update({'Cache-Control': 'no-store', 'X-Frame-Options': 'SAMEORIGIN'})
                response = web.StreamResponse(status=upstream.status, headers=response_headers)
                await response.prepare(request)
                async for chunk in upstream.content.iter_chunked(65536):
                    await response.write(chunk)
                await response.write_eof()
                return response
    except (ClientError, OSError):
        if websocket and 'ws' in locals() and ws.prepared:
            await ws.close()
            return ws
        return error('The browser connection was lost. Select Reconnect in the browser window.', 502)


async def worker_control(request):
    data = await read_json(request)
    if data['action'] == 'token':
        await close_token_sockets(data['token'])
    elif data['action'] in ('user', 'remove'):
        user_id = int(data['user_id'])
        await BROWSERS.stop(user_id, remove=data['action'] == 'remove')
        for key, term in list(TERMINALS.items()):
            if term.user_id == user_id:
                await term.stop()
                TERMINALS.pop(key, None)
    elif data['action'] in ('freeze', 'thaw'):
        if data['action'] == 'freeze': await BROWSERS.freeze()
        else: await BROWSERS.thaw()
    elif data['action'] == 'status':
        return web.json_response(runtime_data())
    else:
        return error('Unknown control action')
    return web.json_response({'ok': True})


def runtime_data(user_id=None):
    users = {}
    for term in TERMINALS.values():
        if user_id is None or term.user_id == user_id:
            entry = users.setdefault(term.user_id, {'terminals': 0, 'browsers': 0})
            entry['terminals'] += 1
    if BROWSERS:
        for uid, browser in BROWSERS.sessions.items():
            if user_id is None or uid == user_id:
                entry = users.setdefault(uid, {'terminals': 0, 'browsers': 0})
                entry['browsers'] = int(browser['process'].returncode is None)
                if hasattr(BROWSERS, 'resources'): entry.update(BROWSERS.resources.usage(uid))
    return {'users': [{'id': key, **value} for key,value in users.items()],
            'limits': {'terminals_per_user': 8, 'browsers_total': 3, 'browser_memory_mib': 1536, 'browser_cpu_cores': 1.5, 'browser_disconnected_hours': 24}, 'session_worker': WORKER_MODE}


async def runtime_status(request):
    # Owners see counts, never URLs, terminal output, cookies or connection details.
    return web.json_response(runtime_data(None if is_owner(request[USER]) else request[USER]['id']))


async def health(request):
    status = {'web': 'ok', 'sessions': 'ok', 'backup': None}
    if WORKER_SOCKET:
        try:
            await session_proxy.control(WORKER_SOCKET, 'status')
        except (ClientError, OSError, asyncio.TimeoutError):
            status['sessions'] = 'unavailable'
    if is_owner(request[USER]):
        path = STATE / 'backup-status.json'
        if path.exists(): status['backup'] = json.loads(path.read_text())
        disk = shutil.disk_usage(STATE)
        status['disk_free_bytes'] = disk.free
    return web.json_response(status)


async def housekeeping(app):
    async def loop():
        while True:
            await asyncio.sleep(5)
            for token, session in list(SESSIONS.items()):
                if not session_valid(session): await revoke(token)
            for key, term in list(TERMINALS.items()):
                if term.state == 'ended' and term.ended_at and time.monotonic() - term.ended_at > 86400:
                    TERMINALS.pop(key, None)
            if BROWSERS and not maintenance_active():
                if hasattr(BROWSERS, 'thaw'): await BROWSERS.thaw()
                for uid, entry in list(BROWSERS.sessions.items()):
                    usage = BROWSERS.resources.usage(uid) if hasattr(BROWSERS, 'resources') else {}
                    if usage.get('memory_bytes', 0) > 1536 * 1024**2 or shutil.disk_usage(STATE).free < 512 * 1024**2:
                        logging.warning('Browser stopped by memory/disk watchdog: user %s', uid)
                        await BROWSERS.stop(uid)
                        continue
                    if not entry.get('clients', 0) and time.monotonic() - entry.get('last_seen', time.monotonic()) > 86400:
                        await BROWSERS.stop(uid)
    task = asyncio.create_task(loop())
    yield
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)


async def shutdown(app):
    if BROWSERS:
        await BROWSERS.shutdown()
    for term in list(TERMINALS.values()):
        await term.stop()
    TERMINALS.clear()
    for token in list(SOCKETS):
        await close_token_sockets(token)


def make_app():
    global BROWSERS, SESSIONS, FILES
    initialize()
    FILES = FileStore(STATE, db, lambda request: session_valid(SESSIONS.get(request[TOKEN])))
    FILES.initialize(clean_uploads=not WORKER_MODE)
    personal=PersonalStore(FILES);personal.initialize()
    if WORKER_MODE or WORKER_SOCKET:
        SESSIONS = SessionStore(STATE / 'admin.sqlite3')
    BROWSERS = None if WORKER_SOCKET else BrowserRuntime(STATE)
    app = web.Application(middlewares=[guard], client_max_size=16384)
    app.router.add_post('/api/login', login)
    sftp=SFTPTools(sys.modules[__name__])
    app.router.add_post('/api/sftp',sftp.handle)
    app.router.add_post('/api/sftp/editor',sftp.handle)
    app.router.add_get('/api/sessions',personal_sessions)
    app.router.add_delete('/api/sessions/{id}',personal_sessions)
    app.router.add_post('/api/logout', logout)
    app.router.add_get('/api/session', session_info)
    app.router.add_post('/api/password', change_password)
    app.router.add_get('/api/users', users)
    app.router.add_post('/api/users', create_user)
    app.router.add_patch('/api/users/{id}', update_user)
    app.router.add_delete('/api/users/{id}', delete_user)
    app.router.add_post('/api/users/{id}/password', reset_password)
    app.router.add_get('/api/desktop', desktop)
    app.router.add_put('/api/desktop', desktop)
    app.router.add_get('/api/items', items)
    app.router.add_post('/api/items', save_item)
    app.router.add_put('/api/items/{id}', save_item)
    app.router.add_delete('/api/items/{id}', delete_item)
    app.router.add_get('/api/workspace', workspace)
    app.router.add_put('/api/workspace', workspace)
    app.router.add_get('/api/health', health)
    monitor=TaskMonitor(sys.modules[__name__])
    app.router.add_get('/api/taskmanager',monitor.handle)
    def file_handler(method):
        async def handle(request):
            request[FILE_USER] = request[USER]
            try: return await getattr(FILES, method)(request)
            except web.HTTPException as exc:
                return error(exc.text or exc.reason, exc.status)
        return handle
    def personal_handler(method):
        async def handle(request):
            request[FILE_USER]=request[USER]
            return await getattr(personal,method)(request)
        return handle
    app.router.add_get('/api/preferences',personal_handler('preferences'))
    app.router.add_put('/api/preferences',personal_handler('preferences'))
    app.router.add_get('/api/documents',personal_handler('documents'))
    app.router.add_get('/api/documents/{key}',personal_handler('documents'))
    app.router.add_put('/api/documents/{key}',personal_handler('documents'))
    app.router.add_delete('/api/documents/{key}',personal_handler('documents'))
    app.router.add_post('/api/files/copy',file_handler('copy'))
    app.router.add_get('/api/files/archive',file_handler('archive'))
    app.router.add_get('/api/files', file_handler('list'))
    app.router.add_post('/api/files/folders', file_handler('create'))
    app.router.add_post('/api/files/upload', file_handler('upload'))
    app.router.add_delete('/api/files/trash', file_handler('purge'))
    app.router.add_get('/api/files/{id}/download', file_handler('download'))
    app.router.add_get('/api/files/{id}/content', file_handler('content'))
    app.router.add_put('/api/files/{id}/content', file_handler('content'))
    app.router.add_patch('/api/files/{id}', file_handler('change'))
    app.router.add_post('/api/files/{id}/trash', file_handler('trash'))
    app.router.add_post('/api/files/{id}/restore', file_handler('restore'))
    app.router.add_delete('/api/files/{id}', file_handler('purge'))
    app.router.add_patch('/api/users/{id}/storage', file_handler('quota'))

    if WORKER_SOCKET:
        async def forward(request): return await session_proxy.proxy(request, WORKER_SOCKET)
        for path in ('/api/terminals', '/api/terminals/{id}', '/api/terminal', '/api/browser/start', '/api/browser/stop', '/api/browser/view/{path:.*}', '/api/runtime'):
            app.router.add_route('*', path, forward)
    else:
        app.router.add_get('/api/terminals', terminal_list)
        app.router.add_delete('/api/terminals/{id}', terminal_delete)
        app.router.add_post('/api/browser/start', browser_start)
        app.router.add_post('/api/browser/stop', browser_stop)
        app.router.add_route('*', '/api/browser/view/{path:.*}', browser_proxy)
        app.router.add_get('/api/terminal', terminal)
        app.router.add_get('/api/runtime', runtime_status)
    if WORKER_MODE:
        app.router.add_post('/internal/control', worker_control)
    app.cleanup_ctx.append(housekeeping)
    app.on_shutdown.append(shutdown)
    return app


if __name__ == '__main__':
    os.umask(0o077)
    if WORKER_MODE:
        web.run_app(make_app(), path=os.environ.get('WIN2K_LISTEN_SOCKET', '/run/win2k-sessions/worker.sock'), access_log=None)
    else:
        web.run_app(make_app(), host='127.0.0.1', port=int(os.environ.get('WIN2K_PORT', 8765)), access_log=None)
