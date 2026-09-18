"""Bounded IPTV catalogue parsing and public-network-only HTTP transport.

Source URLs are secrets. Errors must never interpolate a URL or upstream body.
DNS is resolved and pinned anew for every redirect/request, including HLS children.
"""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
import hashlib
import ipaddress
import json
import re
import socket
from urllib.parse import urlsplit, urljoin, parse_qs, urlencode, quote
import xml.etree.ElementTree as ET
import zlib

import aiohttp
import ijson
from aiohttp import web
from api_client import PinnedResolver, local_addresses

MAX_BYTES = 32 * 1024**2
MAX_ITEMS = 50000
ATTR = re.compile(r'([\w-]+)\s*=\s*(?:"([^"]*)"|\x27([^\x27]*)\x27|([^\s,]+))')


def attrs(text):
    return {m[1].lower(): next((v for v in m.groups()[1:] if v is not None), '') for m in ATTR.finditer(text)}


def text(value, maximum=240):
    return str(value or '').replace('\x00', '')[:maximum]


def url(value):
    try:
        if not isinstance(value, str) or not 1 <= len(value) <= 8192 or any(ord(c) < 33 for c in value):
            raise ValueError()
        p = urlsplit(value)
        if p.scheme not in ('http', 'https') or not p.hostname or p.fragment or (p.port is not None and not 1 <= p.port <= 65535):
            raise ValueError()
        if p.hostname.lower() in ('localhost', 'metadata.google.internal') or '%' in p.hostname:
            raise ValueError()
    except ValueError:
        raise web.HTTPBadRequest(text='Use a valid public HTTP or HTTPS media address.') from None
    return value


def public_ip(value, own=()):
    address = ipaddress.ip_address(value)
    address = address.ipv4_mapped if getattr(address, 'ipv4_mapped', None) else address
    if not address.is_global or str(address) in own or address.is_multicast:
        raise web.HTTPBadRequest(text='IPTV cannot contact local, private or platform network addresses.')


