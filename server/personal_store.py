"""Private preferences and quota-accounted notes/editor drafts."""
import hashlib
import json
import re
import time
from aiohttp import web
from file_store import FILE_USER

class PersonalStore:
    def __init__(self,files):self.files=files
    def initialize(self):
        with self.files.db() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS preferences(user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS personal_docs(user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,key TEXT NOT NULL,data TEXT NOT NULL,size INTEGER NOT NULL,version TEXT NOT NULL,modified REAL NOT NULL,PRIMARY KEY(user_id,key));''')
    async def preferences(self,request):
        uid=request[FILE_USER]['id']
        if request.method=='GET':
            with self.files.db() as db:r=db.execute('SELECT data FROM preferences WHERE user_id=?',(uid,)).fetchone()
            return web.json_response(json.loads(r[0]) if r else {})
        data=await self.files.read_json(request)
        if set(data)-{'fontSize','openText','favorites','recent'}:raise web.HTTPBadRequest()
        if data.get('fontSize',13) not in (12,13,14,16,18):raise web.HTTPBadRequest()
        if data.get('openText','preview') not in ('preview','editor'):raise web.HTTPBadRequest()
        for field in ('favorites','recent'):
            if not isinstance(data.get(field,[]),list) or len(data.get(field,[]))>100 or any(not isinstance(v,str) or len(v)>128 for v in data.get(field,[])):raise web.HTTPBadRequest()
        with self.files.mutation(),self.files.db() as db:db.execute('INSERT INTO preferences VALUES (?,?) ON CONFLICT(user_id) DO UPDATE SET data=excluded.data',(uid,json.dumps(data)))
        return web.json_response({'ok':True})
    async def documents(self,request):
        uid=request[FILE_USER]['id'];key=request.match_info.get('key')
        if key and not re.fullmatch(r'(notes|cad|draft-[a-zA-Z0-9-]{1,80})',key):raise web.HTTPBadRequest()
        if request.method=='GET':
            with self.files.db() as db:
                if not key:
                    return web.json_response({'documents':[dict(r) for r in db.execute('SELECT key,size,version,modified FROM personal_docs WHERE user_id=?',(uid,))]})
                r=db.execute('SELECT * FROM personal_docs WHERE user_id=? AND key=?',(uid,key)).fetchone()
            return web.json_response({'data':json.loads(r['data']) if r else None,'version':r['version'] if r else ''})
        if request.method=='DELETE':
            with self.files.mutation(),self.files.db() as db:db.execute('DELETE FROM personal_docs WHERE user_id=? AND key=?',(uid,key))
            return web.json_response({'ok':True})
        raw=bytearray()
        async for chunk in request.content.iter_chunked(65536):
            raw.extend(chunk)
            if len(raw)>2*1024**2:raise web.HTTPRequestEntityTooLarge(max_size=2*1024**2,actual_size=len(raw))
        if not self.files.valid(request):raise web.HTTPUnauthorized()
        data=json.loads(raw)
        if not isinstance(data,dict):raise web.HTTPBadRequest()
        body=json.dumps(data,ensure_ascii=False);size=len(body.encode());version=hashlib.sha256(body.encode()).hexdigest()
        with self.files.mutation(),self.files.db() as db:
            db.execute('BEGIN IMMEDIATE');old=db.execute('SELECT size,version FROM personal_docs WHERE user_id=? AND key=?',(uid,key)).fetchone()
            if request.headers.get('If-Match','')!=(old['version'] if old else ''):raise web.HTTPConflict(text='The document changed on another page. Reload before continuing.')
            used=self.files.usage(db,uid)
            if used['used']+used['reserved']-(old['size'] if old else 0)+size>used['quota']:raise web.HTTPConflict(text='The draft or note exceeds the storage quota.')
            if not old and db.execute('SELECT COUNT(*) FROM personal_docs WHERE user_id=?',(uid,)).fetchone()[0]>=102:raise web.HTTPConflict(text='Too many drafts. Remove old drafts first.')
            db.execute('INSERT INTO personal_docs VALUES (?,?,?,?,?,?) ON CONFLICT(user_id,key) DO UPDATE SET data=excluded.data,size=excluded.size,version=excluded.version,modified=excluded.modified',(uid,key,body,size,version,time.time()))
        return web.json_response({'version':version})
