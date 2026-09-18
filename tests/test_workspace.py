import copy
import unittest
import test_server
import app

class WorkspaceTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=test_server.ServerTests.asyncSetUp
    asyncTearDown=test_server.ServerTests.asyncTearDown
    create_account=test_server.ServerTests.create_account
    login_account=test_server.ServerTests.login_account

    def layout(self, text='private'):
        return {'windows':[{'type':'calculator-window','left':10,'top':20,'width':450,'height':400,'hidden':True,'maximized':False,'state':{'expression':text}}]}

    async def test_four_accounts_persist_and_never_read_each_other(self):
        headers=[self.headers]
        for name in ('alice','bravo','charlie'):
            await self.create_account(name);headers.append(await self.login_account(name))
        for i,h in enumerate(headers):
            self.assertEqual((await self.client.put('/api/workspace',headers=h,json=self.layout(str(i)))).status,200)
        app.initialize()
        for i,h in enumerate(headers):
            self.assertEqual(await (await self.client.get('/api/workspace',headers=h)).json(),self.layout(str(i)))
        self.assertEqual((await self.client.get('/api/workspace?user_id=2',headers=self.headers)).status,403)
        self.assertEqual((await self.client.put('/api/workspace',headers={**self.headers,'X-Workspace-Owner':'2'},json=self.layout())).status,403)
        self.assertEqual((await self.client.get('/api/workspace')).status,401)

    async def test_stale_tabs_cannot_erase_checkpoint(self):
        r=await self.client.get('/api/workspace',headers=self.headers);tag=r.headers['ETag']
        h={**self.headers,'If-Match':tag}
        self.assertEqual((await self.client.put('/api/workspace',headers=h,json=self.layout())).status,200)
        self.assertEqual((await self.client.put('/api/workspace',headers=h,json={'windows':[]})).status,409)
        self.assertEqual(await (await self.client.get('/api/workspace',headers=self.headers)).json(),self.layout())

    async def test_recovery_quota_and_large_drafts(self):
        data=self.layout('x'*20000)
        self.assertEqual((await self.client.put('/api/workspace',headers=self.headers,json=data)).status,200)
        with app.db() as db:
            usage=app.FILES.usage(db,1);self.assertGreater(usage['used'],20000)
            db.execute('UPDATE users SET storage_quota=100 WHERE id=1')
        self.assertEqual((await self.client.put('/api/workspace',headers=self.headers,json=self.layout('x'*30000))).status,413)
        self.assertEqual(await (await self.client.get('/api/workspace',headers=self.headers)).json(),data)

    async def test_boundaries_and_no_vault_or_password_form_state(self):
        for change in ({'type':'vault-window'},{'type':'terminal-window'},{'left':float('nan')},{'password':'never store a form'}, {'profile':'other'}):
            data=self.layout();data['windows'][0].update(change)
            self.assertEqual((await self.client.put('/api/workspace',headers=self.headers,json=data)).status,400)
        data=self.layout('x'*(4*1024**2))
        self.assertEqual((await self.client.put('/api/workspace',headers=self.headers,json=data)).status,413)

    async def test_expiry_during_body_read_cannot_write(self):
        import json
        async def body():
            yield b'{"windows":'
            app.SESSIONS[self.token]['expires']=0
            yield json.dumps(self.layout()['windows']).encode()+b'}'
        self.assertEqual((await self.client.put('/api/workspace',headers=self.headers,data=body())).status,401)
        with app.db() as db:self.assertIsNone(db.execute('SELECT data FROM workspaces WHERE user_id=1').fetchone())