class Network:
    @asynccontextmanager
    async def open(self, target, headers=None):
        # Only controlled, per-entry UA/Referer headers are accepted by callers.
        target = url(target)
        headers = {'User-Agent': 'Pi-2000 IPTV/1.0', 'Accept-Encoding': 'identity', **(headers or {})}
        try:
            for _ in range(6):
                p = urlsplit(target); port = p.port or (443 if p.scheme == 'https' else 80)
                records = []
                async with asyncio.timeout(10):
                    addresses = await asyncio.get_running_loop().getaddrinfo(p.hostname, port, type=socket.SOCK_STREAM)
                own = local_addresses()
                for family, _, proto, _, address in addresses:
                    public_ip(address[0], own)
                    records.append({'hostname':p.hostname, 'host':address[0], 'port':port, 'family':family, 'proto':proto, 'flags':socket.AI_NUMERICHOST})
                if not records: raise web.HTTPBadGateway(text='The media host could not be resolved.')
                connector = aiohttp.TCPConnector(resolver=PinnedResolver(records), use_dns_cache=False, limit=1)
                async with aiohttp.ClientSession(connector=connector, trust_env=False,
                        cookie_jar=aiohttp.DummyCookieJar(), auto_decompress=False,
                        timeout=aiohttp.ClientTimeout(total=None, connect=12, sock_read=20)) as client:
                    async with client.get(target, headers=headers, allow_redirects=False) as response:
                        if response.status in (301,302,303,307,308):
                            destination = url(urljoin(target, response.headers.get('Location','')))
                            # Never propagate HTTP Basic credentials or custom
                            # referers from one origin to another implicitly.
                            new = urlsplit(destination)
                            if (new.scheme,new.hostname,new.port) != (p.scheme,p.hostname,p.port):
                                headers.pop('Referer',None)
                                if new.username is not None:
                                    raise web.HTTPBadGateway(text='Cross-host credential redirects are not supported.')
                            target = destination
                            continue
                        if response.status not in (200,206):
                            raise web.HTTPBadGateway(text='The provider returned HTTP '+str(response.status)+'. Check subscription, address and connection limits.')
                        if response.headers.get('Content-Encoding','identity').lower() != 'identity':
                            raise web.HTTPBadGateway(text='The provider returned unsupported HTTP compression.')
                        yield response, target
                        return
            raise web.HTTPBadGateway(text='Too many media redirects.')
        except (aiohttp.ClientError, OSError, TimeoutError, ValueError):
            raise web.HTTPBadGateway(text='The provider connection failed. Check the address, network and TLS certificate.') from None

    async def read(self, target, limit=MAX_BYTES):
        async with asyncio.timeout(100):
            async with self.open(target) as (response, final):
                data = bytearray()
                async for chunk in response.content.iter_chunked(65536):
                    data.extend(chunk)
                    if len(data) > limit: raise web.HTTPBadRequest(text='The provider response exceeds the import size limit.')
                return bytes(data), final

    async def json(self, target):
        data, _ = await self.read(target,8*1024**2)
        try: return json.loads(data)
        except (ValueError, RecursionError):
            raise web.HTTPBadGateway(text='The provider did not return valid catalogue data.') from None

    async def array(self,target):
        """Project large Xtream arrays to bounded rows without loading the array."""
        fields={'category_id','stream_id','series_id','name','container_extension','epg_channel_id','tv_archive','tv_archive_duration','stream_icon','cover'}
        class Reader:
            def __init__(self,stream):self.stream=stream;self.total=0
            async def read(self,size=-1):
                value=await self.stream.read(size);self.total+=len(value)
                if self.total>128*1024**2:raise web.HTTPBadRequest(text='The provider catalogue exceeds 128 MB per media type.')
                return value
        try:
            async with asyncio.timeout(180):
                async with self.open(target) as (response,_):
                    depth=0;row=None;key=None;seen=False
                    async for event,value in ijson.basic_parse_async(Reader(response.content),buf_size=4096,use_float=True):
                        if not seen:
                            seen=True
                            if event!='start_array':raise web.HTTPBadGateway(text='The provider did not return a media array.')
                        if event in ('start_map','start_array'):
                            depth+=1
                            if depth>12:raise web.HTTPBadGateway(text='The provider catalogue is nested too deeply.')
                            if depth==2 and event=='start_map':row={}
                        elif event in ('end_map','end_array'):
                            if depth==2 and event=='end_map' and row is not None:
                                yield row;row=None
                            depth-=1
                        elif depth==2 and event=='map_key':key=value
                        elif depth==2 and row is not None and key in fields:
                            row[key]=value[:8192] if isinstance(value,str) else value
                    if not seen:raise web.HTTPBadGateway(text='The provider returned an empty response.')
        except (ijson.JSONError,OverflowError,ValueError):
            raise web.HTTPBadGateway(text='The provider returned invalid streaming catalogue data.') from None


def identity(value):
    return hashlib.sha256(value.encode()).hexdigest()[:32]


def entry(name, target, group='', country='', kind='live', key=None, **fields):
    return {'id':key or identity(target), 'name':text(name) or 'Untitled', 'group':text(group) or 'Ungrouped',
            'country':text(country,80), 'kind':kind, 'secret':{'url':url(target)}, **fields}


