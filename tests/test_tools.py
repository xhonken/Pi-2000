import io
import json
import zipfile
import unittest
from pathlib import Path
import asyncssh
import test_server
import app

class ToolsTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=test_server.ServerTests.asyncSetUp
    asyncTearDown=test_server.ServerTests.asyncTearDown
    create_account=test_server.ServerTests.create_account
    login_account=test_server.ServerTests.login_account
    async def upload(self,name='test.txt',body=b'original',parent='files'):
        r=await self.client.post('/api/files/upload',headers=self.headers,params={'name':name,'parent':parent},data=body)
        self.assertEqual(r.status,201);return (await r.json())['id']
    async def test_documents_quota_privacy_and_conflict(self):
        await self.create_account();alice=await self.login_account()
        r=await self.client.put('/api/documents/notes',headers=self.headers,json={'text':'private'});self.assertEqual(r.status,200);version=(await r.json())['version']
        r=await self.client.get('/api/documents/notes',headers=alice);self.assertIsNone((await r.json())['data'])
        self.assertEqual((await self.client.put('/api/documents/notes',headers=self.headers,json={'text':'stale'})).status,409)
        with app.db() as db:db.execute('UPDATE users SET storage_quota=30 WHERE id=1')
        self.assertEqual((await self.client.put('/api/documents/notes',headers={**self.headers,'If-Match':version},json={'text':'x'*40})).status,409)
        r=await self.client.get('/api/files',headers=self.headers);usage=await r.json();self.assertGreater(usage['documents'],0)
        self.assertEqual((await self.client.post('/api/files/upload?name=too-large.txt',headers=self.headers,data=b'x'*30)).status,413)
        await self.client.delete('/api/documents/notes',headers=self.headers)
        self.assertEqual((await (await self.client.get('/api/files',headers=self.headers)).json())['used'],0)
    async def test_copy_preserves_content_after_edit_and_zip_paths(self):
        folder=(await (await self.client.post('/api/files/folders',headers=self.headers,json={'name':'Projekt'})).json())['id']
        key=await self.upload(parent=folder)
        response=await self.client.post('/api/files/copy',headers=self.headers,json={'ids':[folder,key],'parent':'desktop'});self.assertEqual(response.status,200)
        copied=(await response.json())['ids'][0]
        listing=(await (await self.client.get('/api/files',headers=self.headers)).json())['items'];copyfile=next(x for x in listing if x['parent']==copied)
        content=await (await self.client.get('/api/files/'+key+'/content',headers=self.headers)).json()
        await self.client.put('/api/files/'+key+'/content',headers={**self.headers,'If-Match':content['version']},data=b'changed')
        self.assertEqual(await (await self.client.get('/api/files/'+copyfile['id']+'/download',headers=self.headers)).read(),b'original')
        response=await self.client.get('/api/files/archive',headers=self.headers,params={'ids':copied});self.assertEqual(response.status,200)
        with zipfile.ZipFile(io.BytesIO(await response.read())) as archive:self.assertEqual(archive.read('Projekt/test.txt'),b'original')
        await self.create_account();alice=await self.login_account()
        self.assertEqual((await self.client.get('/api/files/archive',headers=alice,params={'ids':key})).status,404)
        self.assertEqual((await self.client.post('/api/files/copy',headers=alice,json={'ids':[key]})).status,404)
    async def test_preferences_sessions_private(self):
        await self.create_account();alice=await self.login_account()
        response=await self.client.put('/api/preferences',headers=alice,json={'fontSize':16,'favorites':['app:cad']});self.assertEqual(response.status,200)
        self.assertEqual(await (await self.client.get('/api/preferences',headers=self.headers)).json(),{})
        sessions=(await (await self.client.get('/api/sessions',headers=alice)).json())['sessions'];self.assertEqual(len(sessions),1);self.assertTrue(sessions[0]['current'])
        self.assertEqual((await self.client.delete('/api/sessions/'+sessions[0]['id'],headers=self.headers)).status,404)
        self.assertEqual((await self.client.delete('/api/sessions/'+sessions[0]['id'],headers=alice)).status,200)
        self.assertEqual((await self.client.get('/api/files',headers=alice)).status,401)
    async def test_sftp_host_trust_transfer_and_overwrite(self):
        remote=app.STATE/'remote';remote.mkdir();(remote/'source.txt').write_bytes(b'from remote')
        server=await asyncssh.create_server(test_server.SSHServer,'127.0.0.1',0,server_host_keys=[self.key],sftp_factory=lambda channel:asyncssh.SFTPServer(channel,chroot=str(remote)))
        try:
            profile=(await (await self.client.post('/api/items',headers=self.headers,json={'kind':'profile','name':'SFTP','host':'127.0.0.1','port':server.get_port(),'username':'pi'})).json())['id']
            data={'profile':profile,'password':'ssh-test-password','action':'list','path':'.'}
            r=await self.client.post('/api/sftp',headers=self.headers,json=data);self.assertEqual(r.status,409);data['trust']=(await r.json())['fingerprint']
            r=await self.client.post('/api/sftp',headers=self.headers,json=data);self.assertEqual(r.status,200)
            key=await self.upload()
            r=await self.client.post('/api/sftp',headers=self.headers,json={**data,'action':'send','file':key,'path':'target.txt'});self.assertEqual(r.status,200);self.assertEqual((remote/'target.txt').read_bytes(),b'original')
            (remote/'target.txt').write_bytes(b'keep me')
            r=await self.client.post('/api/sftp',headers=self.headers,json={**data,'action':'send','file':key,'path':'target.txt'});self.assertGreaterEqual(r.status,400);self.assertEqual((remote/'target.txt').read_bytes(),b'keep me')
            r=await self.client.post('/api/sftp',headers=self.headers,json={**data,'action':'send','file':key,'path':'target.txt','overwrite':True});self.assertEqual(r.status,200)
            r=await self.client.post('/api/sftp',headers=self.headers,json={**data,'action':'receive','path':'source.txt','parent':'files'});self.assertEqual(r.status,200);received=(await r.json())['id']
            self.assertEqual(await (await self.client.get('/api/files/'+received+'/download',headers=self.headers)).read(),b'from remote')
            await self.create_account();alice=await self.login_account();self.assertEqual((await self.client.post('/api/sftp',headers=alice,json=data)).status,404)
        finally:server.close();await server.wait_closed()
    async def test_sftp_editor_conflicts_permissions_create_and_privacy(self):
        remote=app.STATE/'editor-remote';remote.mkdir();source=remote/'code.py';source.write_text('print("hej")\n');source.chmod(0o751)
        (remote/'binary').write_bytes(b'\xff\x00');(remote/'large').write_bytes(b'a'*1048577)
        (remote/'link.py').symlink_to('code.py')
        server=await asyncssh.create_server(test_server.SSHServer,'127.0.0.1',0,server_host_keys=[self.key],sftp_factory=lambda channel:asyncssh.SFTPServer(channel,chroot=str(remote)))
        try:
            profile=(await (await self.client.post('/api/items',headers=self.headers,json={'kind':'profile','name':'Editor SFTP','host':'127.0.0.1','port':server.get_port(),'username':'pi'})).json())['id']
            data={'profile':profile,'password':'ssh-test-password','path':'code.py','trust':self.key.get_fingerprint('sha256')}
            async def call(action,**kw):return await self.client.post('/api/sftp/editor',headers=self.headers,json={**data,'action':action,**kw})
            r=await call('read');self.assertEqual(r.status,200,await r.text());opened=await r.json()
            r=await call('write',version=opened['version'],text='print("sparad")\n');self.assertEqual(r.status,200,await r.text());saved=await r.json();self.assertEqual(source.read_text(),'print("sparad")\n');self.assertEqual(source.stat().st_mode&0o777,0o751)
            source.write_text('external change')
            r=await call('write',version=saved['version'],text='wrong');self.assertEqual(r.status,409);self.assertEqual(source.read_text(),'external change')
            r=await call('write',version='',text='do not replace');self.assertEqual(r.status,409)
            r=await call('write',path='new.py',version='',text='x'*20000);self.assertEqual(r.status,200,await r.text());self.assertEqual((remote/'new.py').stat().st_size,20000)
            r=await call('read',path='link.py');self.assertEqual(r.status,200);self.assertEqual((await r.json())['path'],'/code.py')
            r=await call('write',path='link.py',version=saved['version'],text='wrong');self.assertEqual(r.status,400);self.assertTrue((remote/'link.py').is_symlink())
            for path in ['binary','large']:
                r=await call('read',path=path);self.assertEqual(r.status,400)
            r=await call('write',path='new.py',version='bad',text='bad');self.assertEqual(r.status,400)
            await self.create_account();alice=await self.login_account();r=await self.client.post('/api/sftp/editor',headers=alice,json={**data,'action':'read'});self.assertEqual(r.status,404)
            self.assertFalse(list(remote.glob('.win2k-*')))
        finally:server.close();await server.wait_closed()
