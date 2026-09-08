"""MariaDB administration using only the connected account's authority.

Plans are short-lived, single-use and scoped to an authenticated SQL session.
Passwords never enter generated SQL previews or persistent query drafts.
"""
import re
import secrets
import time
from aiohttp import web
from pymysql import MySQLError


def name(value):
    if not isinstance(value, str) or not value or len(value) > 64 or '\0' in value:
        raise web.HTTPBadRequest(text='Enter an object name of 1–64 characters.')
    return '`' + value.replace('`', '``') + '`'


def word(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_]+', value):
        raise web.HTTPBadRequest(text='Invalid engine, character set or collation name.')
    return value


def choice(value, allowed):
    if value not in allowed:
        raise web.HTTPBadRequest(text='Choose a supported operation or option.')
    return value


def integer(value, maximum=2147483647):
    if type(value) is not int or not 0 <= value <= maximum:
        raise web.HTTPBadRequest(text='Enter a non-negative whole number within the allowed range.')
    return str(value)


PRIVILEGES = ('SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'DROP', 'REFERENCES',
    'INDEX', 'ALTER', 'CREATE TEMPORARY TABLES', 'LOCK TABLES', 'EXECUTE', 'CREATE VIEW',
    'SHOW VIEW', 'CREATE ROUTINE', 'ALTER ROUTINE', 'EVENT', 'TRIGGER', 'CREATE USER',
    'PROCESS', 'RELOAD', 'SHOW DATABASES', 'REPLICATION CLIENT', 'REPLICATION SLAVE',
    'SUPER', 'ALL PRIVILEGES', 'USAGE')


