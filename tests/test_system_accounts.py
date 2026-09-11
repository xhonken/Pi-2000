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

    def test_pending_deletion_removes_only_unused_reservation(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(app,'STATE',Path(folder)/'web'), patch.object(broker,'STATE',Path(folder)/'web'), patch.object(broker,'ROOT',Path(folder)/'registry'):
            app.initialize(initial_password='fixture-password-123')
            broker.setup_registry()
            with app.db() as db:
                uid=db.execute("INSERT INTO users(username,salt,hash,active,account_state) VALUES ('pending','','',0,'pending')").lastrowid
            owner=broker.user(1)
            with broker.database(broker.ROOT/'accounts.sqlite3') as db:
                db.execute("INSERT INTO bindings(web_id,name,home,managed,creator) VALUES (1,'creator',?,1,1)",(str(Path(folder)/'creator'),))
                db.execute("INSERT INTO bindings(web_id,name,home,managed) VALUES (?,'pending',?,1)",(uid,str(Path(folder)/'missing-home')))
            with patch.object(broker,'actor',return_value=owner), patch.object(broker.pwd,'getpwnam',return_value=object()):
                with self.assertRaises(broker.Denied): broker.dispatch({'operation':'delete','user_id':uid,'confirm':'pending'})
            self.assertIsNotNone(broker.binding(uid))
            with patch.object(broker,'actor',return_value=owner), patch.object(broker.pwd,'getpwnam',side_effect=KeyError):
                broker.dispatch({'operation':'delete','user_id':uid,'confirm':'pending'})
            self.assertIsNone(broker.binding(uid))

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
