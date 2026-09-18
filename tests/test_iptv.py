import asyncio
import gzip
import json
import socket
import time
import unittest
from unittest.mock import patch,AsyncMock
from aiohttp import web
import test_server
import app
import iptv_sources as sources
from iptv_fixture import PLAYLIST,attach,make_media,Response

class ParsingTests(unittest.TestCase):
    def test_m3u_groups_countries_vod_and_safe_options(self):
        rows,guides,skipped=sources.parse_m3u(PLAYLIST.encode(),'https://media.example/list')
        self.assertEqual(len(rows),5);self.assertEqual(guides,['https://media.example/guide.xml']);self.assertEqual(skipped,0)
        self.assertEqual(rows[0]['country'],'SE');self.assertEqual(rows[0]['group'],'Sweden');self.assertEqual(rows[2]['kind'],'movie');self.assertEqual(rows[3]['kind'],'series')
        odd=b'''#EXTM3U\n#EXTINF:-1 group-title="News, Music" tvg-country="SE",Comma, Title\n#EXTVLCOPT:http-user-agent=Fixture\n../channel.ts|Referer=https%3A%2F%2Fmedia.example%2F\n#EXTINF:-1,Bad\nfile:///etc/passwd\n'''
        rows,_,skipped=sources.parse_m3u(odd,'https://media.example/path/list');self.assertEqual(rows[0]['name'],'Comma, Title');self.assertEqual(rows[0]['group'],'News, Music');self.assertEqual(rows[0]['secret']['headers']['User-Agent'],'Fixture');self.assertEqual(skipped,1)

    def test_public_address_boundary_and_scheme_validation(self):
        for value in ('127.0.0.1','::1','::ffff:127.0.0.1','192.168.1.250','169.254.169.254','10.0.0.1','0.0.0.0','224.0.0.1','100.64.0.1'):
            with self.assertRaises(web.HTTPBadRequest):sources.public_ip(value)
        sources.public_ip('8.8.8.8')
        for value in ('file:///etc/passwd','ftp://example.com','http://localhost/x','http://a/\r\nx','http://a:99999/x'):
            with self.assertRaises(web.HTTPBadRequest):sources.url(value)

    def test_xmltv_entity_and_zip_bomb_rejection(self):
        good=b'<tv><programme channel="test" start="20260918100000 +0200" stop="20260918110000 +0200"><title>News</title></programme></tv>'
        self.assertEqual(sources.xmltv(gzip.compress(good))[0]['title'],'News')
        for data in (b'<!DOCTYPE tv [<!ENTITY e SYSTEM "file:///etc/passwd">]><tv>&e;</tv>',gzip.compress(b' '*(25*1024**2))):
            with self.assertRaises(web.HTTPBadRequest):sources.xmltv(data)

    def test_xtream_credentials_roundtrip_without_command_parsing(self):
        c=sources.xtream_config('https://media.example/get.php?username=a%40b&password=x%26%2F%3F&type=m3u_plus')
        self.assertEqual(c['password'],'x&/?');self.assertIn('a%40b/x%26%2F%3F/42.ts',sources.stream_url(c,'live',42,'ts'))
        with self.assertRaises(web.HTTPBadGateway):sources.stream_url(c,'live','../../42','ts')

class NetworkTests(unittest.IsolatedAsyncioTestCase):
    async def test_dns_private_answer_rejected_before_any_connection(self):
        for answer in ('127.0.0.1','169.254.169.254','192.168.1.1'):
            with patch.object(asyncio.get_running_loop(),'getaddrinfo',AsyncMock(return_value=[(socket.AF_INET,socket.SOCK_STREAM,6,'',(answer,80))])):
                with self.assertRaises(web.HTTPBadRequest):await sources.Network().read('http://public-looking.example/list')

    async def test_redirect_cannot_rebind_into_private_network(self):
        from contextlib import asynccontextmanager
        from unittest.mock import MagicMock
        calls=[]
        class Client:
            def __init__(self,**kwargs):pass
            async def __aenter__(self):return self
            async def __aexit__(self,*args):pass
            @asynccontextmanager
            async def get(self,target,**kwargs):
                calls.append(target);yield Response(b'',status=302,headers={'Location':'http://alias.example/secret'})
        answers=[[(socket.AF_INET,socket.SOCK_STREAM,6,'',('8.8.8.8',80))],[(socket.AF_INET,socket.SOCK_STREAM,6,'',('127.0.0.1',80))]]
        with patch.object(asyncio.get_running_loop(),'getaddrinfo',AsyncMock(side_effect=answers)),patch('iptv_sources.local_addresses',return_value=set()),patch('iptv_sources.aiohttp.ClientSession',Client),patch('iptv_sources.aiohttp.TCPConnector',MagicMock()):
            with self.assertRaises(web.HTTPBadRequest):await sources.Network().read('http://provider.example/list')
        self.assertEqual(calls,['http://provider.example/list'])

    async def test_streaming_catalog_projection_and_nested_input(self):
        from contextlib import asynccontextmanager
        raw=json.dumps([{'name':'One','stream_id':1,'plot':{'unneeded':['large metadata']},'cover':'x'},{'name':'Two','series_id':2}]).encode()
        @asynccontextmanager
        async def opened(*args):yield Response(raw),'https://fixture.example'
        network=sources.Network()
        with patch.object(network,'open',opened):
            rows=[row async for row in network.array('https://fixture.example')]
        self.assertEqual([r['name'] for r in rows],['One','Two']);self.assertNotIn('plot',rows[0])
        raw=b'['*20+b'0'+b']'*20
        with patch.object(network,'open',opened):
            with self.assertRaises(web.HTTPBadGateway):rows=[row async for row in network.array('https://fixture.example')]