def build(data, quote):
    """Return statements and redacted previews; identifiers cannot add SQL."""
    operation = data.get('operation')
    statements, previews, hidden = [], [], []
    def add(sql, preview=None):
        statements.append(sql); previews.append(preview or sql)
    def account(prefix=''):
        user, host = data.get(prefix+'user', ''), data.get(prefix+'host', '')
        if not isinstance(user, str) or not user or len(user)>128 or not isinstance(host,str) or not host or len(host)>255 or '\0' in user+host:
            raise web.HTTPBadRequest(text='Enter both the MariaDB user name and allowed host.')
        return quote(user)+'@'+quote(host)
    def password():
        value=data.get('password')
        if not isinstance(value,str) or len(value)>1024 or '\0' in value:
            raise web.HTTPBadRequest(text='Enter a valid password.')
        hidden.append(value)
        return quote(value)
    def database(): return name(data.get('database'))
    def table(): return database()+'.'+name(data.get('table'))
    def options():
        return (' CHARACTER SET '+word(data['charset']) if data.get('charset') else '')+(' COLLATE '+word(data['collation']) if data.get('collation') else '')
    # Database grants treat underscores and percent signs as wildcards. Escape
    # them so a database created for an account never grants access to siblings.
    def grant_database(): return name(data['database'].replace('\\','\\\\').replace('_','\\_').replace('%','\\%'))
    if operation in ('create_database','alter_database','drop_database'):
        add(operation.split('_')[0].upper()+' DATABASE '+database()+(options() if operation!='drop_database' else ''))
    elif operation=='create_user':
        target=account(); value=password()
        add('CREATE USER '+target+' IDENTIFIED BY '+value, 'CREATE USER '+target+" IDENTIFIED BY '[password hidden]'")
        if data.get('database'):
            if data.get('create_database') is True:
                add('CREATE DATABASE '+database()+options())
            add('GRANT ALL PRIVILEGES ON '+grant_database()+'.* TO '+target)
    elif operation=='password':
        target=account();value=password()
        add('ALTER USER '+target+' IDENTIFIED BY '+value,'ALTER USER '+target+" IDENTIFIED BY '[password hidden]'")
    elif operation=='rename_user': add('RENAME USER '+account()+' TO '+account('new_'))
    elif operation=='drop_user': add('DROP USER '+account())
    elif operation=='account_options':
        sql='ALTER USER '+account()
        tls=choice(data.get('tls','KEEP'),('KEEP','NONE','SSL','X509'))
        if tls!='KEEP': sql+=' REQUIRE '+tls
        limits=[]
        for key in ('MAX_QUERIES_PER_HOUR','MAX_UPDATES_PER_HOUR','MAX_CONNECTIONS_PER_HOUR','MAX_USER_CONNECTIONS'):
            if key in data: limits.append(key+' '+integer(data[key]))
        if limits: sql+=' WITH '+' '.join(limits)
        lock=choice(data.get('lock','KEEP'),('KEEP','LOCK','UNLOCK'))
        if lock!='KEEP':sql+=' ACCOUNT '+lock
        expiry=choice(data.get('expiry','KEEP'),('KEEP','EXPIRE','NEVER','DEFAULT','INTERVAL'))
        if expiry!='KEEP':sql+=' PASSWORD EXPIRE'+(' INTERVAL '+integer(data.get('expiry_days'),65535)+' DAY' if expiry=='INTERVAL' else ' '+expiry if expiry in ('NEVER','DEFAULT') else '')
        add(sql)
    elif operation in ('grant','revoke'):
        target=name(data.get('user')) if data.get('principal')=='role' else account(); scope=choice(data.get('scope'),('database','table','procedure','function','global'))
        privileges=data.get('privileges',[])
        if not isinstance(privileges,list) or not privileges or len(privileges)>len(PRIVILEGES):
            raise web.HTTPBadRequest(text='Select at least one privilege.')
        columns=data.get('columns',[])
        if not isinstance(columns,list) or len(columns)>100:raise web.HTTPBadRequest(text='Use up to 100 privilege columns.')
        if columns and (scope!='table' or any(p not in ('SELECT','INSERT','UPDATE','REFERENCES') for p in privileges)):raise web.HTTPBadRequest(text='Column grants support SELECT, INSERT, UPDATE and REFERENCES on a table.')
        privilege=', '.join(choice(p,PRIVILEGES)+(' ('+', '.join(name(c) for c in columns)+')' if columns else '') for p in privileges)
        destination='*.*' if scope=='global' else grant_database()+'.*' if scope=='database' else table()
        if scope in ('procedure','function'): destination=scope.upper()+' '+destination
        add(operation.upper()+' '+privilege+' ON '+destination+(' TO ' if operation=='grant' else ' FROM ')+target+(' WITH GRANT OPTION' if operation=='grant' and data.get('grant_option') is True else ''))
    elif operation=='revoke_grant_option':
        add('REVOKE GRANT OPTION ON '+(grant_database()+'.*' if data.get('scope')=='database' else '*.*')+' FROM '+account())
    elif operation in ('create_role','drop_role'): add(operation.split('_')[0].upper()+' ROLE '+name(data.get('role')))
    elif operation in ('grant_role','revoke_role'):
        add(operation.split('_')[0].upper()+' '+name(data.get('role'))+(' TO ' if operation=='grant_role' else ' FROM ')+account()+(' WITH ADMIN OPTION' if operation=='grant_role' and data.get('admin_option') is True else ''))
    elif operation=='default_role': add('SET DEFAULT ROLE '+(name(data['role']) if data.get('role') else 'NONE')+' FOR '+account())
    elif operation=='create_table':
        columns=data.get('columns')
        if not isinstance(columns,list) or not 1<=len(columns)<=100:
            raise web.HTTPBadRequest(text='Define between 1 and 100 columns.')
        add('CREATE TABLE '+table()+' ('+', '.join(column(c,quote) for c in columns)+') ENGINE='+word(data.get('engine','InnoDB'))+options())
    elif operation in ('add_column','modify_column'):
        add('ALTER TABLE '+table()+(' ADD COLUMN ' if operation=='add_column' else ' MODIFY COLUMN ')+column(data.get('column',{}),quote))
    elif operation=='drop_column': add('ALTER TABLE '+table()+' DROP COLUMN '+name(data.get('column_name')))
    elif operation=='rename_column': add('ALTER TABLE '+table()+' RENAME COLUMN '+name(data.get('column_name'))+' TO '+name(data.get('new_name')))
    elif operation=='create_index':
        kind=choice(data.get('kind','INDEX'),('INDEX','UNIQUE INDEX','FULLTEXT INDEX','SPATIAL INDEX','PRIMARY KEY'))
        columns=data.get('columns',[])
        if not isinstance(columns,list) or not 1<=len(columns)<=32: raise web.HTTPBadRequest(text='Select index columns in order.')
        add('ALTER TABLE '+table()+' ADD '+kind+(' '+name(data.get('index')) if kind!='PRIMARY KEY' else '')+' ('+', '.join(name(c) for c in columns)+')')
    elif operation=='drop_index': add('ALTER TABLE '+table()+(' DROP PRIMARY KEY' if data.get('index')=='PRIMARY' else ' DROP INDEX '+name(data.get('index'))))
    elif operation=='create_foreign_key':
        columns, refs=data.get('columns',[]),data.get('reference_columns',[])
        if not isinstance(columns,list) or not isinstance(refs,list) or not 1<=len(columns)<=32 or len(columns)!=len(refs): raise web.HTTPBadRequest(text='Foreign key columns must match referenced columns.')
        actions=('RESTRICT','CASCADE','SET NULL','NO ACTION')
        add('ALTER TABLE '+table()+' ADD CONSTRAINT '+name(data.get('constraint'))+' FOREIGN KEY ('+', '.join(name(c) for c in columns)+') REFERENCES '+name(data.get('reference_database'))+'.'+name(data.get('reference_table'))+' ('+', '.join(name(c) for c in refs)+') ON DELETE '+choice(data.get('on_delete','RESTRICT'),actions)+' ON UPDATE '+choice(data.get('on_update','RESTRICT'),actions))
    elif operation=='drop_foreign_key': add('ALTER TABLE '+table()+' DROP FOREIGN KEY '+name(data.get('constraint')))
    elif operation=='rename_table': add('RENAME TABLE '+table()+' TO '+name(data.get('destination_database') or data.get('database'))+'.'+name(data.get('new_name')))
    elif operation=='copy_table':
        destination=name(data.get('destination_database') or data.get('database'))+'.'+name(data.get('new_name'))
        add('CREATE TABLE '+destination+' LIKE '+table())
        if data.get('include_data') is True: add('INSERT INTO '+destination+' SELECT * FROM '+table())
    elif operation=='table_options':
        sql='ALTER TABLE '+table()+' ENGINE='+word(data.get('engine','InnoDB'))
        if data.get('collation'): sql+=' DEFAULT COLLATE='+word(data['collation'])
        if data.get('convert_charset'): sql+=', CONVERT TO CHARACTER SET '+word(data['convert_charset'])+(' COLLATE '+word(data['collation']) if data.get('collation') else '')
        comment=data.get('comment','')
        if not isinstance(comment,str) or len(comment)>2048: raise web.HTTPBadRequest(text='Table comments support up to 2,048 characters.')
        sql+=' COMMENT='+quote(comment)
        if 'auto_increment' in data: sql+=' AUTO_INCREMENT='+integer(data['auto_increment'],9007199254740991)
        add(sql)
    elif operation in ('drop_table','truncate_table','check_table','analyze_table','optimize_table','repair_table'):
        add(operation.split('_')[0].upper()+' TABLE '+table())
    elif operation=='drop_object':
        add('DROP '+choice(data.get('kind'),('VIEW','PROCEDURE','FUNCTION','TRIGGER','EVENT'))+' '+database()+'.'+name(data.get('object')))
    elif operation=='event_state': add('ALTER EVENT '+database()+'.'+name(data.get('object'))+' '+choice(data.get('state'),('ENABLE','DISABLE','DISABLE ON SLAVE')))
    elif operation=='kill_query': add('KILL QUERY '+integer(data.get('process'),9007199254740991))
    else: raise web.HTTPBadRequest(text='Unknown administration operation.')
    return statements, previews, hidden