def parse_m3u(data, base):
    value = data.decode('utf-8-sig', errors='replace')
    if not value.lstrip().startswith('#EXTM3U') or '#EXT-X-TARGETDURATION' in value or '#EXT-X-STREAM-INF' in value:
        raise web.HTTPBadRequest(text='Select an M3U channel list, not an HLS playback manifest or web page.')
    result, metadata, name, group, headers, guide, seen = [], {}, '', '', {}, [], set()
    skipped = 0
    for line in value.splitlines():
        line = line.strip()
        if not line: continue
        if len(line) > 16384: raise web.HTTPBadRequest(text='An M3U line is too long.')
        if line.startswith('#EXTM3U'):
            a = attrs(line)
            guide = [urljoin(base,v.strip()) for v in (a.get('x-tvg-url') or a.get('url-tvg') or '').split(',') if v.strip()][:120]
        elif line.startswith('#EXTINF:'):
            # A title separator can occur only outside attribute quotes.
            quoted = None; split = len(line)
            for i,c in enumerate(line):
                if c in ('"',"'"): quoted = None if quoted == c else (c if quoted is None else quoted)
                if c == ',' and quoted is None: split=i;break
            metadata = attrs(line[:split]); name=line[split+1:]; headers={};group=metadata.get('group-title','')
        elif line.startswith('#EXTGRP:'): group=line[8:]
        elif line.startswith('#EXTVLCOPT:'):
            k,_,v=line[11:].partition('=')
            if k in ('http-user-agent','http-referrer') and len(v)<=1024:
                headers[{'http-user-agent':'User-Agent','http-referrer':'Referer'}[k]]=v
        elif not line.startswith('#'):
            # Kodi's URL pipe options are not URLs; support just safe UA/Referer.
            address,_,options=line.partition('|')
            for k,v in parse_qs(options).items():
                if k.lower() in ('user-agent','referer') and v and len(v[0])<=1024 and not any(ord(c)<32 for c in v[0]):
                    headers['User-Agent' if k.lower()=='user-agent' else 'Referer']=v[0]
            target=urljoin(base,address)
            try: url(target)
            except web.HTTPException: skipped+=1;continue
            path=urlsplit(target).path.lower(); label=(group+' '+name).lower()
            kind='series' if '/series/' in path or re.search(r'\bs\d{1,2}\s*e\d{1,3}\b',label) else 'movie' if '/movie/' in path or re.search(r'\b(vod|movies?|films?)\b',group.lower()) or path.endswith(('.mp4','.mkv','.avi','.mov','.webm')) else 'live'
            item=entry(name or metadata.get('tvg-name'),target,group,metadata.get('tvg-country',''),kind,tvg_id=text(metadata.get('tvg-id')),archive=0)
            if item['id'] in seen: continue
            seen.add(item['id'])
            item['secret'].update(headers=headers,logo=urljoin(base,metadata.get('tvg-logo','')) if metadata.get('tvg-logo') else '',catchup=metadata.get('catchup',''),catchup_source=metadata.get('catchup-source',''))
            try:item['archive']=min(30,max(0,int(metadata.get('catchup-days','0'))))
            except ValueError:pass
            result.append(item)
            if len(result)>MAX_ITEMS:raise web.HTTPBadRequest(text='Use a provider list with at most 50,000 entries.')
            metadata={};name='';group='';headers={}
    if not result:raise web.HTTPBadRequest(text='No supported HTTP media entries were found.')
    return result,guide,skipped


def xtream_config(value):
    p=urlsplit(url(value));q=parse_qs(p.query)
    if p.path.rstrip('/').endswith('/get.php') and q.get('username') and q.get('password'):
        return {'base':p._replace(path=p.path.rsplit('/',1)[0],query='',fragment='').geturl(),
                'username':q['username'][0],'password':q['password'][0]}
    return None


def xtream_url(config, action=None, **params):
    values={'username':config['username'],'password':config['password'],**params}
    if action:values['action']=action
    return config['base'].rstrip('/')+'/player_api.php?'+urlencode(values)


def stream_url(config, kind, number, extension):
    if not re.fullmatch(r'\d{1,16}',str(number)) or not re.fullmatch('[a-zA-Z0-9]{1,8}',extension):
        raise web.HTTPBadGateway(text='Invalid provider stream identifier.')
    return config['base'].rstrip('/')+'/'+kind+'/'+quote(config['username'],safe='')+'/'+quote(config['password'],safe='')+'/'+str(number)+'.'+extension


