"""Private HTTP request collections and bounded requests from the development Pi."""
import asyncio
import ipaddress
import json
import re
import secrets
import socket
import time
from urllib.parse import urlsplit
import aiohttp
from aiohttp import web

# Local development endpoints are explicit. Platform/API/Caddy administration
# ports cannot be reached through this tool, even through a DNS alias.
DEV_PORTS = {3000,3001,4000,5000,5001,5173,8000,8001,8080,8081,9000}


def local_addresses():
    values={'127.0.0.1','::1'}
    try:
        values.update(row[4][0] for row in socket.getaddrinfo(socket.gethostname(),None))
        # An unconnected UDP socket reveals the selected interface, without
        # sending a datagram. Include both default-route address families.
        for family,target in ((socket.AF_INET,('192.0.2.1',9)),(socket.AF_INET6,('2001:db8::1',9))):
            try:
                with socket.socket(family,socket.SOCK_DGRAM) as sock:sock.connect(target);values.add(sock.getsockname()[0])
            except OSError:pass
    except OSError:pass
    return values


def validate_address(value,port,local):
    address=ipaddress.ip_address(value.split('%')[0]);address=getattr(address,'ipv4_mapped',None) or address
    if address.is_unspecified or address.is_multicast or address.is_link_local or (address.is_reserved and not address.is_loopback):
        raise web.HTTPBadRequest(text='This network address is not available to API Tester.')
    if (address.is_loopback or str(address) in local) and port not in DEV_PORTS:
        raise web.HTTPBadRequest(text='Pi-2000 platform endpoints are protected. Local development uses ports 3000, 3001, 4000, 5000, 5001, 5173, 8000, 8001, 8080, 8081 or 9000.')


class PinnedResolver(aiohttp.abc.AbstractResolver):
    def __init__(self,records):self.records=records
    async def resolve(self,host,port=0,family=socket.AF_INET):return self.records
    async def close(self):pass


