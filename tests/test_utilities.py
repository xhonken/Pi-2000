import uuid
import io
import stat
import zipfile
import unittest
import asyncssh
import test_server
import app

class UtilityTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=test_server.ServerTests.asyncSetUp
    asyncTearDown=test_server.ServerTests.asyncTearDown
    create_account=test_server.ServerTests.create_account
    login_account=test_server.ServerTests.login_account
    async def call(self,tool,data,headers=None,status=200):
        r=await self.client.post('/api/utilities/'+tool,headers=headers or self.headers,json=data)
        self.assertEqual(r.status,status,await r.text());return await r.json()
    async def upload(self,name,body):
        r=await self.client.post('/api/files/upload',headers=self.headers,params={'name':name},data=body)
        self.assertEqual(r.status,201,await r.text());return (await r.json())['id']
    async def zip(self,entries,compression=zipfile.ZIP_DEFLATED):
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w',compression=compression) as z:
            for name,body in entries:z.writestr(name,body)
        return await self.upload('archive-'+uuid.uuid4().hex+'.zip',stream.getvalue())
    async def test_network_private_targets_real_dns_ping_tcp(self):
        payload={'action':'save','name':'Local SSH','host':'localhost','port':self.port}
        saved=await self.call('network',payload)
        await self.create_account();other=await self.login_account()
        self.assertEqual((await self.call('network',{'action':'list'},other))['targets'],[])
        await self.call('network',{**payload,'id':saved['id']},other,404)
        await self.call('network',{'action':'delete','id':saved['id']},other,404)
        lookup=await self.call('network',{'action':'dns','host':'localhost'})
        self.assertIn('127.0.0.1',lookup['addresses'])
        connected=await self.call('network',{'action':'tcp','host':'127.0.0.1','port':self.port})
        self.assertTrue(connected['ok'])
        ping=await self.call('network',{'action':'ping','host':'127.0.0.1'})
        self.assertTrue(ping['ok'],ping)
        for host in ['--help','a;id','https://localhost','a\nlocalhost','0.0.0.0','224.0.0.1','169.254.1.1']:
            await self.call('network',{'action':'tcp','host':host},status=400)
        for port in [0,65536,True,'80']:
            await self.call('network',{'action':'tcp','host':'localhost','port':port},status=400)
        await self.call('network',{'action':'delete','id':saved['id']})
    async def test_zip_selected_folders_contents_conflict_and_privacy(self):
        key=await self.zip([('project/',b''),('project/main.ino',b'void setup() {}'),('project/images/red.raw',b'\x00\xf8'),('skip.txt',b'skip')])
        listing=await self.call('archive',{'action':'list','file':key})
        payload={'action':'extract','file':key,'version':listing['version'],'entries':[0],'name':'Unpacked'}
        await self.call('archive',{**payload,'version':'stale'},status=409)
        await self.create_account();other=await self.login_account()
        await self.call('archive',{'action':'list','file':key},other,404)
        foreign=(await (await self.client.post('/api/files/folders',headers=other,json={'name':'Private'})).json())['id']
        await self.call('archive',{**payload,'parent':foreign},status=404)
        extracted=await self.call('archive',payload);self.assertEqual(extracted['files'],2)
        files=(await (await self.client.get('/api/files',headers=self.headers)).json())['items']
        self.assertFalse(any(f['name']=='skip.txt' for f in files))
        red=next(f for f in files if f['name']=='red.raw')
        self.assertEqual(await (await self.client.get('/api/files/'+red['id']+'/download',headers=self.headers)).read(),b'\x00\xf8')
        await self.call('archive',payload,status=409)
        self.assertFalse(list(app.STATE.glob('archive-stage-*')))
        with app.db() as db:self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])
    async def test_zip_rejects_paths_links_bombs_and_quota_without_partial_output(self):
        symlink=zipfile.ZipInfo('link');symlink.create_system=3;symlink.external_attr=(stat.S_IFLNK|0o777)<<16
        cases=[ [('../escape',b'x')], [('/absolute',b'x')], [('C:/drive',b'x')], [('a\\b',b'x')], [('a',b'x'),('A',b'y')], [('folder',b'x'),('folder/file',b'y')],[(symlink,b'/etc/passwd')],[('bomb',b'0'*2000000)]]
        for entries in cases:
            key=await self.zip(entries)
            await self.call('archive',{'action':'list','file':key},status=400)
        key=await self.zip([('okay.txt',b'new data')]);listing=await self.call('archive',{'action':'list','file':key})
        with app.db() as db:
            used=app.FILES.usage(db,1)['used'];db.execute('UPDATE users SET storage_quota=? WHERE id=1',(used,))
        await self.call('archive',{'action':'extract','file':key,'version':listing['version'],'entries':[0],'name':'No partial'},status=409)
        files=(await (await self.client.get('/api/files',headers=self.headers)).json())['items']
        self.assertFalse(any(f['name']=='No partial' for f in files))
    async def test_log_bounded_tail_binary_and_account_boundary(self):
        key=await self.upload('large.log',b'INFO old line\n'*90000+b'ERROR latest measurement\n')
        log=await self.call('log',{'file':key});self.assertTrue(log['truncated']);self.assertLessEqual(log['bytes'],262144)
        self.assertTrue(log['text'].startswith('INFO old line\n'));self.assertTrue(log['text'].endswith('ERROR latest measurement\n'))
        await self.create_account();other=await self.login_account();await self.call('log',{'file':key},other,404)
        binary=await self.upload('binary.log',b'\x00secret');await self.call('log',{'file':binary},status=400)
    async def test_ssh_log_real_sftp_tail_rotation_and_privacy(self):
        remote=app.STATE/'remote';remote.mkdir();log=remote/'app.log';log.write_bytes(b'INFO start\n'*100000+b'ERROR remote latest\n')
        server=await asyncssh.create_server(test_server.SSHServer,'127.0.0.1',0,server_host_keys=[self.key],sftp_factory=lambda ch:asyncssh.SFTPServer(ch,chroot=str(remote)))
        try:
            profile=(await (await self.client.post('/api/items',headers=self.headers,json={'kind':'profile','name':'Logs','host':'127.0.0.1','port':server.get_port(),'username':'pi'})).json())['id']
            data={'profile':profile,'password':'ssh-test-password','action':'tail','path':'app.log'}
            r=await self.client.post('/api/sftp/editor',headers=self.headers,json=data);self.assertEqual(r.status,409);data['trust']=(await r.json())['fingerprint']
            r=await self.client.post('/api/sftp/editor',headers=self.headers,json=data);self.assertEqual(r.status,200,await r.text());tail=await r.json();self.assertTrue(tail['truncated']);self.assertTrue(tail['text'].endswith('ERROR remote latest\n'))
            log.rename(remote/'app.log.1');log.write_text('INFO rotated\n')
            r=await self.client.post('/api/sftp/editor',headers=self.headers,json=data);self.assertEqual((await r.json())['text'],'INFO rotated\n')
            await self.create_account();other=await self.login_account();r=await self.client.post('/api/sftp/editor',headers=other,json=data);self.assertEqual(r.status,404)
        finally:server.close();await server.wait_closed()

    async def test_corrupt_zip_crc_rolls_back_all_staged_files(self):
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_STORED) as z:
            z.writestr('first.txt',b'good');z.writestr('second.txt',b'original-content')
        body=stream.getvalue().replace(b'original-content',b'corrupt!-content')
        key=await self.upload('broken.zip',body);listing=await self.call('archive',{'action':'list','file':key})
        await self.call('archive',{'action':'extract','file':key,'version':listing['version'],'entries':[0,1],'name':'Broken'},status=400)
        files=(await (await self.client.get('/api/files',headers=self.headers)).json())['items']
        self.assertEqual([f['name'] for f in files],['broken.zip'])
        self.assertFalse(list(app.STATE.glob('archive-stage-*')))
        self.assertEqual(len(list(app.FILES.blob(1,key).parent.iterdir())),1)
