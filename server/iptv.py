"""Per-account IPTV library. Provider credentials never appear in browser URLs."""
import asyncio
import base64
from datetime import datetime, timezone
import json
import os
import re
import secrets
import tempfile
from pathlib import Path
import time
from urllib.parse import urlsplit, urlencode, quote
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from aiohttp import web
from request_security import body_chunks
import iptv_sources as sources
from iptv_media import Media


class IPTV:
    def __init__(self,app,cipher):
        self.app=app;self.cipher=cipher;self.network=sources.Network();self.media=Media(self);self.importing=False

    def initialize(self):
        with self.app.db() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS iptv_sources(id TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,name TEXT NOT NULL,kind TEXT NOT NULL,secret TEXT NOT NULL,updated REAL NOT NULL,revision INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS iptv_entries(source TEXT NOT NULL REFERENCES iptv_sources(id) ON DELETE CASCADE,id TEXT NOT NULL,data TEXT NOT NULL,secret TEXT NOT NULL,PRIMARY KEY(source,id));
            CREATE TABLE IF NOT EXISTS iptv_preferences(source TEXT NOT NULL REFERENCES iptv_sources(id) ON DELETE CASCADE,id TEXT NOT NULL,favorite INTEGER NOT NULL DEFAULT 0,position REAL NOT NULL DEFAULT 0,watched REAL NOT NULL DEFAULT 0,PRIMARY KEY(source,id));
            CREATE TABLE IF NOT EXISTS iptv_guide(source TEXT NOT NULL REFERENCES iptv_sources(id) ON DELETE CASCADE,channel TEXT NOT NULL,start REAL NOT NULL,stop REAL NOT NULL,data TEXT NOT NULL,PRIMARY KEY(source,channel,start));
            CREATE INDEX IF NOT EXISTS iptv_guide_channel ON iptv_guide(source,channel,start);
            CREATE INDEX IF NOT EXISTS iptv_entry_kind ON iptv_entries(source,json_extract(data,'$.kind'));
            CREATE INDEX IF NOT EXISTS iptv_entry_group ON iptv_entries(source,json_extract(data,'$.group'));
            ''')

    def encode(self,data):return self.cipher.encrypt(json.dumps(data,ensure_ascii=False).encode()).decode()
    def decode(self,data):return json.loads(self.cipher.decrypt(data.encode()))

    def source(self,uid,key):
        with self.app.db() as db:row=db.execute('SELECT * FROM iptv_sources WHERE id=? AND user_id=?',(key,uid)).fetchone()
        if not row:raise web.HTTPNotFound(text='Playlist not found.')
        return dict(row)

    def item(self,uid,source,key):
        profile=self.source(uid,source)
        with self.app.db() as db:row=db.execute('SELECT * FROM iptv_entries WHERE source=? AND id=?',(source,key)).fetchone()
        if not row:raise web.HTTPNotFound(text='Media entry not found. Refresh the library.')
        return profile,{**json.loads(row['data']),'secret':self.decode(row['secret'])}

    async def read(self,request):
        raw=bytearray()
        async for chunk in body_chunks(request):
            raw.extend(chunk)
            if len(raw)>8*1024**2:raise web.HTTPBadRequest(text='The playlist upload exceeds 8 MB.')
        self.app.require_current(request)
        result=json.loads(raw)
        if not isinstance(result,dict):raise web.HTTPBadRequest(text='Enter playlist details.')
        return result

    def summary(self,row):
        with self.app.db() as db:count=db.execute('SELECT COUNT(*) FROM iptv_entries WHERE source=?',(row['id'],)).fetchone()[0]
        return {k:row[k] for k in ('id','name','kind','updated','revision')}|{'count':count}

    async def playlists(self,request):
        uid=request[self.app.USER]['id'];key=request.match_info.get('id')
        if request.method=='GET':
            with self.app.db() as db:rows=db.execute('SELECT * FROM iptv_sources WHERE user_id=? ORDER BY name',(uid,)).fetchall()
            return web.json_response({'sources':[self.summary(row) for row in rows]})
        old=self.source(uid,key) if key else None
        if request.method=='DELETE':
            with self.app.db() as db:db.execute('DELETE FROM iptv_sources WHERE id=? AND user_id=?',(key,uid))
            self.media.drop(uid,key);return web.json_response({'ok':True})
        data=await self.read(request)
        if old and request.method=='PATCH':
            name=data.get('name')
            if not isinstance(name,str) or not 1<=len(name.strip())<=100:raise web.HTTPBadRequest(text='Enter a playlist name of up to 100 characters.')
            self.source(uid,key)
            with self.app.db() as db:db.execute('UPDATE iptv_sources SET name=? WHERE id=? AND user_id=?',(name.strip(),key,uid))
            return web.json_response({'ok':True})
        if self.importing or self.media.converting:raise web.HTTPTooManyRequests(text='Wait for the current import or compatibility conversion to finish.')
        with self.app.db() as db:
            if not old and db.execute('SELECT COUNT(*) FROM iptv_sources WHERE user_id=?',(uid,)).fetchone()[0]>=8:
                raise web.HTTPConflict(text='Save up to eight private IPTV sources.')
        if old:
            config=self.decode(old['secret']);name=old['name']
        else:
            name=data.get('name');kind=data.get('kind','m3u')
            if not isinstance(name,str) or not 1<=len(name.strip())<=100:raise web.HTTPBadRequest(text='Enter a playlist name of up to 100 characters.')
            name=name.strip()
            if kind=='xtream':
                base=sources.url(data.get('url','')).rstrip('/')
                p=urlsplit(base)
                if p.query or p.username is not None:raise web.HTTPBadRequest(text='For Xtream, enter the server address and separate credentials.')
                username,password=data.get('username'),data.get('password')
                if any(not isinstance(v,str) or not 1<=len(v)<=512 or any(ord(c)<32 for c in v) for v in (username,password)):
                    raise web.HTTPBadRequest(text='Enter the IPTV username and password.')
                config={'kind':'xtream','xtream':{'base':base,'username':username,'password':password}}
            elif kind=='m3u':
                address=sources.url(data.get('url',''));xtream=sources.xtream_config(address)
                config={'kind':'xtream','xtream':xtream} if xtream and data.get('use_xtream',True) else {'kind':'m3u','url':address}
            elif kind=='file':
                content=data.get('content')
                if not isinstance(content,str) or len(content.encode())>6*1024**2:raise web.HTTPBadRequest(text='Select an M3U file of up to 6 MB.')
                config={'kind':'file','content':content}
            else:raise web.HTTPBadRequest(text='Choose M3U, Xtream or an M3U file.')
        self.importing=True
        staging=None
        try:
            warnings=[]
            fd,stage_name=tempfile.mkstemp(prefix='.iptv-import-',dir=self.app.STATE);os.close(fd);staging=Path(stage_name)
            # The stage contains encrypted URLs, lives in private state, and is
            # never a served file. A failed import leaves the old library intact.
            count=0
            async def emit(batch):
                nonlocal count
                def append():
                    with staging.open('a') as output:
                        for row in self.pack(batch):output.write(json.dumps(row,ensure_ascii=False)+'\n')
                work=asyncio.create_task(asyncio.to_thread(append))
                try:await asyncio.shield(work)
                except asyncio.CancelledError:
                    await work;raise
                if staging.stat().st_size>512*1024**2:raise web.HTTPBadRequest(text='The encrypted catalogue exceeds 512 MB.')
                count+=len(batch)
            async with asyncio.timeout(240):
                if config['kind']=='xtream':
                    _,config['xtream'],warnings=await sources.xtream_catalog(self.network,config['xtream'],emit);config['guides']=[]
                else:
                    raw,base=await self.network.read(config['url']) if config['kind']=='m3u' else (config['content'].encode(),'https://invalid.example/')
                    items,config['guides'],skipped=await asyncio.to_thread(sources.parse_m3u,raw,base)
                    if skipped:warnings.append(str(skipped)+' non-HTTP or invalid entries were skipped.')
                    for start in range(0,len(items),500):await emit(items[start:start+500])
            self.app.require_current(request)
            if old and self.source(uid,key)['revision']!=old['revision']:raise web.HTTPConflict(text='Playlist changed. Retry refresh.')
            key=key or secrets.token_hex(16);revision=old['revision']+1 if old else 1
            with self.app.db() as db:
                existing=db.execute('SELECT COUNT(*) FROM iptv_entries e JOIN iptv_sources s ON s.id=e.source WHERE s.user_id=? AND s.id<>?',(uid,key)).fetchone()[0]
                cached=db.execute("SELECT COUNT(*) FROM iptv_entries WHERE source=? AND json_extract(data,'$.parent') IS NOT NULL",(key,)).fetchone()[0]
                if existing+count+cached>600000:raise web.HTTPConflict(text='Your IPTV library exceeds 600,000 entries. Use smaller source lists.')
                db.execute('INSERT INTO iptv_sources VALUES (?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET secret=excluded.secret,updated=excluded.updated,revision=excluded.revision',(key,uid,name,config['kind'],self.encode(config),time.time(),revision))
                db.execute("DELETE FROM iptv_entries WHERE source=? AND json_extract(data,'$.parent') IS NULL",(key,))
                with staging.open() as stream:
                    db.executemany('INSERT OR IGNORE INTO iptv_entries VALUES (?,?,?,?)',((key,*json.loads(line)) for line in stream))
                db.execute("DELETE FROM iptv_entries WHERE source=? AND json_extract(data,'$.parent') IS NOT NULL AND json_extract(data,'$.parent') NOT IN (SELECT id FROM iptv_entries WHERE source=?)",(key,key))
                db.execute('DELETE FROM iptv_preferences WHERE source=? AND id NOT IN (SELECT id FROM iptv_entries WHERE source=?)',(key,key))
            self.media.drop(uid,key)
            return web.json_response({'source':self.summary(self.source(uid,key)),'warnings':warnings},status=200 if old else 201)
        except TimeoutError:raise web.HTTPGatewayTimeout(text='The provider import timed out. The previous library is unchanged.') from None
        finally:
            if staging:staging.unlink(missing_ok=True)
            self.importing=False

    def pack(self,items):
        return [(item['id'],json.dumps({k:v for k,v in item.items() if k!='secret'},ensure_ascii=False),self.encode(item['secret'])) for item in items]

    async def catalog(self,request):
        uid=request[self.app.USER]['id'];key=request.match_info['id'];profile=self.source(uid,key)
        query=request.query;where=['e.source=?'];args=[key]
        kind=query.get('kind','all')
        if kind not in ('all','live','movie','series','favorites','recent'):raise web.HTTPBadRequest(text='Invalid library view.')
        if kind in ('live','movie','series'):where.append("json_extract(e.data,'$.kind')=?");args.append(kind)
        if kind=='favorites':where.append('p.favorite=1')
        if kind=='recent':where.append('p.watched>0')
        for field in ('group','country','parent'):
            value=query.get(field,'')
            if value:where.append("json_extract(e.data,'$."+field+"')=?");args.append(value[:240])
        if not query.get('parent') and kind not in ('favorites','recent'):where.append("json_extract(e.data,'$.parent') IS NULL")
        search=query.get('q','').strip()[:200]
        if search:
            where.append("instr(lower(json_extract(e.data,'$.name')),lower(?))>0");args.append(search)
        try:offset=max(0,min(600000,int(query.get('offset','0'))))
        except ValueError:raise web.HTTPBadRequest(text='Invalid library page.') from None
        clause=' AND '.join(where);join=' FROM iptv_entries e LEFT JOIN iptv_preferences p ON p.source=e.source AND p.id=e.id '
        with self.app.db() as db:
            count=db.execute('SELECT COUNT(*)'+join+'WHERE '+clause,args).fetchone()[0]
            order="p.watched DESC" if kind=='recent' else "json_extract(e.data,'$.name') COLLATE NOCASE"
            rows=db.execute('SELECT e.data,COALESCE(p.favorite,0) AS favorite,COALESCE(p.position,0) AS position'+join+'WHERE '+clause+' ORDER BY '+order+' LIMIT 200 OFFSET ?',(*args,offset)).fetchall()
            groups=[r[0] for r in db.execute("SELECT DISTINCT json_extract(data,'$.group') FROM iptv_entries WHERE source=? ORDER BY 1 COLLATE NOCASE LIMIT 2000",(key,))]
            countries=[r[0] for r in db.execute("SELECT DISTINCT json_extract(data,'$.country') FROM iptv_entries WHERE source=? AND json_extract(data,'$.country')<>'' ORDER BY 1 LIMIT 256",(key,))]
        return web.json_response({'items':[{**json.loads(r['data']),'favorite':bool(r['favorite']),'position':r['position']} for r in rows], 'count':count,'offset':offset,'groups':groups,'countries':countries,'source':self.summary(profile)})

    async def episodes(self,request):
        uid=request[self.app.USER]['id'];profile,item=self.item(uid,request.match_info['id'],request.match_info['entry'])
        config=self.decode(profile['secret'])
        if not item.get('series_folder') or config['kind']!='xtream':raise web.HTTPBadRequest(text='Select an Xtream series.')
        if self.importing or self.media.converting:raise web.HTTPTooManyRequests(text='Wait for the current import or compatibility conversion to finish.')
        self.importing=True
        try:
            result=await self.network.json(sources.xtream_url(config['xtream'],'get_series_info',series_id=item['provider_id']))
            if not isinstance(result,dict) or not isinstance(result.get('episodes'),dict):raise web.HTTPBadGateway(text='The provider returned no series episodes.')
            items=[]
            for season,episodes in result['episodes'].items():
                if not isinstance(episodes,list):continue
                for row in episodes:
                    if not isinstance(row,dict):continue
                    target=sources.stream_url(config['xtream'],'series',row.get('id',''),str(row.get('container_extension') or 'mp4'))
                    title='S'+str(season).zfill(2)+' E'+str(row.get('episode_num','')).zfill(2)+' — '+sources.text(row.get('title') or item['name'])
                    items.append(sources.entry(title,target,item['group'],kind='series',key=sources.identity('episode:'+str(row['id'])),parent=item['id'],season=sources.text(season,20),archive=0))
                    if len(items)>5000:raise web.HTTPBadGateway(text='This series exceeds 5,000 episodes.')
            rows=await asyncio.to_thread(self.pack,items)
            self.app.require_current(request)
            if self.source(uid,profile['id'])['revision']!=profile['revision']:raise web.HTTPConflict(text='Playlist changed. Reopen the series.')
            with self.app.db() as db:
                count=db.execute('SELECT COUNT(*) FROM iptv_entries e JOIN iptv_sources s ON s.id=e.source WHERE s.user_id=?',(uid,)).fetchone()[0]
                if count+len(rows)>600000:raise web.HTTPConflict(text='The IPTV library has reached its entry limit.')
                db.execute("DELETE FROM iptv_entries WHERE source=? AND json_extract(data,'$.parent')=?",(profile['id'],item['id']))
                db.executemany('INSERT OR REPLACE INTO iptv_entries VALUES (?,?,?,?)',((profile['id'],*r) for r in rows))
            return web.json_response({'count':len(rows),'parent':item['id']})
        finally:self.importing=False

    async def preference(self,request):
        data=await self.app.read_json(request);uid=request[self.app.USER]['id']
        profile,item=self.item(uid,request.match_info['id'],request.match_info['entry'])
        with self.app.db() as db:
            row=db.execute('SELECT * FROM iptv_preferences WHERE source=? AND id=?',(profile['id'],item['id'])).fetchone()
            favorite=row['favorite'] if row else 0;position=row['position'] if row else 0;watched=row['watched'] if row else 0
            if 'favorite' in data:
                if type(data['favorite']) is not bool:raise web.HTTPBadRequest(text='Invalid favorite setting.')
                favorite=int(data['favorite'])
            if 'position' in data:
                p=data['position']
                if type(p) not in (int,float) or not 0<=p<=7*86400:raise web.HTTPBadRequest(text='Invalid playback position.')
                position=p if item['kind']!='live' else 0;watched=time.time()
            db.execute('INSERT OR REPLACE INTO iptv_preferences VALUES (?,?,?,?,?)',(profile['id'],item['id'],favorite,position,watched))
        return web.json_response({'ok':True})

    async def guide_sources(self,request):
        profile=self.source(request[self.app.USER]['id'],request.match_info['id']);config=self.decode(profile['secret'])
        # Display only a safe host/path label, never guide query credentials.
        def label(v):
            try:p=urlsplit(v);return (p.hostname or '')+' / '+p.path.rsplit('/',1)[-1][:100]
            except ValueError:return 'Programme guide'
        return web.json_response({'guides':[{'index':i,'name':label(v)} for i,v in enumerate(config.get('guides',[]))],'xtream':config['kind']=='xtream'})

    async def import_guide(self,request):
        data=await self.app.read_json(request);uid=request[self.app.USER]['id'];profile=self.source(uid,request.match_info['id']);config=self.decode(profile['secret'])
        if self.importing or self.media.converting:raise web.HTTPTooManyRequests(text='Wait for the current import or compatibility conversion to finish.')
        if data.get('url'):target=sources.url(data['url'])
        else:
            index=data.get('index')
            if type(index) is not int or not 0<=index<len(config.get('guides',[])):raise web.HTTPBadRequest(text='Select or enter an XMLTV guide.')
            target=config['guides'][index]
        self.importing=True
        try:
            raw,_=await self.network.read(target,24*1024**2)
            programmes=await asyncio.to_thread(sources.xmltv,raw)
            self.app.require_current(request)
            if self.source(uid,profile['id'])['revision']!=profile['revision']:raise web.HTTPConflict(text='Playlist changed. Refresh the guide again.')
            self.save_guide(profile['id'],programmes,replace=True)
            return web.json_response({'count':len(programmes)})
        finally:self.importing=False

    def save_guide(self,source,programmes,replace=False):
        now=time.time()
        with self.app.db() as db:
            if replace:db.execute('DELETE FROM iptv_guide WHERE source=?',(source,))
            db.execute('DELETE FROM iptv_guide WHERE stop<?',(now-30*86400,))
            db.executemany('INSERT OR REPLACE INTO iptv_guide VALUES (?,?,?,?,?)',((source,p['channel'],p['start'],p['stop'],json.dumps(p)) for p in programmes if now-30*86400<p['stop']<now+30*86400))
            db.execute('DELETE FROM iptv_guide WHERE source=? AND rowid NOT IN (SELECT rowid FROM iptv_guide WHERE source=? ORDER BY stop DESC LIMIT 50000)',(source,source))

    async def guide(self,request):
        uid=request[self.app.USER]['id'];profile,item=self.item(uid,request.match_info['id'],request.match_info['entry']);config=self.decode(profile['secret'])
        channel=item.get('tvg_id') or item['id']
        if request.method=='POST' and config['kind']=='xtream' and item.get('provider_id') and item['kind']=='live':
            if self.importing or self.media.converting:raise web.HTTPTooManyRequests(text='Wait for the current import or compatibility conversion to finish.')
            self.importing=True
            try:result=await self.network.json(sources.xtream_url(config['xtream'],'get_simple_data_table',stream_id=item['provider_id']))
            finally:self.importing=False
            rows=result.get('epg_listings',[]) if isinstance(result,dict) else [];programmes=[]
            def decoded(value):
                try:return base64.b64decode(str(value),validate=True).decode('utf-8')
                except (ValueError,UnicodeError):return str(value)
            for row in rows[:2000]:
                if not isinstance(row,dict):continue
                try:
                    start=float(row.get('start_timestamp',0));stop=float(row.get('stop_timestamp') or row.get('end_timestamp',0))
                    if not 0<stop-start<=86400:continue
                    programmes.append({'channel':channel,'start':start,'stop':stop,'title':sources.text(decoded(row.get('title',''))),'description':sources.text(decoded(row.get('description','')),2000)})
                except (ValueError,TypeError):continue
            self.app.require_current(request)
            if self.source(uid,profile['id'])['revision']!=profile['revision']:raise web.HTTPConflict(text='Playlist changed. Reopen the guide.')
            self.save_guide(profile['id'],programmes)
        now=time.time()
        with self.app.db() as db:rows=db.execute('SELECT data FROM iptv_guide WHERE source=? AND channel=? AND stop>? ORDER BY start LIMIT 1000',(profile['id'],channel,now-max(1,item.get('archive',0))*86400)).fetchall()
        result=[]
        for row in rows:
            p=json.loads(row[0]);p['available']=bool(item.get('archive') and now-item['archive']*86400<=p['start']<p['stop']<=now)
            result.append(p)
        return web.json_response({'programmes':result,'archive_days':item.get('archive',0)})

    async def play(self,request):
        data=await self.app.read_json(request);uid=request[self.app.USER]['id']
        profile,item=self.item(uid,request.match_info['id'],request.match_info['entry'])
        if item.get('series_folder'):raise web.HTTPBadRequest(text='Open a series and choose an episode.')
        target=item['secret']['url']
        if data.get('start') is not None:
            start=data['start'];now=time.time();days=item.get('archive',0)
            if type(start) not in (int,float) or not days or not now-days*86400<=start<now:raise web.HTTPBadRequest(text='This programme is outside the provider archive window.')
            with self.app.db() as db:row=db.execute('SELECT * FROM iptv_guide WHERE source=? AND channel=? AND start=?',(profile['id'],item.get('tvg_id') or item['id'],start)).fetchone()
            if not row or row['stop']>now:raise web.HTTPBadRequest(text='Select a completed programme from the guide.')
            duration=int(row['stop']-start);config=self.decode(profile['secret'])
            if config['kind']=='xtream':
                c=config['xtream']
                try:zone=ZoneInfo(c.get('timezone','UTC'))
                except ZoneInfoNotFoundError:zone=timezone.utc
                stamp=datetime.fromtimestamp(start,zone).strftime('%Y-%m-%d:%H-%M')
                target=c['base'].rstrip('/')+'/timeshift/'+quote(c['username'],safe='')+'/'+quote(c['password'],safe='')+'/'+str(max(1,(duration+59)//60))+'/'+stamp+'/'+item['provider_id']+'.ts'
            else:
                template=item['secret'].get('catchup_source','');mode=item['secret'].get('catchup','')
                if not template:raise web.HTTPBadRequest(text='This list does not provide an archive URL template.')
                if mode=='append':template=target+template
                dt=datetime.fromtimestamp(start,timezone.utc)
                values={'utc':str(int(start)),'utcend':str(int(row['stop'])),'start':str(int(start)),'end':str(int(row['stop'])),'duration':str(duration),'Y':dt.strftime('%Y'),'m':dt.strftime('%m'),'d':dt.strftime('%d'),'H':dt.strftime('%H'),'M':dt.strftime('%M'),'S':dt.strftime('%S')}
                for k,v in values.items():template=template.replace('${'+k+'}',v).replace('{'+k+'}',v)
                if '{' in template:raise web.HTTPBadRequest(text='This provider uses an unsupported archive URL template.')
                target=sources.url(template)
            item={**item,'kind':'archive'}
        return web.json_response(self.media.create(request,profile,item,target,data.get('mode','original')))

    def register(self,application):
        self.initialize()
        application.cleanup_ctx.append(self.media.lifecycle)
        def owned(handler):
            async def handle(request):
                if request.headers.get('X-IPTV-Owner')!=str(request[self.app.USER]['id']):
                    raise web.HTTPForbidden(text='The signed-in account changed. Reopen IPTV Player.')
                return await handler(request)
            handle.library=self
            return handle
        application.router.add_get('/api/iptv/sources',owned(self.playlists))
        application.router.add_post('/api/iptv/sources',owned(self.playlists))
        application.router.add_delete('/api/iptv/sources/{id}',owned(self.playlists))
        application.router.add_patch('/api/iptv/sources/{id}',owned(self.playlists))
        application.router.add_post('/api/iptv/sources/{id}/refresh',owned(self.playlists))
        application.router.add_get('/api/iptv/sources/{id}/catalog',owned(self.catalog))
        application.router.add_get('/api/iptv/sources/{id}/guides',owned(self.guide_sources))
        application.router.add_post('/api/iptv/sources/{id}/guides',owned(self.import_guide))
        application.router.add_post('/api/iptv/sources/{id}/entries/{entry}/episodes',owned(self.episodes))
        application.router.add_patch('/api/iptv/sources/{id}/entries/{entry}',owned(self.preference))
        application.router.add_get('/api/iptv/sources/{id}/entries/{entry}/guide',owned(self.guide))
        application.router.add_post('/api/iptv/sources/{id}/entries/{entry}/guide',owned(self.guide))
        application.router.add_post('/api/iptv/sources/{id}/entries/{entry}/play',owned(self.play))
        application.router.add_get('/api/iptv/media/{sid}/{resource}',self.media.handle)
        application.router.add_delete('/api/iptv/play/{sid}',owned(self.media.stop))
