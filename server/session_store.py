"""Shared login sessions. Only token digests are persisted on disk."""
from collections.abc import MutableMapping
from contextlib import contextmanager
import hashlib
import json
import sqlite3
import time

class SessionStore(MutableMapping):
    def __init__(self, path):
        self.path = path
        with self.connect() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS login_sessions (token TEXT PRIMARY KEY, data TEXT NOT NULL, expires REAL NOT NULL)')
            conn.execute('DELETE FROM login_sessions WHERE expires < ?', (time.time(),))

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=15)
        try:
            with conn: yield conn
        finally:
            conn.close()

    @staticmethod
    def key(token):
        # Iteration returns opaque database keys, never usable login cookies.
        return token if token.startswith('sha256:') else 'sha256:' + hashlib.sha256(token.encode()).hexdigest()

    def __getitem__(self, token):
        with self.connect() as conn:
            row = conn.execute('SELECT data FROM login_sessions WHERE token=?', (self.key(token),)).fetchone()
        if not row:
            raise KeyError(token)
        return json.loads(row[0])

    def __setitem__(self, token, data):
        with self.connect() as conn:
            conn.execute('INSERT OR REPLACE INTO login_sessions VALUES (?,?,?)', (self.key(token), json.dumps(data), data['expires']))

    def __delitem__(self, token):
        with self.connect() as conn:
            if not conn.execute('DELETE FROM login_sessions WHERE token=?', (self.key(token),)).rowcount:
                raise KeyError(token)

    def __iter__(self):
        with self.connect() as conn:
            return iter([row[0] for row in conn.execute('SELECT token FROM login_sessions')])

    def __len__(self):
        with self.connect() as conn:
            return conn.execute('SELECT COUNT(*) FROM login_sessions').fetchone()[0]
