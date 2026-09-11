import sys
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
import app
import account_service as broker

class SystemAccountTests(unittest.TestCase):
    def test_named_creator_protection_survives_restart(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(app,'STATE',Path(folder)):
            app.initialize(initial_password='fixture-password-123',initial_username='creator-test')
            app.initialize()
            with app.db() as db:
                creator=dict(db.execute('SELECT * FROM users WHERE is_creator=1').fetchone())
                self.assertEqual(creator['username'],'creator-test')
                self.assertTrue(app.is_owner(creator))
                for sql in ('DELETE FROM users WHERE is_creator=1',"UPDATE users SET active=0 WHERE is_creator=1","UPDATE users SET role='user' WHERE is_creator=1",'UPDATE users SET is_creator=0 WHERE is_creator=1'):
                    with self.assertRaises(sqlite3.IntegrityError):db.execute(sql)
                db.execute("INSERT INTO users(username,salt,hash) VALUES ('admin','','')")
                with self.assertRaises(sqlite3.IntegrityError):db.execute("UPDATE users SET is_creator=1 WHERE username='admin'")
                self.assertFalse(app.is_owner(dict(db.execute("SELECT * FROM users WHERE username='admin'").fetchone())))

    def test_password_byte_limit_and_control_characters(self):
        broker.password('å'*256,True)
        for value in ['å'*257,'short','abcde\n123456789','x'*513]:
            with self.assertRaises(broker.Denied):broker.password(value,True)

    def test_foreign_uid_cannot_be_used(self):
        import pwd
        account=pwd.getpwuid(__import__('os').getuid())
        with self.assertRaises(broker.Denied):broker.identity({'name':account.pw_name,'uid':account.pw_uid+1,'home':account.pw_dir})

    def test_missing_binding_does_not_grant_creator(self):
        with patch.object(broker,'binding',return_value=None):
            self.assertFalse(broker.creator({'id':1,'is_creator':1}))
