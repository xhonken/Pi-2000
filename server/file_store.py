"""Account-owned file metadata, streaming quota reservations and recoverable trash."""
import asyncio
from contextlib import contextmanager
import fcntl
import hashlib
import io
import zipfile
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import time
import unicodedata
from urllib.parse import quote
from aiohttp import web

DEFAULT_QUOTA = 50 * 1024**2
ROOTS = ('files', 'desktop')
FILE_USER = web.RequestKey('file_user', dict)

class FileStore:
    def __init__(self, state, db, valid):
        self.state, self.db, self.valid = Path(state), db, valid
        self.root = self.state/'files'

    def initialize(self, clean_uploads=False):
        self.root.mkdir(exist_ok=True, mode=0o700)
        (self.state/'files.lock').touch(exist_ok=True)
        with self.db() as conn:
            if 'storage_quota' not in {r['name'] for r in conn.execute('PRAGMA table_info(users)')}:
                conn.execute(f'ALTER TABLE users ADD COLUMN storage_quota INTEGER NOT NULL DEFAULT {DEFAULT_QUOTA}')
            conn.executescript('''CREATE TABLE IF NOT EXISTS files (
                id TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                parent TEXT NOT NULL, name TEXT NOT NULL, name_key TEXT NOT NULL,
                kind TEXT NOT NULL CHECK(kind IN ('file','folder')),
                size INTEGER NOT NULL DEFAULT 0 CHECK(size>=0),
                state TEXT NOT NULL CHECK(state IN ('live','trash','upload')),
                trash_root TEXT, modified REAL NOT NULL);
                CREATE INDEX IF NOT EXISTS files_owner ON files(user_id,parent,state);
                CREATE UNIQUE INDEX IF NOT EXISTS files_name ON files(user_id,parent,name_key) WHERE state IN ('live','upload');''')
            if 'content_key' not in {r['name'] for r in conn.execute('PRAGMA table_info(files)')}:
                conn.execute('ALTER TABLE files ADD COLUMN content_key TEXT')
            if clean_uploads:
                rows=conn.execute("SELECT id,user_id FROM files WHERE state='upload'").fetchall()
                conn.execute("DELETE FROM files WHERE state='upload'")
                for row in rows:
                    self.blob(row['user_id'],row['id']).unlink(missing_ok=True)
                    self.blob(row['user_id'],row['id']).with_suffix('.part').unlink(missing_ok=True)

        if clean_uploads:
            # Complete or roll back an interrupted permanent deletion.
            for directory in self.root.iterdir():
                if not directory.name.isdigit() or not directory.is_dir(): continue
                with self.db() as conn:
                    known={r['content_key'] or r['id'] for r in conn.execute('SELECT id,content_key FROM files WHERE user_id=?',(int(directory.name),))}
                garbage=directory/'garbage'
                if garbage.exists():
                    for path in garbage.iterdir():
                        if path.name in known: path.replace(directory/path.name)
                        else: path.unlink()
                for path in directory.iterdir():
                    if path.is_file() and path.name not in known: path.unlink()

    @contextmanager
    def mutation(self):
        with (self.state/'files.lock').open('a') as lock:
            try: fcntl.flock(lock, fcntl.LOCK_SH|fcntl.LOCK_NB)
            except BlockingIOError: raise web.HTTPServiceUnavailable(text='A backup is in progress. Try again shortly.')
            yield

    def blob(self, uid, key):
        if not re.fullmatch(r'[a-f0-9]{32}',key): raise web.HTTPNotFound()
        return self.root/str(int(uid))/key

    @staticmethod
    def name(value):
        if not isinstance(value,str): raise web.HTTPBadRequest(text='Enter a file name.')
        value=unicodedata.normalize('NFC',value.strip())
        if not value or value in ('.','..') or len(value.encode())>240 or any(ord(c)<32 or c in '/\\' for c in value):
            raise web.HTTPBadRequest(text='The name must not contain slashes or control characters and must not exceed 240 bytes.')
        return value

    def row(self, conn, uid, key, state=None):
        row=conn.execute('SELECT * FROM files WHERE id=? AND user_id=?',(key,uid)).fetchone()
        if not row or (state and row['state']!=state): raise web.HTTPNotFound(text='The file or folder does not exist.')
        return dict(row)

    def parent(self, conn, uid, key):
        if key in ROOTS: return key
        row=self.row(conn,uid,key,'live')
        if row['kind']!='folder': raise web.HTTPBadRequest(text='The destination must be a folder.')
        return key

    def unique(self,conn,uid,parent,name,exclude=''):
        if conn.execute("SELECT 1 FROM files WHERE user_id=? AND parent=? AND name_key=? AND state IN ('live','upload') AND id!=?",(uid,parent,name.casefold(),exclude)).fetchone():
            raise web.HTTPConflict(text='A file or folder with that name already exists.')

    def usage(self,conn,uid):
        row=conn.execute('SELECT storage_quota FROM users WHERE id=?',(uid,)).fetchone()
        if not row: raise web.HTTPUnauthorized()
        sizes=conn.execute("SELECT COALESCE(SUM(CASE WHEN state='upload' THEN size ELSE 0 END),0),COALESCE(SUM(CASE WHEN state!='upload' THEN size ELSE 0 END),0) FROM files WHERE user_id=?",(uid,)).fetchone()
        documents=0
        if conn.execute("SELECT 1 FROM sqlite_master WHERE name='personal_docs'").fetchone():
            documents=conn.execute('SELECT COALESCE(SUM(size),0) FROM personal_docs WHERE user_id=?',(uid,)).fetchone()[0]
        return {'quota':row['storage_quota'],'reserved':sizes[0],'used':sizes[1]+documents,'documents':documents}

    def descendants(self,conn,uid,key,state):
        rows=conn.execute('SELECT * FROM files WHERE user_id=? AND state=?',(uid,state)).fetchall()
        selected={key}
        while True:
            more={row['id'] for row in rows if row['parent'] in selected}-selected
            if not more: break
            selected.update(more)
        return [dict(row) for row in rows if row['id'] in selected]

    async def read_json(self,request):
        data=await request.json()
        actor=self.valid(request)
        if not actor: raise web.HTTPUnauthorized(text='The account or login changed. Log in again.')
        request[FILE_USER]=actor
        if not isinstance(data,dict): raise web.HTTPBadRequest(text='A JSON object is required.')
        return data

    async def list(self,request):
        uid=request[FILE_USER]['id']
        with self.db() as conn:
            rows=[dict(r) for r in conn.execute("SELECT id,parent,name,kind,size,state,trash_root,modified FROM files WHERE user_id=? AND state!='upload' ORDER BY kind DESC,name_key",(uid,))]
            return web.json_response({'items':rows,**self.usage(conn,uid)})

    async def create(self,request):
        uid=request[FILE_USER]['id'];data=await self.read_json(request);name=self.name(data.get('name'))
        with self.mutation(), self.db() as conn:
            conn.execute('BEGIN IMMEDIATE')
            parent=self.parent(conn,uid,data.get('parent','files'));self.unique(conn,uid,parent,name)
            if conn.execute('SELECT COUNT(*) FROM files WHERE user_id=?',(uid,)).fetchone()[0]>=5000: raise web.HTTPConflict(text='Maximum 5,000 files and folders per account.')
            key=secrets.token_hex(16)
            conn.execute("INSERT INTO files (id,user_id,parent,name,name_key,kind,size,state,trash_root,modified) VALUES (?,?,?,?,?,'folder',0,'live',NULL,?)",(key,uid,parent,name,name.casefold(),time.time()))
        return web.json_response({'id':key},status=201)

    async def upload(self,request):
        uid=request[FILE_USER]['id'];key=secrets.token_hex(16)
        name=self.name(request.query.get('name'))
        if request.headers.get('Content-Encoding','identity').lower() != 'identity': raise web.HTTPBadRequest(text='Compressed transfers are not supported. Upload the original file.')
        size=request.content_length
        if size is None: raise web.HTTPLengthRequired(text='The file size is required.')
        with self.mutation(), self.db() as conn:
            conn.execute('BEGIN IMMEDIATE')
            parent=self.parent(conn,uid,request.query.get('parent','files'));self.unique(conn,uid,parent,name)
            usage=self.usage(conn,uid)
            if size>usage['quota']-usage['used']-usage['reserved']: raise web.HTTPRequestEntityTooLarge(max_size=usage['quota']-usage['used']-usage['reserved'],actual_size=size,text='The file exceeds your storage quota. Empty the Recycle Bin or ask an administrator to increase your quota.')
            if conn.execute('SELECT COUNT(*) FROM files WHERE user_id=?',(uid,)).fetchone()[0]>=5000: raise web.HTTPConflict(text='Maximum 5,000 files and folders per account.')
            if shutil.disk_usage(self.root).free < size+512*1024**2: raise web.HTTPInsufficientStorage(text='The server has insufficient free storage.')
            conn.execute("INSERT INTO files (id,user_id,parent,name,name_key,kind,size,state,trash_root,modified) VALUES (?,?,?,?,?,'file',?,'upload',NULL,?)",(key,uid,parent,name,name.casefold(),size,time.time()))
        final=self.blob(uid,key);final.parent.mkdir(exist_ok=True,mode=0o700);part=final.with_suffix('.part')
        completed=False
        try:
            written=0
            with part.open('xb') as handle:
                async for chunk in request.content.iter_chunked(65536):
                    written+=len(chunk)
                    if written>size: raise web.HTTPBadRequest(text='The file size does not match.')
                    if not self.valid(request): raise web.HTTPUnauthorized(text='Log in again.')
                    await asyncio.to_thread(handle.write,chunk)
                await asyncio.to_thread(handle.flush)
                await asyncio.to_thread(os.fsync,handle.fileno())
            if written!=size: raise web.HTTPBadRequest(text='The upload did not complete.')
            with self.mutation(), self.db() as conn:
                conn.execute('BEGIN IMMEDIATE')
                if not self.valid(request): raise web.HTTPUnauthorized(text='Log in again.')
                self.parent(conn,uid,parent)
                self.row(conn,uid,key,'upload')
                part.replace(final)
                conn.execute("UPDATE files SET state='live',modified=? WHERE id=?",(time.time(),key))
            completed=True
            return web.json_response({'id':key},status=201)
        finally:
            if not completed:
                part.unlink(missing_ok=True);final.unlink(missing_ok=True)
                with self.db() as conn: conn.execute("DELETE FROM files WHERE id=? AND state='upload'",(key,))

    async def download(self,request):
        uid=request[FILE_USER]['id']
        with self.db() as conn: row=self.row(conn,uid,request.match_info['id'],'live')
        if row['kind']!='file': raise web.HTTPBadRequest(text='Open the folder to download a file.')
        path=self.blob(uid,row['content_key'] or row['id'])
        if not path.is_file(): raise web.HTTPNotFound(text='File content is missing.')
        return web.FileResponse(path,headers={'Content-Type':'application/octet-stream','Content-Disposition':"attachment; filename*=UTF-8''"+quote(row['name'],safe=''),'Content-Security-Policy':"sandbox; default-src 'none'",'X-Content-Type-Options':'nosniff','Cache-Control':'no-store'})

    async def content(self, request):
        uid=request[FILE_USER]['id'];key=request.match_info['id'];limit=1024**2
        body=b''
        if request.method=='PUT':
            async for chunk in request.content.iter_chunked(65536):
                body+=chunk
                if len(body)>limit: raise web.HTTPRequestEntityTooLarge(max_size=limit,actual_size=len(body),text='Code Editor supports up to 1 MB per file.')
            try: body.decode('utf-8')
            except UnicodeDecodeError: raise web.HTTPBadRequest(text='The file must use UTF-8.')
            if b'\x00' in body: raise web.HTTPBadRequest(text='Binary files cannot be edited.')
        with self.mutation(), self.db() as conn:
            conn.execute('BEGIN IMMEDIATE')
            if not self.valid(request): raise web.HTTPUnauthorized()
            row=self.row(conn,uid,key,'live')
            if row['kind']!='file': raise web.HTTPBadRequest(text='Select a text file.')
            if row['size']>limit: raise web.HTTPBadRequest(text='Code Editor supports up to 1 MB per file.')
            old=self.blob(uid,row['content_key'] or key)
            contents=old.read_bytes()
            version=hashlib.sha256(contents).hexdigest()
            if request.method=='GET':
                try: text=contents.decode('utf-8')
                except UnicodeDecodeError: raise web.HTTPBadRequest(text='The file must use UTF-8. Download it to open it in another application.')
                if '\x00' in text: raise web.HTTPBadRequest(text='Binary files cannot be edited.')
                return web.json_response({'text':text,'version':version,'name':row['name'],'parent':row['parent']},headers={'Cache-Control':'no-store'})
            if request.headers.get('If-Match')!=version:
                raise web.HTTPConflict(text='The file changed since it was opened. Save as a new file to keep your changes.')
            usage=self.usage(conn,uid)
            if usage['used']+usage['reserved']-row['size']+len(body)>usage['quota']:
                raise web.HTTPConflict(text='The file exceeds your storage quota.')
            if shutil.disk_usage(self.root).free < len(body)+512*1024**2: raise web.HTTPInsufficientStorage()
            newkey=secrets.token_hex(16);new=self.blob(uid,newkey)
            try:
                with new.open('xb') as handle:
                    handle.write(body);handle.flush();os.fsync(handle.fileno())
                directory=os.open(new.parent,os.O_RDONLY|os.O_DIRECTORY)
                try: os.fsync(directory)
                finally: os.close(directory)
                conn.execute('UPDATE files SET content_key=?,size=?,modified=? WHERE id=?',(newkey,len(body),time.time(),key))
                conn.commit()
            except BaseException:
                new.unlink(missing_ok=True)
                raise
            old.unlink(missing_ok=True)
        return web.json_response({'version':hashlib.sha256(body).hexdigest()})

    async def change(self,request):
        uid=request[FILE_USER]['id'];data=await self.read_json(request);key=request.match_info['id']
        with self.mutation(),self.db() as conn:
            conn.execute('BEGIN IMMEDIATE');row=self.row(conn,uid,key,'live')
            name=self.name(data.get('name',row['name']));parent=self.parent(conn,uid,data.get('parent',row['parent']))
            if row['kind']=='folder' and parent in {r['id'] for r in self.descendants(conn,uid,key,'live')}: raise web.HTTPBadRequest(text='A folder cannot be moved into itself.')
            self.unique(conn,uid,parent,name,key)
            conn.execute('UPDATE files SET name=?,name_key=?,parent=?,modified=? WHERE id=?',(name,name.casefold(),parent,time.time(),key))
        return web.json_response({'ok':True})

    async def trash(self,request):
        uid=request[FILE_USER]['id'];key=request.match_info['id']
        with self.mutation(),self.db() as conn:
            conn.execute('BEGIN IMMEDIATE');self.row(conn,uid,key,'live')
            for row in self.descendants(conn,uid,key,'live'):
                conn.execute("UPDATE files SET state='trash',trash_root=?,modified=? WHERE id=?",(key,time.time(),row['id']))
        return web.json_response({'ok':True})

    async def restore(self,request):
        uid=request[FILE_USER]['id'];key=request.match_info['id']
        with self.mutation(),self.db() as conn:
            conn.execute('BEGIN IMMEDIATE');row=self.row(conn,uid,key,'trash')
            if row['trash_root']!=key: raise web.HTTPBadRequest(text='Restore the parent folder first.')
            parent=row['parent']
            try:self.parent(conn,uid,parent)
            except web.HTTPException:parent='files'
            name=row['name'];number=1
            while True:
                try:self.unique(conn,uid,parent,name);break
                except web.HTTPConflict:
                    number+=1;name=row['name'][:48]+f' (restored {number})'
            conn.execute('UPDATE files SET parent=?,name=?,name_key=? WHERE id=?',(parent,name,name.casefold(),key))
            conn.execute("UPDATE files SET state='live',trash_root=NULL,modified=? WHERE user_id=? AND trash_root=?",(time.time(),uid,key))
        return web.json_response({'parent':parent,'name':name})

    async def purge(self,request):
        uid=request[FILE_USER]['id'];key=request.match_info.get('id')
        with self.mutation(),self.db() as conn:
            conn.execute('BEGIN IMMEDIATE')
            if key:
                row=self.row(conn,uid,key,'trash')
                if row['trash_root']!=key: raise web.HTTPBadRequest(text='Select the parent folder.')
                rows=conn.execute("SELECT * FROM files WHERE user_id=? AND trash_root=?",(uid,key)).fetchall()
            else:rows=conn.execute("SELECT * FROM files WHERE user_id=? AND state='trash'",(uid,)).fetchall()
            # Commit metadata first: a crash can leave an unreferenced blob,
            # but can never remove content still referenced by a live row.
            for row in rows: conn.execute('DELETE FROM files WHERE id=?',(row['id'],))
            conn.commit()
            for row in rows: self.blob(uid,row['content_key'] or row['id']).unlink(missing_ok=True)
        return web.json_response({'ok':True,'removed':len(rows)})

    async def quota(self,request):
        data=await self.read_json(request);actor=request[FILE_USER];uid=int(request.match_info['id']);mb=data.get('quota_mb')
        if actor['role']!='admin':raise web.HTTPForbidden(text='Only administrators can change storage quotas.')
        if type(mb) is not int or not 1<=mb<=1048576:raise web.HTTPBadRequest(text='Enter a whole number between 1 and 1048576 MB.')
        with self.mutation(),self.db() as conn:
            conn.execute('BEGIN IMMEDIATE');user=conn.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
            if not user:raise web.HTTPNotFound()
            if not actor['is_creator'] and user['role']=='admin' and uid!=actor['id']:raise web.HTTPForbidden(text='Only the owner can change other administrator quotas.')
            usage=self.usage(conn,uid)
            if mb*1024**2<usage['used']+usage['reserved']:raise web.HTTPConflict(text='The quota cannot be lower than the storage already used or reserved for uploads.')
            conn.execute('UPDATE users SET storage_quota=? WHERE id=?',(mb*1024**2,uid))
        return web.json_response({'ok':True})

    def store_bytes(self,uid,parent,name,body):
        name=self.name(name);key=secrets.token_hex(16);path=self.blob(uid,key)
        try:
            with self.mutation(),self.db() as db:
                db.execute('BEGIN IMMEDIATE');self.parent(db,uid,parent);self.unique(db,uid,parent,name)
                usage=self.usage(db,uid)
                if len(body)>usage['quota']-usage['used']-usage['reserved']:raise web.HTTPConflict(text='The file exceeds the storage quota.')
                if db.execute('SELECT COUNT(*) FROM files WHERE user_id=?',(uid,)).fetchone()[0]>=5000:raise web.HTTPConflict(text='Too many files.')
                if shutil.disk_usage(self.root).free<len(body)+512*1024**2:raise web.HTTPInsufficientStorage()
                path.parent.mkdir(exist_ok=True,mode=0o700)
                with path.open('xb') as file:file.write(body);file.flush();os.fsync(file.fileno())
                db.execute("INSERT INTO files(id,user_id,parent,name,name_key,kind,size,state,modified) VALUES(?,?,?,?,?,'file',?,'live',?)",(key,uid,parent,name,name.casefold(),len(body),time.time()))
            return key
        except BaseException:
            path.unlink(missing_ok=True)
            raise

    async def copy(self,request):
        uid=request[FILE_USER]['id'];data=await self.read_json(request);created=[]
        keys=data.get('ids',[])
        if not isinstance(keys,list) or not 1<=len(keys)<=100:raise web.HTTPBadRequest()
        try:
            with self.mutation(),self.db() as db:
                db.execute('BEGIN IMMEDIATE');parent=self.parent(db,uid,data.get('parent','files'))
                roots=[self.row(db,uid,key,'live') for key in dict.fromkeys(keys)]
                selected={r['id'] for r in roots}
                # Do not duplicate descendants separately when their ancestor was selected.
                allrows={r['id']:dict(r) for r in db.execute("SELECT * FROM files WHERE user_id=? AND state='live'",(uid,))}
                def nested(row):
                    p=row['parent'];seen=set()
                    while p in allrows and p not in seen:
                        if p in selected:return True
                        seen.add(p);p=allrows[p]['parent']
                    return False
                roots=[r for r in roots if not nested(r)]
                groups=[(r,self.descendants(db,uid,r['id'],'live')) for r in roots]
                rows=[r for _,group in groups for r in group]
                usage=self.usage(db,uid)
                if sum(r['size'] for r in rows)>usage['quota']-usage['used']-usage['reserved']:raise web.HTTPConflict(text='The copy exceeds the storage quota.')
                if db.execute('SELECT COUNT(*) FROM files WHERE user_id=?',(uid,)).fetchone()[0]+len(rows)>5000:raise web.HTTPConflict(text='Too many files.')
                mapping={r['id']:secrets.token_hex(16) for r in rows}
                for root,group in groups:
                    if parent in {r['id'] for r in group}:raise web.HTTPBadRequest(text='Select a folder outside the one being copied.')
                    name=root['name'];number=1
                    while True:
                        try:self.unique(db,uid,parent,name);break
                        except web.HTTPConflict:number+=1;name=root['name'][:48]+f' (kopia {number})'
                    for row in group:
                        key=mapping[row['id']];target=parent if row['id']==root['id'] else mapping[row['parent']]
                        label=name if row['id']==root['id'] else row['name']
                        if row['kind']=='file':
                            path=self.blob(uid,key);os.link(self.blob(uid,row['content_key'] or row['id']),path);created.append(path)
                        db.execute("INSERT INTO files(id,user_id,parent,name,name_key,kind,size,state,modified) VALUES(?,?,?,?,?,?,?,'live',?)",(key,uid,target,label,label.casefold(),row['kind'],row['size'],time.time()))
            return web.json_response({'ids':[mapping[r['id']] for r in roots]})
        except BaseException:
            for path in created:path.unlink(missing_ok=True)
            raise

    async def archive(self,request):
        uid=request[FILE_USER]['id'];keys=request.query.get('ids','').split(',');limit=50*1024**2
        if not 1<=len(keys)<=100:raise web.HTTPBadRequest()
        # Bound the archive and build without awaiting: metadata/blobs cannot change
        # halfway through the snapshot. Stored ZIP avoids CPU-heavy compression.
        with self.mutation(),self.db() as db:
            allrows={r['id']:dict(r) for r in db.execute("SELECT * FROM files WHERE user_id=? AND state='live'",(uid,))}
            selected={};top=set(keys)
            for key in top:
                self.row(db,uid,key,'live')
                for r in self.descendants(db,uid,key,'live'):selected[r['id']]=r
            if len(selected)>1000 or sum(r['size'] for r in selected.values())>limit:raise web.HTTPBadRequest(text='Download up to 1,000 items or 50 MB as ZIP at a time.')
            output=io.BytesIO();names=set()
            with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_STORED) as z:
                for row in selected.values():
                    parts=[row['name']];p=row['parent'];seen=set()
                    while p in selected and p not in seen:seen.add(p);parts.insert(0,selected[p]['name']);p=selected[p]['parent']
                    name='/'.join(parts)+('/' if row['kind']=='folder' else '')
                    if name in names:raise web.HTTPConflict(text='Items from different folders have the same ZIP path. Download them separately.')
                    names.add(name)
                    if row['kind']=='folder':z.writestr(name,b'')
                    else:z.write(self.blob(uid,row['content_key'] or row['id']),name)
        return web.Response(body=output.getvalue(),headers={'Content-Type':'application/zip','Content-Disposition':'attachment; filename="mina-filer.zip"','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