class IPTVTests(unittest.IsolatedAsyncioTestCase):
    asyncTearDown=test_server.ServerTests.asyncTearDown
    create_account=test_server.ServerTests.create_account
    login_account=test_server.ServerTests.login_account
    async def asyncSetUp(self):
        await test_server.ServerTests.asyncSetUp(self)
        self.headers['X-IPTV-Owner']='1';self.library=attach(self.client.server.app)
    async def add(self,xtream=False):
        data={'name':'Fixture','url':'https://media.example/get.php?username=fixture-user&password=fixture-private-secret' if xtream else 'https://media.example/playlist.m3u8'}
        r=await self.client.post('/api/iptv/sources',headers=self.headers,json=data);self.assertEqual(r.status,201,await r.text());result=await r.json();self.assertEqual(result['source']['name'],'Fixture');return result['source']['id']
    async def catalog(self,source,query=''):
        r=await self.client.get('/api/iptv/sources/'+source+'/catalog'+query,headers=self.headers);self.assertEqual(r.status,200);return await r.json()
    async def test_private_catalog_credentials_and_account_switch_boundary(self):
        source=await self.add(True);data=await self.catalog(source)
        self.assertEqual(data['count'],3);self.assertNotIn('fixture-private-secret',json.dumps(data));self.assertNotIn('media.example',json.dumps(data))
        with app.db() as db:
            for table in ('iptv_sources','iptv_entries'):
                self.assertNotIn('fixture-private-secret',str([tuple(r) for r in db.execute('SELECT * FROM '+table)]))
        uid=await self.create_account('iptv-other');other=await self.login_account('iptv-other');other['X-IPTV-Owner']=str(uid)
        for path,method in [('/catalog','get'),('','delete'),('/refresh','post')]:
            r=await getattr(self.client,method)('/api/iptv/sources/'+source+path,headers=other,json={} if method=='post' else None);self.assertEqual(r.status,404)
        r=await self.client.post('/api/iptv/sources',headers={**other,'X-IPTV-Owner':'1'},json={'name':'Wrong account','url':'https://media.example/playlist.m3u8'});self.assertEqual(r.status,403)

    async def test_filters_favorites_atomic_refresh_and_history(self):
        source=await self.add();data=await self.catalog(source,'?kind=live&country=SE');self.assertEqual(data['count'],2)
        movie=(await self.catalog(source,'?kind=movie'))['items'][0];path='/api/iptv/sources/'+source+'/entries/'+movie['id']
        r=await self.client.patch(path,headers=self.headers,json={'favorite':True,'position':123});self.assertEqual(r.status,200)
        favorites=await self.catalog(source,'?kind=favorites');self.assertEqual(favorites['items'][0]['position'],123)
        with patch.object(self.library.network,'read',AsyncMock(side_effect=web.HTTPBadGateway(text='Fixture offline'))):
            r=await self.client.post('/api/iptv/sources/'+source+'/refresh',headers=self.headers,json={});self.assertEqual(r.status,502)
        self.assertEqual((await self.catalog(source))['count'],5)
        r=await self.client.post('/api/iptv/sources/'+source+'/refresh',headers=self.headers,json={});self.assertEqual(r.status,200)
        self.assertEqual((await self.catalog(source,'?kind=favorites'))['items'][0]['position'],123)

    async def test_login_bound_hls_rewriting_and_revocation(self):
        source=await self.add();item=next(i for i in (await self.catalog(source))['items'] if i['name']=='Swedish Test News')
        r=await self.client.post('/api/iptv/sources/'+source+'/entries/'+item['id']+'/play',headers=self.headers,json={});self.assertEqual(r.status,200);play=await r.json()
        r=await self.client.get(play['url'],headers=self.headers);manifest=await r.text();self.assertEqual(r.status,200);self.assertNotIn('media.example',manifest);self.assertIn('/api/iptv/media/',manifest)
        other_token=await self.login_account('admin',self.password)
        r=await self.client.get(play['url'],headers=other_token);self.assertEqual(r.status,404)
        r=await self.client.delete('/api/iptv/play/'+play['session'],headers=self.headers);self.assertEqual(r.status,200)
        r=await self.client.get(play['url'],headers=self.headers);self.assertEqual(r.status,404)

    async def test_hls_keys_maps_and_media_urls_are_opaque(self):
        session={'id':'fixture','targets':{},'reverse':__import__('collections').OrderedDict()}
        raw=b'#EXTM3U\n#EXT-X-KEY:METHOD=AES-128,URI="https://media.example/key?password=hidden"\n#EXT-X-MAP:URI="init.mp4"\n#EXT-X-MEDIA:TYPE=AUDIO,URI="audio.m3u8"\n#EXTINF:2,\npart.ts\n'
        result=self.library.media.manifest(session,raw,'https://media.example/list.m3u8').decode();self.assertNotIn('password',result);self.assertEqual(result.count('/api/iptv/media/'),4)

    async def test_xtream_episodes_and_actual_archive_url(self):
        source=await self.add(True);items=(await self.catalog(source))['items'];series=next(i for i in items if i['kind']=='series');live=next(i for i in items if i['kind']=='live')
        path='/api/iptv/sources/'+source+'/entries/'
        r=await self.client.post(path+series['id']+'/episodes',headers=self.headers,json={});self.assertEqual(r.status,200)
        episodes=await self.catalog(source,'?kind=series&parent='+series['id']);self.assertEqual(episodes['count'],2)
        r=await self.client.post(path+live['id']+'/guide',headers=self.headers,json={});self.assertEqual(r.status,200);p=(await r.json())['programmes'][0];self.assertEqual(p['title'],'Previous Bulletin');self.assertTrue(p['available'])
        r=await self.client.post(path+live['id']+'/play',headers=self.headers,json={'start':p['start']});self.assertEqual(r.status,200);play=await r.json();self.assertFalse(play['live']);self.assertIn('/timeshift/',self.library.media.sessions[play['session']]['root'])
        r=await self.client.post(path+live['id']+'/play',headers=self.headers,json={'start':time.time()-60*86400});self.assertEqual(r.status,400)

    async def test_xmltv_import_and_catalog_delete_cascade(self):
        source=await self.add();r=await self.client.post('/api/iptv/sources/'+source+'/guides',headers=self.headers,json={'index':0});self.assertEqual(r.status,200)
        r=await self.client.delete('/api/iptv/sources/'+source,headers=self.headers);self.assertEqual(r.status,200)
        with app.db() as db:
            for table in ('iptv_entries','iptv_guide','iptv_preferences'):self.assertEqual(db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0],0)

    async def test_isolated_ffmpeg_audio_and_video_conversion(self):
        await asyncio.to_thread(make_media,app.STATE/'fixture-media');self.library.network.media=app.STATE/'fixture-media'
        source=await self.add();item=next(i for i in (await self.catalog(source))['items'] if i['name']=='British Test TS');path='/api/iptv/sources/'+source+'/entries/'+item['id']+'/play'
        for mode in ('audio','compatible'):
            r=await self.client.post(path,headers=self.headers,json={'mode':mode});self.assertEqual(r.status,200);data=await r.json()
            # Capture diagnostics only for generated fixtures, never provider media.
            launch=asyncio.create_subprocess_exec
            diagnostics=[]
            async def capture(*args,**kwargs):
                if '/usr/bin/ffmpeg' in args:kwargs['stderr']=asyncio.subprocess.PIPE
                process=await launch(*args,**kwargs)
                if '/usr/bin/ffmpeg' in args:
                    diagnostics.append(asyncio.create_task(process.stderr.read(16384)))
                return process
            with patch('iptv_media.asyncio.create_subprocess_exec',capture):
                r=await self.client.get(data['url'],headers=self.headers);raw=await r.read()
            details=await asyncio.wait_for(asyncio.gather(*diagnostics),5)
            self.assertEqual(r.status,200,(mode,raw[:200],details));self.assertGreater(len(raw),5000);self.assertEqual(raw[0],0x47)
            for _ in range(100):
                if not self.library.media.converting:break
                await asyncio.sleep(.02)
            self.assertFalse(self.library.media.converting)