class ApiClient:
    def __init__(self,app,cipher):self.app=app;self.cipher=cipher;self.running=set()
    def initialize(self):
        with self.app.db() as db:db.execute('CREATE TABLE IF NOT EXISTS api_requests(id TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,data TEXT NOT NULL)')

    def validate(self,data):
        if not isinstance(data,dict):raise web.HTTPBadRequest(text='Enter request details.')
        url=data.get('url','');method=data.get('method','GET');headers=data.get('headers',{});body=data.get('body','');name=data.get('name','Untitled request')
        if not isinstance(url,str) or len(url)>8192 or not isinstance(body,str) or len(body.encode())>1024*1024 or not isinstance(name,str) or not 1<=len(name)<=100:raise web.HTTPBadRequest(text='Request name, URL or body is too large.')
        try:parsed=urlsplit(url);port=parsed.port
        except ValueError:raise web.HTTPBadRequest(text='Enter a valid HTTP or HTTPS URL.')
        if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username is not None or parsed.password is not None or any(c in url for c in '\r\n\0'):raise web.HTTPBadRequest(text='Use HTTP or HTTPS. Put authentication in the Authorization header.')
        if method not in ('GET','HEAD','POST','PUT','PATCH','DELETE','OPTIONS'):raise web.HTTPBadRequest(text='Unsupported HTTP method.')
        if not isinstance(headers,dict) or len(headers)>100:raise web.HTTPBadRequest(text='Use up to 100 request headers.')
        for key,value in headers.items():
            if not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+",key) or not isinstance(value,str) or len(value)>8192 or any(c in value for c in '\r\n\0'):raise web.HTTPBadRequest(text='Invalid HTTP header.')
            if key.lower() in ('host','connection','content-length','transfer-encoding','proxy-authorization','proxy-connection','upgrade'):raise web.HTTPBadRequest(text='This transport header is managed by API Tester.')
        return {'name':name,'url':url,'method':method,'headers':headers,'body':body}

    async def read(self,request):
        raw=bytearray()
        async for chunk in request.content.iter_chunked(65536):
            raw.extend(chunk)
            if len(raw)>2*1024*1024:raise web.HTTPRequestEntityTooLarge(max_size=2*1024*1024,actual_size=len(raw))
        self.app.require_current(request);return json.loads(raw)

    async def collections(self,request):
        uid=request[self.app.USER]['id'];key=request.match_info.get('id')
        with self.app.db() as db:
            if request.method=='GET':return web.json_response({'requests':[dict(json.loads(self.cipher.decrypt(r['data'].encode())),id=r['id']) for r in db.execute('SELECT * FROM api_requests WHERE user_id=?',(uid,))]})
            if key and not db.execute('SELECT 1 FROM api_requests WHERE id=? AND user_id=?',(key,uid)).fetchone():raise web.HTTPNotFound(text='Request not found.')
            if request.method=='DELETE':db.execute('DELETE FROM api_requests WHERE id=? AND user_id=?',(key,uid));return web.json_response({'ok':True})
        data=self.validate(await self.read(request));key=key or secrets.token_hex(16)
        secret=self.cipher.encrypt(json.dumps(data).encode()).decode()
        with self.app.db() as db:
            rows=db.execute('SELECT id,LENGTH(data) AS size FROM api_requests WHERE user_id=?',(uid,)).fetchall()
            if len(rows)>=100 and key not in [r['id'] for r in rows]:raise web.HTTPConflict(text='Save up to 100 API requests.')
            if sum(r['size'] for r in rows if r['id']!=key)+len(secret)>8*1024*1024:raise web.HTTPConflict(text='Saved API requests exceed the 8 MB collection limit.')
            db.execute('INSERT INTO api_requests VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data',(key,uid,secret))
        return web.json_response({**data,'id':key})

    async def send(self,request):
        uid=request[self.app.USER]['id']
        if uid in self.running or len(self.running)>=4:raise web.HTTPTooManyRequests(text='An API request is already running. Try again shortly.')
        data=self.validate(await self.read(request));parsed=urlsplit(data['url']);port=parsed.port or (443 if parsed.scheme=='https' else 80)
        if uid in self.running or len(self.running)>=4:raise web.HTTPTooManyRequests(text='An API request is already running.')
        self.running.add(uid)
        try:
            async with asyncio.timeout(30):
                loop=asyncio.get_running_loop();addresses=await loop.getaddrinfo(parsed.hostname,port,type=socket.SOCK_STREAM)
                local=local_addresses()
                # Include the configured site address, including additional NICs.
                site=urlsplit(self.app.ORIGIN).hostname
                if site:
                    try:local.update(r[4][0] for r in await loop.getaddrinfo(site,None,type=socket.SOCK_STREAM))
                    except OSError:pass
                records=[]
                for family,_,proto,_,address in addresses:
                    validate_address(address[0],port,local)
                    records.append({'hostname':parsed.hostname,'host':address[0],'port':port,'family':family,'proto':proto,'flags':socket.AI_NUMERICHOST})
                connector=aiohttp.TCPConnector(resolver=PinnedResolver(records),use_dns_cache=False,limit=1)
                started=time.monotonic()
                async with aiohttp.ClientSession(connector=connector,cookie_jar=aiohttp.DummyCookieJar(),trust_env=False,auto_decompress=False,timeout=aiohttp.ClientTimeout(total=25)) as client:
                    async with client.request(data['method'],data['url'],headers=data['headers'],data=data['body'].encode() if data['body'] else None,allow_redirects=False) as response:
                        raw=bytearray();truncated=False
                        async for chunk in response.content.iter_chunked(65536):
                            raw.extend(chunk)
                            if len(raw)>1024*1024:del raw[1024*1024:];truncated=True;break
                        self.app.require_current(request)
                        import base64
                        return web.json_response({'status':response.status,'reason':response.reason,'headers':list(response.headers.items()),'body':raw.decode('utf-8',errors='replace'),'base64':base64.b64encode(raw).decode(),'bytes':len(raw),'truncated':truncated,'elapsed_ms':round((time.monotonic()-started)*1000),'url':str(response.url)})
        except (aiohttp.ClientError,OSError,asyncio.TimeoutError):raise web.HTTPBadGateway(text='The HTTP request failed. Check the address, network access and TLS certificate. The request may have reached the server; check before retrying writes.')
        finally:self.running.discard(uid)
