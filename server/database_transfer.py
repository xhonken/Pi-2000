"""Bounded MariaDB export/restore jobs, private to the originating login.

A transfer has a separate connection, never commits the editor's transaction,
and never invokes client programs or grants access to server filesystem paths.
"""
import asyncio
import base64
import json
import tempfile
import time
import aiomysql
from aiohttp import web
from database_admin import name

MAX_TRANSFER = 64 * 1024 * 1024
MAX_IMPORT = 16 * 1024 * 1024


def statements(text):
    """Split client SQL with DELIMITER, preserving routine bodies and comments.

Executable MariaDB/MySQL comments stay in statements for the server to process.
Backslash escaping follows the usual dump SQL mode; dumps changing the parser's
quote mode mid-file should be normalized by the originating client first.
"""
    delimiter=';'; start=0; i=0; quote=None; comment=None; line_start=True
    while i<len(text):
        c=text[i]; nxt=text[i:i+2]
        if comment=='line':
            if c=='\n': comment=None;line_start=True
            i+=1;continue
        if comment=='block':
            if nxt=='*/':comment=None;i+=2
            else:i+=1
            continue
        if quote:
            if c=='\\' and quote!='`':i+=2;continue
            if c==quote:
                if i+1<len(text) and text[i+1]==quote:i+=2;continue
                quote=None
            i+=1;continue
        if line_start:
            end=text.find('\n',i)
            if end<0:end=len(text)
            line=text[i:end].strip()
            if line.upper().startswith('DELIMITER '):
                prefix=text[start:i].strip()
                if prefix and any(not l.lstrip().startswith(('--','#')) and l.strip() for l in prefix.splitlines()):
                    raise ValueError('DELIMITER must occur between complete statements.')
                delimiter=line.split(None,1)[1].strip()
                if not delimiter or len(delimiter)>16 or any(c.isspace() for c in delimiter):raise ValueError('Invalid SQL delimiter.')
                i=end+1;start=i;continue
            if c not in ' \t\r':line_start=False
        if text.startswith(delimiter,i):
            value=text[start:i].strip()
            if value:yield value
            i+=len(delimiter);start=i;continue
        if c in "'\"`":quote=c
        elif c=='#' or (nxt=='--' and (i+2==len(text) or text[i+2].isspace())):comment='line'
        elif nxt=='/*':comment='block';i+=2;continue
        if c=='\n':line_start=True
        i+=1
    if quote or comment=='block':raise ValueError('Unclosed SQL quote or comment.')
    tail=text[start:].strip()
    if tail and any(not l.lstrip().startswith(('--','#')) and l.strip() for l in tail.splitlines()):yield tail


def literal(value):
    if value is None:return 'NULL'
    if isinstance(value,(int,float)):return str(value)
    if isinstance(value,bytes):return "X'"+value.hex()+"'"
    return "CONVERT(X'"+str(value).encode('utf8').hex()+"' USING utf8mb4)"


