"""Opt-in real CLI + Unix-worker + cgroup test; uses no production accounts/devices."""
import asyncio
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import time
from aiohttp.test_utils import TestClient, TestServer
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'server'))
import app
import arduino_workshop as ar
from session_store import SessionStore

async def main():
    runtime=Path(os.environ['PI2000_TEST_ARDUINO_RUNTIME']).resolve()
    cli=Path(os.environ['WIN2K_ARDUINO_CLI']).resolve()
    with tempfile.TemporaryDirectory(prefix='arduino-service-test-',dir=Path.home()/'.cache') as temp:
        state=Path(temp);sock=state/'worker.sock';unit='pi2000-arduino-validation-'+secrets.token_hex(4)
        app.STATE=state;app.SESSIONS={};app.WORKER_SOCKET='';app.WORKER_MODE=False;app.ORIGIN='http://127.0.0.1:18766';ar.SOCKET=str(sock)
        application=app.make_app();app.SESSIONS=SessionStore(state/'admin.sqlite3')
        (state/'arduino-runtime').mkdir();(state/'arduino-runtime'/'1').symlink_to(runtime,target_is_directory=True)
        token=secrets.token_urlsafe(32);app.SESSIONS[token]={'user_id':1,'version':1,'expires':time.time()+1800}
        command=['systemd-run','--user','--quiet','--unit='+unit,'--property=MemoryHigh=1536M','--property=MemoryMax=2048M','--property=MemorySwapMax=128M','--property=CPUQuota=150%','--property=TasksMax=128','--property=NoNewPrivileges=true',
                 '--setenv=WIN2K_STATE='+str(state),'--setenv=WIN2K_ORIGIN='+app.ORIGIN,'--setenv=WIN2K_ARDUINO_CLI='+str(cli),'--setenv=WIN2K_ARDUINO_LISTEN='+str(sock),str(ROOT/'.venv/bin/python'),str(ROOT/'server/arduino_service.py')]
        subprocess.run(command,check=True)
        client=TestClient(TestServer(application));await client.start_server()
        async def call(action,status=200,**data):
            r=await client.post('/api/development/arduino',json={'action':action,**data},headers={'Origin':app.ORIGIN,'Cookie':app.COOKIE+'='+token})
            v=await r.json();assert r.status==status,(r.status,v);return v
        try:
            for _ in range(100):
                if sock.exists():break
                await asyncio.sleep(.1)
            assert sock.exists(),'worker failed to start'
            p=await call('create',name='ServiceProbe',fqbn='esp32:esp32:esp32',files={'ServiceProbe.ino':'#include <ArduinoJson.h>\nvoid setup(){ Serial.begin(115200); JsonDocument d; d["ok"]=true; serializeJson(d,Serial); }\nvoid loop(){}\n'})
            await call('compile',project=p['id'],revision=1)
            cgroup=subprocess.check_output(['systemctl','--user','show',unit,'--property=ControlGroup','--value'],text=True).strip()
            cg=Path('/sys/fs/cgroup'+cgroup)
            assert (cg/'memory.max').read_text().strip()=='2147483648'
            peak=0
            for _ in range(600):
                peak=max(peak,int((cg/'memory.current').read_text()))
                status=await call('status')
                if status['job']['state']!='running':break
                await asyncio.sleep(1)
            assert status['job']['state']=='succeeded',status['job']
            assert 'Sketch uses' in status['job']['output']
            print('PASS: real ESP32 + ArduinoJson compile through API proxy and separate Unix worker; cgroup memory.max=2147483648, sampled peak='+str(peak),flush=True)
            subprocess.run(['systemctl','--user','restart',unit],check=True)
            for _ in range(100):
                if not sock.exists():
                    await asyncio.sleep(.1);continue
                try:
                    status=await call('status');break
                except Exception:await asyncio.sleep(.1)
            assert status['job']['state']=='succeeded','completed job log not preserved'
            assert len(status['projects'])==1
            print('PASS: project and completed job log survive worker restart.',flush=True)
        finally:
            await client.close();subprocess.run(['systemctl','--user','stop',unit],check=True);subprocess.run(['systemctl','--user','reset-failed',unit],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
asyncio.run(main())