def column(data, quote):
    if not isinstance(data,dict): raise web.HTTPBadRequest(text='Invalid column definition.')
    kind=choice(data.get('type'),('TINYINT','SMALLINT','MEDIUMINT','INT','BIGINT','DECIMAL','FLOAT','DOUBLE','BOOLEAN','CHAR','VARCHAR','BINARY','VARBINARY','TEXT','TINYTEXT','MEDIUMTEXT','LONGTEXT','BLOB','TINYBLOB','MEDIUMBLOB','LONGBLOB','DATE','TIME','DATETIME','TIMESTAMP','YEAR','JSON','ENUM','SET','GEOMETRY','POINT','LINESTRING','POLYGON'))
    sql=name(data.get('name'))+' '+kind
    length=data.get('length','')
    if kind in ('ENUM','SET'):
        values=data.get('values',[])
        if not isinstance(values,list) or not 1<=len(values)<=1000 or any(not isinstance(v,str) or len(v)>255 for v in values): raise web.HTTPBadRequest(text='Enter enumeration values.')
        sql+='('+', '.join(quote(v) for v in values)+')'
    elif length:
        if not isinstance(length,str) or not re.fullmatch(r'\d{1,5}(,\s*\d{1,2})?',length): raise web.HTTPBadRequest(text='Length must be a number or precision,scale.')
        sql+='('+length+')'
    if data.get('unsigned') is True: sql+=' UNSIGNED'
    sql+=' NULL' if data.get('nullable') is True else ' NOT NULL'
    default=data.get('default_mode','none')
    choice(default,('none','null','value','timestamp'))
    if default=='null': sql+=' DEFAULT NULL'
    elif default=='timestamp': sql+=' DEFAULT CURRENT_TIMESTAMP'
    elif default=='value':
        value=data.get('default','')
        if not isinstance(value,str) or len(value)>8192: raise web.HTTPBadRequest(text='Invalid default value.')
        sql+=' DEFAULT '+quote(value)
    if data.get('auto_increment') is True: sql+=' AUTO_INCREMENT'
    if data.get('primary') is True: sql+=' PRIMARY KEY'
    return sql