async def xtream_catalog(network, config, emit=None):
    auth=await network.json(xtream_url(config))
    if not isinstance(auth,dict) or str(auth.get('user_info',{}).get('auth'))!='1':
        raise web.HTTPBadRequest(text='The provider rejected the IPTV login.')
    zone=auth.get('server_info',{}).get('timezone','UTC');config={**config,'timezone':text(zone,80)}
    result=[];warnings=[];count=0
    for kind,category_action,action,idkey in [('live','get_live_categories','get_live_streams','stream_id'),('movie','get_vod_categories','get_vod_streams','stream_id'),('series','get_series_categories','get_series','series_id')]:
        try:
            categories=await network.json(xtream_url(config,category_action))
            categories={str(c.get('category_id')):text(c.get('category_name')) for c in categories if isinstance(c,dict)} if isinstance(categories,list) else {}
        except web.HTTPException:
            if kind=='live':raise
            warnings.append(kind.title()+' catalogue unavailable from this provider.');continue
        async for row in network.array(xtream_url(config,action)):
            if not isinstance(row,dict) or not re.fullmatch(r'\d{1,16}',str(row.get(idkey,''))):continue
            number=str(row[idkey]);extension=text(row.get('container_extension') or ('ts' if kind=='live' else 'mp4'),8)
            if not re.fullmatch('[a-zA-Z0-9]{1,8}',extension):extension='mp4'
            target=stream_url(config,'live' if kind=='live' else 'movie' if kind=='movie' else 'series',number,extension)
            item=entry(row.get('name'),target,categories.get(str(row.get('category_id')),''),kind=kind,key=identity(kind+':'+number),provider_id=number,series_folder=kind=='series',tvg_id=text(row.get('epg_channel_id')),archive=0)
            if kind=='live' and str(row.get('tv_archive','0'))=='1':
                try:item['archive']=min(30,max(0,int(row.get('tv_archive_duration',0))))
                except (TypeError,ValueError):pass
            item['secret']['logo']=text(row.get('stream_icon') or row.get('cover'),8192)
            result.append(item)
            count+=1
            if count>500000:raise web.HTTPBadRequest(text='Use an IPTV source with at most 500,000 entries.')
            if emit and len(result)>=500:
                await emit(result);result.clear()
    if not count:raise web.HTTPBadRequest(text='The IPTV account has no available media.')
    if emit:
        if result:await emit(result)
        result=[]
    return result, config, warnings


def xmltv(data):
    if data.startswith(b'\x1f\x8b'):
        try:
            inflater=zlib.decompressobj(16+zlib.MAX_WBITS)
            data=inflater.decompress(data,24*1024**2+1)
            if len(data)>24*1024**2 or not inflater.eof:raise ValueError()
        except (zlib.error,ValueError):raise web.HTTPBadRequest(text='The compressed guide is invalid or exceeds 24 MB.') from None
    if len(data)>24*1024**2:raise web.HTTPBadRequest(text='The guide exceeds 24 MB. Select a country-specific guide.')
    try:
        value=data.decode('utf-8-sig')
        if '<!DOCTYPE' in value.upper() or '<!ENTITY' in value.upper():raise ValueError()
        root=ET.fromstring(value)
        if root.tag!='tv':raise ValueError()
        result=[]
        def stamp(v):return datetime.strptime(v,'%Y%m%d%H%M%S %z').timestamp()
        for p in root.iter('programme'):
            try:
                start=stamp(p.get('start',''));stop=stamp(p.get('stop',''))
                if not 0<stop-start<=86400:continue
                result.append({'channel':text(p.get('channel')), 'start':start,'stop':stop,'title':text(p.findtext('title')),'description':text(p.findtext('desc'),2000)})
            except (ValueError,OverflowError):continue
            if len(result)>50000:raise web.HTTPBadRequest(text='The guide has over 50,000 programmes. Select a smaller guide.')
        return result
    except (UnicodeError,ET.ParseError,ValueError):
        raise web.HTTPBadRequest(text='Use a UTF-8 XMLTV guide without DTDs or entities.') from None