class Transfers:
    def __init__(self,manager):self.manager=manager;self.jobs={}

    def remove(self,key):
        job=self.jobs.pop(key,None)
        if job:
            if job.get('task') and not job['task'].done():job['task'].cancel()
            job['file'].close()

    async def handle(self,request):
        manager=self.manager;app=manager.app
        raw=bytearray()
        async for chunk in request.content.iter_chunked(65536):
            raw.extend(chunk)
            if len(raw)>MAX_IMPORT*2:raise web.HTTPRequestEntityTooLarge(max_size=MAX_IMPORT*2,actual_size=len(raw))
        data=json.loads(raw);app.require_current(request)
        if not isinstance(data,dict):raise web.HTTPBadRequest(text='A JSON object is required.')
        uid=request[app.USER]['id'];token=request[app.TOKEN];action=data.get('action')
        for key,job in list(self.jobs.items()):
            if time.monotonic()-job['used']>600 or not app.session_valid(app.SESSIONS.get(job['token'])):self.remove(key)
        if action in ('export','restore'):
            session=manager.session(request,data.get('session'))
            if len(self.jobs)>=4 or any(j['uid']==uid for j in self.jobs.values()):raise web.HTTPConflict(text='Close or cancel your current database transfer first.')
            database=data.get('database');name(database)
            if action=='restore':
                source=data.get('sql')
                if not isinstance(source,str) or not source.strip() or len(source.encode())>MAX_IMPORT:raise web.HTTPBadRequest(text='Choose a UTF-8 SQL file up to 16 MB.')
                # Parse completely before executing any SQL, so malformed scripts
                # do not cause partial writes just because the parser failed late.
                try:
                    sql=list(statements(source))
                    if len(sql)>100000:raise ValueError('The import exceeds 100,000 statements.')
                except ValueError as exc:raise web.HTTPBadRequest(text=str(exc))
            else:sql=None
            import secrets
            key=secrets.token_hex(24)
            job={'uid':uid,'token':token,'used':time.monotonic(),'state':'running','kind':action,'bytes':0,'rows':0,'completed':0,'object':'','error':'','file':tempfile.TemporaryFile(),'task':None,'total':len(sql) if sql is not None else 0}
            self.jobs[key]=job
            job['task']=asyncio.create_task(self.run(job,dict(session['settings']),session['password'],database,data,sql))
            return web.json_response({'job':key})
        key=data.get('job')
        job=self.jobs.get(key) if isinstance(key,str) else None
        if not job or job['uid']!=uid or job['token']!=token:raise web.HTTPNotFound(text='This transfer ended or belongs to another login.')
        job['used']=time.monotonic()
        if action=='close':self.remove(data['job']);return web.json_response({'ok':True})
        if action=='cancel':
            job['task'].cancel();await asyncio.gather(job['task'],return_exceptions=True)
            return web.json_response({'ok':True})
        if action=='status':return web.json_response({k:job[k] for k in ('state','kind','bytes','rows','completed','total','object','error')})
        if action=='read':
            if job['state']!='complete' or job['kind']!='export':raise web.HTTPConflict(text='Wait for a successful export before downloading.')
            offset=data.get('offset',0)
            if type(offset) is not int or not 0<=offset<=job['bytes']:raise web.HTTPBadRequest(text='Invalid export offset.')
            job['file'].seek(offset);chunk=job['file'].read(256*1024)
            return web.json_response({'data':base64.b64encode(chunk).decode(),'offset':offset+len(chunk),'done':offset+len(chunk)==job['bytes']})
        raise web.HTTPBadRequest(text='Unknown transfer operation.')

    async def run(self,job,settings,password,database,options,sql):
        conn=None
        try:
            async with asyncio.timeout(300):
                settings['database']=database
                conn=await self.manager.open_connection(settings,password)
                conn.transfer_mode=True
                if sql is None:await self.export(job,conn,database,options)
                else:
                    for statement in sql:
                        # Restore results are discarded with the same bounded reader.
                        await self.manager.execute(conn,statement)
                        job['completed']+=1
                    # Do not silently roll back imports ending with an open transaction.
                    if conn.server_status&1:await self.manager.execute(conn,'COMMIT')
                job['state']='complete'
        except asyncio.CancelledError:
            job['state']='cancelled';job['error']='Transfer cancelled. Completed restore statements may remain; inspect the database before retrying.'
        except Exception as exc:
            job['state']='failed'
            # Restore SQL may contain account passwords or private data. Never
            # expose SQL text from a server syntax error in a persistent job status.
            code=exc.args[0] if exc.args and isinstance(exc.args[0],int) else None
            job['error']=('MariaDB error '+str(code)+'. ' if code else '')+('Restore stopped after '+str(job['completed'])+' statements. Earlier writes may remain. Check the SQL file, grants and server compatibility.' if sql is not None else 'Export failed. Check object privileges, connection, concurrent schema changes and the 64 MB export / 2 MB packet limits. No complete backup was produced.')
        finally:
            if conn:conn.close()
            job['used']=time.monotonic()

    async def export(self,job,conn,database,options):
        def write(text):
            raw=text.encode();job['bytes']+=len(raw)
            if job['bytes']>MAX_TRANSFER:raise ValueError('Export exceeds 64 MB.')
            job['file'].write(raw)
        async def query(sql,args=None):return (await self.manager.execute(conn,sql,args))[0]
        await query("SET SESSION SQL_MODE='NO_AUTO_VALUE_ON_ZERO'")
        tables=await query("SELECT TABLE_NAME, TABLE_TYPE, ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=%s ORDER BY TABLE_NAME",(database,))
        # A transaction gives one InnoDB data snapshot, without global locks.
        await query('SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ')
        await query('START TRANSACTION WITH CONSISTENT SNAPSHOT')
        write('-- Pi-2000Web MariaDB export\n-- InnoDB snapshot; avoid concurrent DDL. Non-transactional tables are not snapshot-consistent.\n-- Restore to the original database name: definitions may contain qualified references. Account grants are not included.\nSET @PI2000_OLD_SQL_MODE=@@SQL_MODE;\nSET SQL_MODE=\'NO_AUTO_VALUE_ON_ZERO\';\nSET @PI2000_OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS;\nSET FOREIGN_KEY_CHECKS=0;\nSET NAMES utf8mb4;\n')
        views=[]
        for table,kind,engine in tables['rows']:
            job['object']=table
            if kind=='VIEW':views.append(table);continue
            definition=await query('SHOW CREATE TABLE '+name(database)+'.'+name(table))
            write('\n'+definition['rows'][0][1]+';\n')
            if options.get('include_data',True):
                # Generated columns must not be explicitly assigned on restore.
                meta=await query('SHOW FULL COLUMNS FROM '+name(database)+'.'+name(table))
                names=[r[0] for r in meta['rows'] if 'GENERATED' not in str(r[6])]
                if names:
                    cursor=await conn.cursor(aiomysql.SSCursor)
                    try:
                        await cursor.execute('SELECT '+','.join(name(n) for n in names)+' FROM '+name(database)+'.'+name(table))
                        while True:
                            row=await cursor.fetchone()
                            if row is None:break
                            write('INSERT INTO '+name(table)+' ('+','.join(name(n) for n in names)+') VALUES ('+','.join(literal(v) for v in row)+');\n')
                            job['rows']+=1
                            if job['rows']%100==0:await asyncio.sleep(0)
                    except BaseException:conn.close();raise
                    finally:
                        if not conn.closed:await cursor.close()
            job['completed']+=1
        # Views in dependency order: retry ordering using metadata dependencies
        # is version-specific, so create temporary stand-ins, then replace them.
        async def write_views():
            for view in views:
                meta=await query('SHOW FULL COLUMNS FROM '+name(database)+'.'+name(view))
                write('CREATE TABLE '+name(view)+' ('+','.join(name(r[0])+' '+r[1] for r in meta['rows'])+');\n')
            for view in views:
                definition=await query('SHOW CREATE VIEW '+name(database)+'.'+name(view))
                write('DROP TABLE '+name(view)+';\n'+definition['rows'][0][1]+';\n');job['completed']+=1
        if options.get('include_objects',True):
            for kind,statement in [('PROCEDURE',"SELECT ROUTINE_NAME FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA=%s AND ROUTINE_TYPE='PROCEDURE'"),('FUNCTION',"SELECT ROUTINE_NAME FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA=%s AND ROUTINE_TYPE='FUNCTION'"),('TRIGGER',"SELECT TRIGGER_NAME FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA=%s"),('EVENT',"SELECT EVENT_NAME FROM information_schema.EVENTS WHERE EVENT_SCHEMA=%s")]:
                if kind=='TRIGGER':await write_views()
                objects=await query(statement,(database,))
                for (obj,) in objects['rows']:
                    job['object']=obj
                    definition=await query('SHOW CREATE '+kind+' '+name(database)+'.'+name(obj))
                    index=next((i for i,c in enumerate(definition['columns']) if c.startswith('Create ') or c=='SQL Original Statement'),None)
                    if index is None or not definition['rows'][0][index]:raise ValueError('Missing object definition.')
                    value=definition['rows'][0][index]
                    delimiter=';;PI2000;;'
                    while delimiter in value:delimiter+='X'
                    write('\nDELIMITER '+delimiter+'\n'+value+delimiter+'\nDELIMITER ;\n');job['completed']+=1
        else:await write_views()
        write('\nSET FOREIGN_KEY_CHECKS=@PI2000_OLD_FOREIGN_KEY_CHECKS;\nSET SQL_MODE=@PI2000_OLD_SQL_MODE;\n-- Export completed successfully.\n')
        job['file'].flush();await query('ROLLBACK')
