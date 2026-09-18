"""In-memory provider fixtures, used only by tests; no production network bypass."""
from contextlib import asynccontextmanager
import base64
import json
from pathlib import Path
import subprocess
import time
from urllib.parse import urlsplit, parse_qs
from aiohttp import web

PLAYLIST='''#EXTM3U x-tvg-url="https://media.example/guide.xml"
#EXTINF:-1 tvg-id="news.se" tvg-country="SE" group-title="Sweden",Swedish Test News
https://media.example/master.m3u8
#EXTINF:-1 tvg-country="GB" group-title="United Kingdom",British Test TS
https://media.example/live.ts
#EXTINF:-1 group-title="Movies",Test Film
https://media.example/film.mp4
#EXTINF:-1 group-title="Series",Example S01E01
https://media.example/episode.mp4
#EXTINF:-1 tvg-country="SE" group-title="Sweden",<img src=x onerror=alert(1)>
https://media.example/other.ts
'''

class Content:
    def __init__(self,data):self.data=data;self.offset=0
    async def read(self,size=-1):
        data=self.data[self.offset:] if size<0 else self.data[self.offset:self.offset+size]
        self.offset+=len(data);return data
    async def iter_chunked(self,size):
        while True:
            value=await self.read(size)
            if not value:return
            yield value

class Response:
    def __init__(self,data,mime='application/octet-stream',status=200,headers=None):
        self.content=Content(data);self.content_type=mime;self.status=status;self.headers={'Content-Length':str(len(data)),**(headers or {})}

class FixtureNetwork:
    def __init__(self,media=None):self.media=Path(media) if media else None;self.calls=[]
    def data(self,target):
        p=urlsplit(target);query=parse_qs(p.query);self.calls.append(p.path)
        if p.path=='/playlist.m3u8':return PLAYLIST.encode(),'audio/x-mpegurl'
        if p.path=='/guide.xml':
            now=time.time();stamp=lambda v:time.strftime('%Y%m%d%H%M%S +0000',time.gmtime(v))
            return ('<tv><programme channel="news.se" start="'+stamp(now-600)+'" stop="'+stamp(now+1200)+'"><title>Test Bulletin</title><desc>Programme guide fixture</desc></programme></tv>').encode(),'application/xml'
        if p.path=='/player_api.php':
            action=query.get('action',[''])[0]
            if not action:value={'user_info':{'auth':1},'server_info':{'timezone':'Europe/Stockholm'}}
            elif action.endswith('_categories'):value=[{'category_id':'1','category_name':'Nordic'}]
            elif action=='get_live_streams':value=[{'stream_id':42,'name':'Archive TV','category_id':'1','epg_channel_id':'archive.tv','tv_archive':1,'tv_archive_duration':7}]
            elif action=='get_vod_streams':value=[{'stream_id':45,'name':'Xtream Film','category_id':'1','container_extension':'mp4'}]
            elif action=='get_series':value=[{'series_id':46,'name':'Example Series','category_id':'1'}]
            elif action=='get_series_info':value={'episodes':{'1':[{'id':50,'title':'Pilot','episode_num':1,'container_extension':'mp4'},{'id':51,'title':'Second Episode','episode_num':2,'container_extension':'mp4'}]}}
            elif action=='get_simple_data_table':value={'epg_listings':[{'start_timestamp':int(time.time())-7200,'stop_timestamp':int(time.time())-3600,'title':base64.b64encode(b'Previous Bulletin').decode(),'description':base64.b64encode(b'Archive fixture').decode()}]}
            else:raise web.HTTPBadGateway(text='Unknown fixture action.')
            return json.dumps(value).encode(),'application/json'
        if p.path=='/master.m3u8':return b'#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=300000,RESOLUTION=320x180,CODECS="avc1.42c00d,mp4a.40.2"\nhls/index.m3u8\n','application/vnd.apple.mpegurl'
        if self.media:
            filename='live.ts' if p.path.endswith('.ts') and not p.path.startswith('/hls/') else 'film.mp4' if p.path.endswith('.mp4') else p.path.lstrip('/')
            path=self.media/filename
            if path.is_file() and path.resolve().is_relative_to(self.media.resolve()):
                return path.read_bytes(),'application/vnd.apple.mpegurl' if path.suffix=='.m3u8' else 'video/mp4' if path.suffix=='.mp4' else 'video/mp2t'
        return b'fixture-segment','video/mp2t'
    async def read(self,target,limit=None):return self.data(target)[0],target
    async def json(self,target):return json.loads(self.data(target)[0])
    async def array(self,target):
        for row in await self.json(target):yield row
    @asynccontextmanager
    async def open(self,target,headers=None):
        data,mime=self.data(target);status=200;extra={'Accept-Ranges':'bytes'}
        if headers and headers.get('Range'):
            start,_,end=headers['Range'].removeprefix('bytes=').partition('-');start=int(start or 0);end=int(end) if end else len(data)-1
            extra['Content-Range']=f'bytes {start}-{end}/{len(data)}';data=data[start:end+1];status=206
        yield Response(data,mime,status,extra),target

def make_media(root):
    root=Path(root);(root/'hls').mkdir(parents=True,exist_ok=True)
    common=['ffmpeg','-hide_banner','-loglevel','error','-y','-f','lavfi','-i','testsrc2=size=320x180:rate=25','-f','lavfi','-i','sine=frequency=440:sample_rate=48000','-t','8','-c:v','libx264','-threads','1','-preset','ultrafast','-pix_fmt','yuv420p','-g','50','-c:a','aac','-b:a','96k']
    subprocess.run([*common,'-movflags','+faststart',str(root/'film.mp4')],check=True)
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(root/'film.mp4'),'-c','copy','-f','mpegts',str(root/'live.ts')],check=True)
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(root/'film.mp4'),'-c','copy','-hls_time','2','-hls_list_size','0','-hls_segment_filename',str(root/'hls/part%d.ts'),str(root/'hls/index.m3u8')],check=True)

def attach(application,media=None):
    library=next(r.handler.library for r in application.router.routes() if r.resource.canonical=='/api/iptv/sources')
    library.network=FixtureNetwork(media);return library
