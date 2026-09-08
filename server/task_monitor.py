"""Read-only Linux monitoring. Never reads process arguments, environments or paths."""
import asyncio
import os
import re
import time
from pathlib import Path
from aiohttp import web

class TaskMonitor:
    def __init__(self, app, proc=Path('/proc')):
        self.app=app;self.proc=proc;self.previous=None;self.cached=None;self.lock=asyncio.Lock()
        self.ticks=os.sysconf('SC_CLK_TCK');self.page_size=os.sysconf('SC_PAGE_SIZE')

    @staticmethod
    def cpu_percent(old, new):
        if old is None:return None
        total=sum(new[:8])-sum(old[:8]);idle=(new[3]+new[4])-(old[3]+old[4])
        return round(max(0,min(100,100*(total-idle)/total)),1) if total>0 else None

    def sample(self):
        now=time.monotonic();cpus={};running=0
        for line in (self.proc/'stat').read_text().splitlines():
            fields=line.split()
            if fields[0]=='cpu' or re.fullmatch(r'cpu\d+',fields[0]):cpus[fields[0]]=[int(x) for x in fields[1:]]
            elif fields[0]=='procs_running':running=int(fields[1])
        memory={}
        for line in (self.proc/'meminfo').read_text().splitlines():
            key,value=line.split(':',1);memory[key]=int(value.split()[0])*1024
        total=memory['MemTotal'];available=memory.get('MemAvailable',memory.get('MemFree',0))
        cores=max(1,len(cpus)-1);processes=[];previous=self.previous;elapsed=now-previous['time'] if previous else None
        previous_processes=previous['processes'] if previous else {}
        for directory in self.proc.iterdir():
            if not directory.name.isdecimal():continue
            try:
                raw=(directory/'stat').read_text();end=raw.rfind(')');fields=raw[end+2:].split()
                pid=int(directory.name);name=raw[raw.index('(')+1:end];start=int(fields[19]);ticks=int(fields[11])+int(fields[12])
                rss=max(0,int(fields[21]))*self.page_size;threads=int(fields[17]);cpu=None
                old=previous_processes.get((pid,start))
                if old is not None and elapsed and elapsed>0:cpu=round(max(0,min(100,100*(ticks-old)/self.ticks/elapsed/cores)),2)
                group=(directory/'cgroup').read_text()
                match=re.search(r'(?:^|/)win2k-sessions\.service/browser-(\d+)(?:/|\s|$)',group)
                uid=int(match[1]) if match else None
                # Detect exit/reuse between metadata and cgroup reads.
                check=(directory/'stat').read_text();check_fields=check[check.rfind(')')+2:].split()
                if int(check_fields[19])!=start:continue
                processes.append({'pid':pid,'name':name,'state':fields[0],'memory_bytes':rss,'threads':threads,'cpu_percent':cpu,'cpu_seconds':round(ticks/self.ticks,2),'user_id':uid,'_ticks':ticks,'_start':start})
            except (OSError,ValueError,IndexError):continue
        self.previous={'time':now,'cpus':cpus,'processes':{(p['pid'],p['_start']):p['_ticks'] for p in processes}}
        cpu={key:self.cpu_percent(previous['cpus'].get(key) if previous else None,value) for key,value in cpus.items()}
        disk=os.statvfs(self.app.STATE);unit=disk.f_frsize
        return {'sampled_at':time.time(),'_time':now,'cpu':{'percent':cpu['cpu'],'cores':[cpu[k] for k in sorted((key for key in cpu if key!='cpu'),key=lambda key:int(key[3:]))],'count':cores},
                'memory':{'total':total,'available':available,'used':max(0,total-available),'cache':memory.get('Cached',0)+memory.get('SReclaimable',0),'swap_total':memory.get('SwapTotal',0),'swap_used':max(0,memory.get('SwapTotal',0)-memory.get('SwapFree',0))},
                'disk':{'total':disk.f_blocks*unit,'used':(disk.f_blocks-disk.f_bfree)*unit,'free':disk.f_bavail*unit,'reserved':max(0,disk.f_bfree-disk.f_bavail)*unit},
                'uptime':float((self.proc/'uptime').read_text().split()[0]),'running':running,'process_count':len(processes),'threads':sum(p['threads'] for p in processes),'processes':processes}

    async def handle(self,request):
        a=self.app;uid=request[a.USER]['id'];owner=a.is_owner(request[a.USER]);scope=request.query.get('scope','mine')
        if scope not in ('mine','server'):raise web.HTTPBadRequest()
        if scope=='server' and not owner:raise web.HTTPForbidden(text='Only the owner can view all server processes.')
        async with self.lock:
            if self.cached is None or time.monotonic()-self.cached['_time']>=1:
                self.cached=await asyncio.to_thread(self.sample)
            snapshot=self.cached
        a.require_current(request)
        with a.db() as db:
            storage=a.FILES.usage(db,uid)
            row=db.execute("SELECT COALESCE(SUM(CASE WHEN state='trash' THEN size ELSE 0 END),0) AS trash, COALESCE(SUM(CASE WHEN state='live' AND kind='file' THEN 1 ELSE 0 END),0) AS files FROM files WHERE user_id=?",(uid,)).fetchone()
            storage.update(dict(row))
        filtered=[{key:value for key,value in p.items() if not key.startswith('_') and key!='user_id'} for p in snapshot['processes'] if scope=='server' or p['user_id']==uid]
        return web.json_response({**{k:v for k,v in snapshot.items() if k not in ('processes','_time')},'processes':filtered,'scope':scope,'can_view_server':owner,'storage':storage,'process_memory_kind':'RSS','interval_seconds':2},headers={'Cache-Control':'no-store'})
