import asyncio
import fcntl
import json
import io
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
import test_server
import app

# Reuse the account fixture without inheriting its unrelated test methods.
class FileTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=test_server.ServerTests.asyncSetUp
    asyncTearDown=test_server.ServerTests.asyncTearDown

    async def upload(self,name,body=b'private contents',parent='files',headers=None):
        return await self.client.post('/api/files/upload',params={'name':name,'parent':parent},headers=headers or self.headers,data=body)

    async def folder(self,name,parent='files'):
        response=await self.client.post('/api/files/folders',headers=self.headers,json={'name':name,'parent':parent})
        self.assertEqual(response.status,201)
        return (await response.json())['id']

    async def user(self):
        response=await self.client.post('/api/users',headers=self.headers,json={'username':'alice','password':'alice-password-123'})
        uid=(await response.json())['id']
        response=await self.client.post('/api/login',headers=self.origin,json={'username':'alice','password':'alice-password-123'})
        return uid,{**self.origin,'Cookie':f"{app.COOKIE}={response.cookies[app.COOKIE].value}"}

    async def test_private_download_moves_and_admin_quota(self):
        uid,alice=await self.user()
        self.assertEqual((await (await self.client.get('/api/files',headers=alice)).json())['quota'],50*1024**2)
        folder=await self.folder('Privat')
        response=await self.upload('sida.html',b'<script>bad()</script>',folder)
        self.assertEqual(response.status,201);key=(await response.json())['id']
        self.assertEqual((await self.client.get('/api/files',headers=alice)).status,200)
        self.assertEqual((await (await self.client.get('/api/files',headers=alice)).json())['items'],[])
        for method,url,payload in [('GET',f'/api/files/{key}/download',None),('PATCH',f'/api/files/{key}',{'parent':'desktop'}),('POST',f'/api/files/{key}/trash',{}),('DELETE',f'/api/files/{key}',None),('POST',f'/api/files/{key}/restore',{})]:
            response=await self.client.request(method,url,headers=alice,json=payload)
            self.assertEqual(response.status,404)
        response=await self.upload('alien.txt',parent=folder,headers=alice);self.assertEqual(response.status,404)
        response=await self.client.get(f'/api/files/{key}/download',headers=self.headers)
        self.assertEqual(await response.read(),b'<script>bad()</script>')
        self.assertIn('attachment',response.headers['Content-Disposition'])
        self.assertEqual(response.headers['Content-Type'],'application/octet-stream')
        response=await self.client.patch(f'/api/users/{uid}/storage',headers=alice,json={'quota_mb':100})
        self.assertEqual(response.status,403)
        response=await self.client.patch(f'/api/users/{uid}/storage',headers=self.headers,json={'quota_mb':100})
        self.assertEqual(response.status,200)
        self.assertEqual((await (await self.client.get('/api/files',headers=alice)).json())['quota'],100*1024**2)

    async def test_added_admin_can_set_own_and_regular_user_quota(self):
        uid,_=await self.user()
        response=await self.client.patch(f'/api/users/{uid}',headers=self.headers,json={'role':'admin'})
        self.assertEqual(response.status,200)
        response=await self.client.post('/api/login',headers=self.origin,json={'username':'alice','password':'alice-password-123'})
        added_admin={**self.origin,'Cookie':f"{app.COOKIE}={response.cookies[app.COOKIE].value}"}
        response=await self.client.post('/api/users',headers=added_admin,json={'username':'bob','password':'bob-password-123'})
        self.assertEqual(response.status,201);other=(await response.json())['id']
        for target in (uid,other):
            response=await self.client.patch(f'/api/users/{target}/storage',headers=added_admin,json={'quota_mb':150})
            self.assertEqual(response.status,200)
        listing=await (await self.client.get('/api/users',headers=added_admin)).json()
        for target in (uid,other):
            self.assertEqual(next(row for row in listing['users'] if row['id']==target)['storage_quota'],150*1024**2)
        response=await self.client.patch('/api/users/1/storage',headers=added_admin,json={'quota_mb':150})
        self.assertEqual(response.status,403)

    async def test_quota_includes_trash_and_permanent_delete_frees_space(self):
        with app.db() as conn:conn.execute('UPDATE users SET storage_quota=12 WHERE id=1')
        response=await self.upload('first.bin',b'12345678');self.assertEqual(response.status,201);key=(await response.json())['id']
        self.assertEqual((await self.upload('second.bin',b'12345')).status,413)
        await self.client.post(f'/api/files/{key}/trash',headers=self.headers,json={})
        self.assertEqual((await self.upload('second.bin',b'12345')).status,413)
        self.assertEqual((await self.client.get(f'/api/files/{key}/download',headers=self.headers)).status,404)
        await self.client.delete('/api/files/trash',headers=self.headers)
        self.assertFalse(app.FILES.blob(1,key).exists())
        self.assertEqual((await self.upload('second.bin',b'12345')).status,201)
        listing=await (await self.client.get('/api/files',headers=self.headers)).json();self.assertEqual(listing['used'],5)

    async def test_folder_trash_restore_collision_and_missing_parent(self):
        parent=await self.folder('Projekt','desktop');child=await self.folder('Dokument',parent)
        key=(await (await self.upload('data.txt',b'data',child)).json())['id']
        self.assertEqual((await self.client.patch('/api/files/'+parent,headers=self.headers,json={'parent':child})).status,400)
        await self.client.post('/api/files/'+parent+'/trash',headers=self.headers,json={})
        await self.folder('Projekt','desktop')
        response=await self.client.post('/api/files/'+parent+'/restore',headers=self.headers,json={})
        restored=await response.json();self.assertEqual(restored['parent'],'desktop');self.assertIn('restored',restored['name'])
        self.assertEqual((await self.client.get('/api/files/'+key+'/download',headers=self.headers)).status,200)
        await self.client.post('/api/files/'+child+'/trash',headers=self.headers,json={})
        await self.client.post('/api/files/'+parent+'/trash',headers=self.headers,json={})
        await self.client.delete('/api/files/'+parent,headers=self.headers)
        response=await self.client.post('/api/files/'+child+'/restore',headers=self.headers,json={})
        self.assertEqual((await response.json())['parent'],'files')
        self.assertEqual((await self.client.get('/api/files/'+key+'/download',headers=self.headers)).status,200)

    async def test_parallel_upload_reservations(self):
        with app.db() as conn:conn.execute('UPDATE users SET storage_quota=10 WHERE id=1')
        started=asyncio.Event();release=asyncio.Event()
        async def body():
            yield b'1234';started.set();await release.wait();yield b'5678'
        task=asyncio.create_task(self.client.post('/api/files/upload?name=first.bin&parent=files',headers={**self.headers,'Content-Length':'8'},data=body()))
        await started.wait()
        for _ in range(50):
            listing=await (await self.client.get('/api/files',headers=self.headers)).json()
            if listing['reserved']==8:break
            await asyncio.sleep(.01)
        self.assertEqual(listing['reserved'],8)
        response=await self.upload('second.bin',b'abc');self.assertEqual(response.status,413)
        release.set();self.assertEqual((await task).status,201)
        listing=await (await self.client.get('/api/files',headers=self.headers)).json();self.assertEqual((listing['used'],listing['reserved']),(8,0))

    async def test_names_duplicates_backup_lock_and_account_deletion(self):
        for name in ('../file','a/b','a\\b','..','bad\nname'):
            self.assertEqual((await self.upload(name)).status,400)
        response=await self.upload('Test.txt');self.assertEqual(response.status,201)
        self.assertEqual((await self.upload('test.TXT')).status,409)
        with (app.STATE/'files.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            self.assertEqual((await self.upload('locked.txt')).status,503)
        uid,alice=await self.user();response=await self.upload('alice.txt',headers=alice);key=(await response.json())['id']
        self.assertTrue(app.FILES.blob(uid,key).exists())
        await self.client.delete('/api/users/'+str(uid),headers=self.headers)
        self.assertFalse((app.STATE/'files'/str(uid)).exists())

    async def test_large_stream_and_lower_quota_refused(self):
        response=await self.upload('large.bin',io.BytesIO(b'a'*(1024**2+7)));self.assertEqual(response.status,201)
        key=(await response.json())['id']
        response=await self.client.patch('/api/users/1/storage',headers=self.headers,json={'quota_mb':1});self.assertEqual(response.status,409)
        response=await self.client.get('/api/files/'+key+'/download',headers=self.headers);self.assertEqual(len(await response.read()),1024**2+7)
        self.assertEqual((await self.client.delete('/api/files/'+key,headers=self.headers)).status,404)

    async def test_interrupted_upload_releases_quota_and_no_partial_file(self):
        started=asyncio.Event();release=asyncio.Event()
        async def body():
            yield b'1234';started.set();await release.wait();yield b'5678'
        task=asyncio.create_task(self.client.post('/api/files/upload?name=partial.bin',headers={**self.headers,'Content-Length':'8'},data=body()))
        await started.wait()
        for _ in range(50):
            result=await (await self.client.get('/api/files',headers=self.headers)).json()
            if result['reserved']==8:break
            await asyncio.sleep(.01)
        with (app.STATE/'files.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            release.set()
            self.assertEqual((await task).status,503)
        result=await (await self.client.get('/api/files',headers=self.headers)).json()
        self.assertEqual((result['used'],result['reserved']),(0,0))
        self.assertFalse(list((app.STATE/'files').rglob('*.part')))
        self.assertEqual((await self.upload('partial.bin')).status,201)

    async def test_client_disconnect_cleans_upload(self):
        started=asyncio.Event()
        async def body():
            yield b'1234';started.set();await asyncio.Event().wait()
        task=asyncio.create_task(self.client.post('/api/files/upload?name=cancelled.bin',headers={**self.headers,'Content-Length':'8'},data=body()))
        await started.wait()
        for _ in range(100):
            result=await (await self.client.get('/api/files',headers=self.headers)).json()
            if result['reserved']==8:break
            await asyncio.sleep(.01)
        self.assertEqual(result['reserved'],8)
        task.cancel();await asyncio.gather(task,return_exceptions=True)
        for _ in range(100):
            result=await (await self.client.get('/api/files',headers=self.headers)).json()
            if result['reserved']==0:break
            await asyncio.sleep(.01)
        self.assertEqual((result['used'],result['reserved']),(0,0))
        self.assertFalse(list((app.STATE/'files').rglob('*.part')))

    async def test_editor_private_atomic_save_conflict_and_quota(self):
        key=(await (await self.upload('hello.py',b'print(1)')).json())['id']
        _,alice=await self.user()
        url=f'/api/files/{key}/content'
        self.assertEqual((await self.client.get(url,headers=alice)).status,404)
        self.assertEqual((await self.client.put(url,headers=alice,data=b'bad')).status,404)
        content=await (await self.client.get(url,headers=self.headers)).json()
        headers={**self.headers,'If-Match':content['version']}
        response=await self.client.put(url,headers=headers,data='print("å")'.encode());self.assertEqual(response.status,200)
        self.assertEqual(await (await self.client.get(f'/api/files/{key}/download',headers=self.headers)).read(),'print("å")'.encode())
        self.assertEqual((await self.client.put(url,headers=headers,data=b'stale')).status,409)
        content=await (await self.client.get(url,headers=self.headers)).json();headers['If-Match']=content['version']
        with app.db() as conn:conn.execute('UPDATE users SET storage_quota=15 WHERE id=1')
        self.assertEqual((await self.client.put(url,headers=headers,data=b'x'*16)).status,409)
        self.assertEqual((await self.client.put(url,headers=headers,data=b'\xff')).status,400)
        self.assertEqual((await self.client.put(url,headers=headers,data=b'\x00')).status,400)
        self.assertEqual((await self.client.put(url,headers=headers,data=b'x'*(1024**2+1))).status,413)
        app.FILES.initialize(clean_uploads=True)
        self.assertEqual((await (await self.client.get(url,headers=self.headers)).json())['text'],'print("å")')
        await self.client.post(f'/api/files/{key}/trash',headers=self.headers,json={})
        self.assertEqual((await self.client.put(url,headers=headers,data=b'no')).status,404)
        await self.client.post(f'/api/files/{key}/restore',headers=self.headers,json={})
        self.assertEqual((await (await self.client.get(url,headers=self.headers)).json())['text'],'print("å")')
        await self.client.post(f'/api/files/{key}/trash',headers=self.headers,json={})
        await self.client.delete(f'/api/files/{key}',headers=self.headers)
        self.assertEqual(list((app.STATE/'files'/'1').iterdir()),[])

    async def test_icon_positions_private_and_validated(self):
        _,alice=await self.user()
        layout={'shortcuts':[],'color':'#3a6ea5','positions':{'app:files':[350,200]}}
        self.assertEqual((await self.client.put('/api/desktop',headers=alice,json=layout)).status,200)
        self.assertEqual(await (await self.client.get('/api/desktop',headers=alice)).json(),layout)
        self.assertIsNone(await (await self.client.get('/api/desktop',headers=self.headers)).json())
        layout['positions']['app:files']=[-1,0]
        self.assertEqual((await self.client.put('/api/desktop',headers=alice,json=layout)).status,400)
