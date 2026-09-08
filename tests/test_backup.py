import json
from contextlib import closing
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
from backup import snapshot, restore

class BackupTests(unittest.IsolatedAsyncioTestCase):
    async def test_snapshot_restores_database_profiles_and_omits_login_tokens(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);state=root/'state';state.mkdir()
            with closing(sqlite3.connect(state/'admin.sqlite3')) as db:
                db.executescript("CREATE TABLE users(id INTEGER PRIMARY KEY,name TEXT); INSERT INTO users VALUES(1,'alice'); CREATE TABLE login_sessions(token TEXT); INSERT INTO login_sessions VALUES('secret');")
            with closing(sqlite3.connect(state/'admin.sqlite3')) as db:
                db.executescript("CREATE TABLE files(id TEXT,state TEXT,content_key TEXT); INSERT INTO files VALUES('original','live','kept'); INSERT INTO files VALUES('pending','upload',NULL);")
            files=state/'files/1';files.mkdir(parents=True)
            (files/'kept').write_bytes(b'uploaded-file-fixture')
            (files/'pending.part').write_bytes(b'incomplete')
            profile=state/'browsers/1/chromium/Default';profile.mkdir(parents=True)
            (profile/'Cookies').write_bytes(b'private-cookie-fixture')
            (profile/'Cache').mkdir();(profile/'Cache/skip').write_text('cache')
            (state/'database-credentials.key').write_bytes(b'private-credential-key-fixture')
            archive=await snapshot(state,root/'backup','',None)
            dest=root/'restored';restore(archive,dest)
            self.assertEqual((dest/'state/database-credentials.key').read_bytes(),b'private-credential-key-fixture')
            self.assertEqual((dest/'state/database-credentials.key').stat().st_mode & 0o777,0o600)
            with closing(sqlite3.connect(dest/'state/admin.sqlite3')) as db:
                self.assertEqual(db.execute('SELECT name FROM users').fetchone()[0],'alice')
                self.assertEqual(db.execute('SELECT COUNT(*) FROM login_sessions').fetchone()[0],0)
            self.assertEqual((dest/'state/files/1/kept').read_bytes(),b'uploaded-file-fixture')
            self.assertFalse((dest/'state/files/1/pending.part').exists())
            with closing(sqlite3.connect(dest/'state/admin.sqlite3')) as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM files').fetchone()[0],1)
                self.assertEqual(db.execute('SELECT content_key FROM files').fetchone()[0],'kept')
            self.assertEqual((dest/'state/browsers/1/chromium/Default/Cookies').read_bytes(),b'private-cookie-fixture')
            self.assertFalse((dest/'state/browsers/1/chromium/Default/Cache').exists())
            self.assertTrue(json.loads((state/'backup-status.json').read_text())['verified_restore'])
            with archive.open('ab') as f:f.write(b'corruption')
            with self.assertRaisesRegex(RuntimeError,'checksum'):restore(archive,root/'bad-restore')
