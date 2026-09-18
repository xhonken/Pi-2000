import unittest
import test_server
import app

class DesktopTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=test_server.ServerTests.asyncSetUp
    asyncTearDown=test_server.ServerTests.asyncTearDown

    def document(self):
        return {'shortcuts':[],'color':'#3a6ea5','positions':{'app:files':[120,0]},'icons':{'vault':{'name':'My safe','visible':False}},'view':{'sort':'type','direction':'asc','autoArrange':True,'snap':False,'showIcons':True,'openMode':'double'}}

    async def test_legacy_roundtrip_and_conditional_writes(self):
        legacy={'shortcuts':[],'color':'#008080'}
        self.assertEqual((await self.client.put('/api/desktop',headers=self.headers,json=legacy)).status,200)
        response=await self.client.get('/api/desktop',headers=self.headers)
        self.assertEqual(await response.json(),legacy)
        tag=response.headers['ETag']
        response=await self.client.put('/api/desktop',headers={**self.headers,'If-Match':tag},json=self.document())
        self.assertEqual(response.status,200);self.assertNotEqual(tag,response.headers['ETag'])
        response=await self.client.put('/api/desktop',headers={**self.headers,'If-Match':tag},json=legacy)
        self.assertEqual(response.status,409)
        self.assertEqual(await (await self.client.get('/api/desktop',headers=self.headers)).json(),self.document())

    async def test_account_isolation_and_stale_account_header(self):
        response=await self.client.post('/api/users',headers=self.headers,json={'username':'alice','password':'alice-password-123'})
        uid=(await response.json())['id']
        response=await self.client.post('/api/login',headers=self.origin,json={'username':'alice','password':'alice-password-123'})
        alice={**self.origin,'Cookie':f"{app.COOKIE}={response.cookies[app.COOKIE].value}",'X-Desktop-Owner':str(uid)}
        self.assertEqual((await self.client.put('/api/desktop',headers=alice,json=self.document())).status,200)
        self.assertIsNone(await (await self.client.get('/api/desktop',headers=self.headers)).json())
        forged={**self.headers,'X-Desktop-Owner':str(uid)}
        self.assertEqual((await self.client.put('/api/desktop',headers=forged,json=self.document())).status,403)
        self.assertEqual((await self.client.get('/api/desktop',headers=forged)).status,403)
        self.assertEqual((await self.client.get('/api/desktop?user_id='+str(uid),headers=self.headers)).status,403)

    async def test_bounded_settings_and_inert_names(self):
        for field,value in [('icons',{'logout':{'name':'bad','visible':True}}),('icons',{'vault':{'name':'','visible':True}}),('view',{'snap':'true'}),('view',{'sort':[]} ),('positions',{'app:files':[True,0]}),('view',{'openMode':'execute'})]:
            data=self.document();data[field]=value
            self.assertEqual((await self.client.put('/api/desktop',headers=self.headers,json=data)).status,400)
        data=self.document();data['icons']['vault']['name']='<img src=x onerror=alert(1)>'
        self.assertEqual((await self.client.put('/api/desktop',headers=self.headers,json=data)).status,200)
        shortcut={'id':'one','name':'link','url':'https://example.com','desktop':True,'start':True,'deleted':False}
        for shortcuts in [[shortcut,shortcut],[{**shortcut,'url':'javascript:alert(1)'}],[{**shortcut,'url':'https://'}],[{**shortcut,'id':'x'*121}]]:
            data=self.document();data['shortcuts']=shortcuts
            self.assertEqual((await self.client.put('/api/desktop',headers=self.headers,json=data)).status,400)

    async def test_duplicate_copy_retains_file_extension_and_contents(self):
        response=await self.client.post('/api/files/upload?parent=desktop&name=report.txt',headers={**self.headers,'Content-Type':'application/octet-stream'},data=b'private fixture')
        self.assertEqual(response.status,201)
        original=(await response.json())['id']
        response=await self.client.post('/api/files/copy',headers=self.headers,json={'ids':[original],'parent':'desktop'})
        self.assertEqual(response.status,200)
        items=(await (await self.client.get('/api/files',headers=self.headers)).json())['items']
        self.assertEqual({x['name'] for x in items},{'report.txt','report (copy 2).txt'})
        for item in items:
            response=await self.client.get('/api/files/'+item['id']+'/download',headers=self.headers)
            self.assertEqual(await response.read(),b'private fixture')