async def handle(manager, session, data):
    conn=session['conn']; action=data['action']
    if action=='admin_preview':
        statements, previews, hidden=build(data,conn.escape)
        token=secrets.token_hex(24)
        session['admin_plan']={'id':token,'expires':time.monotonic()+300,'statements':statements,'hidden':hidden}
        return {'plan':token,'sql':';\n'.join(previews)+';', 'steps':len(statements),
            'notice':'Review the target and each statement. Schema and account changes can commit immediately. If a later statement fails, earlier changes remain.'}
    if action=='admin_apply':
        plan=session.get('admin_plan')
        if not plan or plan['id']!=data.get('plan') or plan['expires']<time.monotonic():
            raise web.HTTPConflict(text='The administration preview expired or was already used. Review the operation again.')
        session.pop('admin_plan',None)
        completed=0; results=[]
        for statement in plan['statements']:
            try: results.extend(await manager.execute(conn,statement));completed+=1
            except MySQLError as exc:
                detail=str(exc)[:1500]
                for secret in plan['hidden']:
                    if secret: detail=detail.replace(secret,'[password hidden]').replace(conn.escape(secret),'[password hidden]')
                # Account SQL syntax errors can contain escaped fragments of secrets.
                if plan['hidden']: detail='MariaDB error '+str(exc.args[0])+'. Check account permissions, server version and whether the account or database already exists.'
                raise web.HTTPBadRequest(text=f'{completed} of {len(plan["statements"])} statements completed. Earlier changes may remain. {detail}')
        return {'results':results,'completed':completed,'elapsed_ms':0}
    if action=='admin_search':
        database=data.get('database');name(database)
        term=data.get('term')
        if not isinstance(term,str) or not 1<=len(term)<=200:raise web.HTTPBadRequest(text='Enter search text of 1–200 characters.')
        columns=(await manager.execute(conn,"SELECT TABLE_NAME,COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=%s AND DATA_TYPE IN ('char','varchar','tinytext','text','mediumtext','longtext','enum','set') ORDER BY TABLE_NAME,ORDINAL_POSITION LIMIT 1000",(database,)))[0]['rows']
        tables={}
        for table,column_name in columns:tables.setdefault(table,[]).append(column_name)
        matches=[];searched=0;limited=len(tables)>50 or len(columns)==1000
        value='%'+term.replace('!','!!').replace('%','!%').replace('_','!_')+'%'
        for table,column_names in list(tables.items())[:50]:
            if len(column_names)>30:limited=True
            column_names=column_names[:30]
            sql='SELECT '+','.join(name(c) for c in column_names)+' FROM '+name(database)+'.'+name(table)+' WHERE '+' OR '.join(name(c)+" LIKE %s ESCAPE '!'" for c in column_names)+' LIMIT 20'
            result=(await manager.execute(conn,sql,tuple(value for _ in column_names)))[0]
            searched+=1
            if len(result['rows'])==20:limited=True
            # Return matching rows as JSON previews so server collation, not a
            # second Python comparison, determines which text matched.
            import json
            for row in result['rows']:
                matches.append([table,json.dumps(dict(zip(column_names,row)),ensure_ascii=False)[:4000]])
                if len(matches)>=250:limited=True;break
            if len(matches)>=250:break
        return {'results':[{'columns':['Table','Matching row preview'],'rows':matches,'affected':len(matches),'insert_id':None}], 'elapsed_ms':0,'searched_tables':searched,'limited':limited}
    section=data.get('section'); db=data.get('database'); table=data.get('table'); parameters=None
    if section=='databases': sql='SELECT SCHEMA_NAME AS Name, DEFAULT_CHARACTER_SET_NAME AS Charset, DEFAULT_COLLATION_NAME AS Collation FROM information_schema.SCHEMATA ORDER BY SCHEMA_NAME'
    elif section=='accounts': sql='SELECT User, Host, plugin AS Authentication, is_role AS Role, ssl_type AS TLS, max_questions AS Queries_per_hour, max_updates AS Updates_per_hour, max_connections AS Connections_per_hour, max_user_connections AS Concurrent_connections FROM mysql.user ORDER BY User, Host'
    elif section=='grants':
        user,host=data.get('user'),data.get('host')
        if not isinstance(user,str) or not isinstance(host,str): raise web.HTTPBadRequest(text='Select an account.')
        sql='SHOW GRANTS FOR '+conn.escape(user)+'@'+conn.escape(host)
    elif section=='my_grants': sql='SHOW GRANTS'
    elif section=='collations': sql='SHOW COLLATION'
    elif section=='engines': sql='SHOW ENGINES'
    elif section=='privileges': sql='SHOW PRIVILEGES'
    elif section=='status': sql='SHOW GLOBAL STATUS'
    elif section=='variables': sql='SHOW GLOBAL VARIABLES'
    elif section=='processes': sql='SHOW FULL PROCESSLIST'
    elif section=='tables':
        sql='SELECT TABLE_NAME AS Name, TABLE_TYPE AS Type, ENGINE AS Engine, TABLE_ROWS AS Estimated_rows, DATA_LENGTH AS Data_bytes, INDEX_LENGTH AS Index_bytes, TABLE_COLLATION AS Collation, TABLE_COMMENT AS Comment FROM information_schema.TABLES WHERE TABLE_SCHEMA=%s ORDER BY TABLE_NAME';parameters=(db,)
    elif section=='columns': sql='SHOW FULL COLUMNS FROM '+name(db)+'.'+name(table)
    elif section=='indexes': sql='SHOW INDEX FROM '+name(db)+'.'+name(table)
    elif section=='relations':
        sql='SELECT k.CONSTRAINT_NAME, k.TABLE_NAME, k.COLUMN_NAME, k.REFERENCED_TABLE_SCHEMA, k.REFERENCED_TABLE_NAME, k.REFERENCED_COLUMN_NAME, r.UPDATE_RULE, r.DELETE_RULE FROM information_schema.KEY_COLUMN_USAGE k JOIN information_schema.REFERENTIAL_CONSTRAINTS r ON k.CONSTRAINT_SCHEMA=r.CONSTRAINT_SCHEMA AND k.CONSTRAINT_NAME=r.CONSTRAINT_NAME AND k.TABLE_NAME=r.TABLE_NAME WHERE k.TABLE_SCHEMA=%s AND k.REFERENCED_TABLE_NAME IS NOT NULL ORDER BY k.TABLE_NAME,k.CONSTRAINT_NAME,k.ORDINAL_POSITION';parameters=(db,)
    elif section=='objects':
        sql="SELECT TABLE_NAME AS Name, 'VIEW' AS Type FROM information_schema.VIEWS WHERE TABLE_SCHEMA=%s UNION ALL SELECT ROUTINE_NAME, ROUTINE_TYPE FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA=%s UNION ALL SELECT TRIGGER_NAME,'TRIGGER' FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA=%s UNION ALL SELECT EVENT_NAME,'EVENT' FROM information_schema.EVENTS WHERE EVENT_SCHEMA=%s ORDER BY Type,Name";parameters=(db,db,db,db)
    elif section=='definition': sql='SHOW CREATE '+choice(data.get('kind'),('TABLE','VIEW','PROCEDURE','FUNCTION','TRIGGER','EVENT'))+' '+name(db)+'.'+name(data.get('object'))
    else: raise web.HTTPBadRequest(text='Unknown administration view.')
    results=await manager.execute(conn,sql,parameters)
    if section in ('grants','my_grants'):
        for result in results:
            result['rows']=[[re.sub(r'(?i) IDENTIFIED .*?(?= REQUIRE | WITH |$)',' IDENTIFIED [authentication hidden]',str(v)) for v in row] for row in result['rows']]
    return {'results':results,'elapsed_ms':0}
