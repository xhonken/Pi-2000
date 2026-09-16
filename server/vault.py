"""Account-scoped opaque client-encrypted vaults. No server decryption keys."""
import base64
import binascii
import json
import re
from aiohttp import web

MAX_BYTES = 4 * 1024 * 1024
MAX_ENTRIES = 500
HEX = re.compile(r'[a-f0-9]{32}')
KDF = {'name': 'argon2id', 'memory': 65536, 'iterations': 3, 'parallelism': 1}


def exact(value, fields):
    if not isinstance(value, dict) or set(value) != set(fields):
        raise ValueError('Unsupported vault structure')


def binary(value, minimum, maximum):
    if not isinstance(value, str) or len(value) > (maximum + 2) // 3 * 4:
        raise ValueError('Invalid encrypted field')
    try:
        decoded = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error):
        raise ValueError('Invalid encrypted field') from None
    if not minimum <= len(decoded) <= maximum or base64.b64encode(decoded).decode() != value:
        raise ValueError('Invalid encrypted field')


def envelope(value, minimum=16, maximum=131072):
    exact(value, ('iv', 'data'))
    binary(value['iv'], 12, 12)
    binary(value['data'], minimum, maximum)


def validate(payload):
    exact(payload, ('format', 'id', 'kdf', 'a', 'b', 'recovery', 'index', 'entries'))
    if type(payload['format']) is not int or payload['format'] != 1 or not isinstance(payload['id'], str) or not HEX.fullmatch(payload['id']):
        raise ValueError('Unsupported vault format')
    if payload['kdf'] != KDF:
        raise ValueError('Unsupported password derivation settings')
    for level in ('a', 'b'):
        exact(payload[level], ('salt', 'wrapped'))
        binary(payload[level]['salt'], 16, 16)
        envelope(payload[level]['wrapped'], 48, 48)
    if payload['a']['salt'] == payload['b']['salt']:
        raise ValueError('Separate password salts are required')
    envelope(payload['recovery'], 80, 80)
    envelope(payload['index'], 16, 262144)
    if not isinstance(payload['entries'], dict) or len(payload['entries']) > MAX_ENTRIES:
        raise ValueError('Too many vault entries')
    for key, item in payload['entries'].items():
        if not HEX.fullmatch(key):
            raise ValueError('Invalid entry identifier')
        envelope(item)


class Vault:
    def __init__(self, app):
        self.app = app

    def initialize(self):
        with self.app.db() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS vaults (
                user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                revision INTEGER NOT NULL, data TEXT NOT NULL, size INTEGER NOT NULL)''')

    def owner(self, request):
        uid = self.app.require_current(request)['id']
        # This header is a stale-client guard, never authority to select an owner.
        if request.headers.get('X-Vault-Owner') != str(uid):
            raise web.HTTPForbidden(text='The signed-in account changed. Close Vault and sign in again.')
        if request.query:
            raise web.HTTPBadRequest(text='Vault does not accept account selectors.')
        return uid

    async def handle(self, request):
        uid = self.owner(request)
        if request.method == 'GET':
            with self.app.db() as db:
                row = db.execute('SELECT revision,data FROM vaults WHERE user_id=?', (uid,)).fetchone()
            value = {'owner': uid, 'revision': row['revision'] if row else 0}
            if request.path != '/api/vault/status':
                value['vault'] = json.loads(row['data']) if row else None
            return web.json_response(value, headers={'Cache-Control': 'no-store'})
        raw = bytearray()
        async for chunk in request.content.iter_chunked(65536):
            raw.extend(chunk)
            if len(raw) > MAX_BYTES:
                raise web.HTTPRequestEntityTooLarge(max_size=MAX_BYTES, actual_size=len(raw))
        uid = self.owner(request)  # Revalidate after all awaited body reads.
        payload = json.loads(raw)
        try:
            validate(payload)
        except ValueError as exc:
            raise web.HTTPBadRequest(text=str(exc)) from None
        data = json.dumps(payload, separators=(',', ':'))
        size = len(data.encode())
        with self.app.FILES.mutation(), self.app.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT revision,size FROM vaults WHERE user_id=?', (uid,)).fetchone()
            revision = row['revision'] if row else 0
            if request.headers.get('If-Match') != str(revision):
                raise web.HTTPConflict(text='Vault changed in another window. Lock and reload before saving.')
            usage = self.app.FILES.usage(db, uid)
            if usage['used'] + usage['reserved'] - (row['size'] if row else 0) + size > usage['quota']:
                raise web.HTTPConflict(text='Vault exceeds your private storage quota.')
            db.execute('''INSERT INTO vaults VALUES(?,?,?,?) ON CONFLICT(user_id)
                DO UPDATE SET revision=excluded.revision,data=excluded.data,size=excluded.size''',
                (uid, revision + 1, data, size))
        return web.json_response({'owner': uid, 'revision': revision + 1})
