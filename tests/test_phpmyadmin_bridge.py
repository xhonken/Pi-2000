import asyncio
import hashlib
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
from aiohttp import web
from phpmyadmin_bridge import PhpMyAdmin, params, record

class Request(dict):
    match_info={'sid':'a'*48}

class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.profile={'host':'127.0.0.1','port':3306}
        self.app=SimpleNamespace(TOKEN='token',SESSIONS={'owner':{'active':True}},session_valid=lambda s:s)
        self.db=SimpleNamespace(profile=Mock(return_value=(self.profile,'encrypted')))
        self.bridge=PhpMyAdmin(self.app,self.db)
        self.bridge.sessions['a'*48]=dict(token='owner',uid=7,profile_id='connection',
            fingerprint=hashlib.sha256(json.dumps([self.profile,'encrypted']).encode()).hexdigest(),
            expires=time.monotonic()+100)
    def test_other_login_cannot_use_session(self):
        with self.assertRaises(web.HTTPUnauthorized):
            self.bridge.session(Request(token='another-login'))
        self.db.profile.assert_not_called()
    def test_revoked_login_expires_immediately(self):
        self.app.SESSIONS.clear()
        with self.assertRaises(web.HTTPUnauthorized):
            self.bridge.session(Request(token='owner'))
        self.assertFalse(self.bridge.sessions)
    def test_profile_changes_invalidate_session(self):
        self.db.profile.return_value=({'host':'different'},'encrypted')
        with self.assertRaises(web.HTTPUnauthorized):
            self.bridge.session(Request(token='owner'))
        self.assertFalse(self.bridge.sessions)
    def test_profile_owner_rechecked(self):
        self.bridge.session(Request(token='owner'))
        self.db.profile.assert_called_once_with(7,'connection')
    def test_expired_session_cannot_resume(self):
        self.bridge.sessions['a'*48]['expires']=0
        with self.assertRaises(web.HTTPUnauthorized):
            self.bridge.session(Request(token='owner'))
    def test_disconnect_does_not_interrupt_running_write(self):
        self.bridge.sessions['a'*48]['running']=True
        with self.assertRaises(web.HTTPConflict):
            asyncio.run(self.bridge.disconnect(Request(token='owner')))
        self.assertIn('a'*48,self.bridge.sessions)
    def test_fastcgi_binary_lengths(self):
        self.assertEqual(record(5,b'abc'),b'\x01\x05\x00\x01\x00\x03\x00\x00abc')
        self.assertEqual(params({'A':'B'}),b'\x01\x01AB')
        self.assertEqual(params({'A':'x'*128})[:5],b'\x01\x80\x00\x00\x80')

if __name__=='__main__':unittest.main()
