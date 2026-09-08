import asyncio
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import unittest

import asyncssh
from aiohttp import ClientSession, ClientTimeout, WSMsgType
from test_server import SSHServer

async def echo(process):
    process.stdout.write("READY\r\n")
    while data := await process.stdin.readline():
        if data.strip() == "background-job":
            process.stdout.write("BACKGROUND-JOB-STARTED\r\n")
            await asyncio.sleep(.5)
            process.stdout.write("BACKGROUND-JOB-COMPLETED\r\n")
        else: process.stdout.write("ECHO:" + data)

SERVER = Path(__file__).resolve().parents[1]/'server'

class WorkerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.state=Path(self.temp.name)
        self.socket=str(self.state/'worker.sock')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));self.port=sock.getsockname()[1]
        self.origin=f'http://127.0.0.1:{self.port}'
        self.env={**os.environ,'WIN2K_STATE':str(self.state),'WIN2K_ORIGIN':self.origin,'WIN2K_CGROUP_LIMITS':'0'}
        self.log=(self.state/'process.log').open('wb')
        self.worker=await asyncio.create_subprocess_exec(sys.executable,str(SERVER/'app.py'),env={**self.env,'WIN2K_SESSION_WORKER':'1','WIN2K_LISTEN_SOCKET':self.socket},stdout=self.log,stderr=self.log)
        for _ in range(100):
            if Path(self.socket).exists():break
            await asyncio.sleep(.05)
        else:raise RuntimeError('Worker failed to start')
        self.front=None
        await self.start_front()
        self.http=ClientSession(timeout=ClientTimeout(total=10))
        response=await self.http.post(self.origin+'/api/login',headers={'Origin':self.origin},json={'username':'admin','password':(self.state/'initial-password.txt').read_text().strip()})
        self.assertEqual(response.status,200)
        self.token=response.cookies['__Host-win2k'].value
        self.headers={'Origin':self.origin,'Cookie':'__Host-win2k='+self.token}
        key=asyncssh.generate_private_key('ssh-ed25519')
        self.ssh=await asyncssh.create_server(SSHServer,'127.0.0.1',0,server_host_keys=[key],process_factory=echo,line_editor=False)

    async def start_front(self):
        self.front=await asyncio.create_subprocess_exec(sys.executable,str(SERVER/'app.py'),env={**self.env,'WIN2K_WORKER_SOCKET':self.socket,'WIN2K_PORT':str(self.port),'WIN2K_SESSION_WORKER':'0'},stdout=self.log,stderr=self.log)
        for _ in range(100):
            try:
                reader,writer=await asyncio.open_connection('127.0.0.1',self.port);writer.close();await writer.wait_closed();return
            except OSError: await asyncio.sleep(.05)
        raise RuntimeError('Front failed to start')

    async def asyncTearDown(self):
        await self.http.close()
        for process in (self.front,self.worker):
            if process and process.returncode is None:
                process.terminate()
                try:await asyncio.wait_for(process.wait(),8)
                except asyncio.TimeoutError:process.kill();await process.wait()
        self.ssh.close();await self.ssh.wait_closed()
        self.log.close();self.temp.cleanup()

    async def test_front_restart_preserves_login_and_background_terminal(self):
        response=await self.http.post(self.origin+'/api/items',headers=self.headers,json={'kind':'profile','name':'Worker SSH','host':'127.0.0.1','port':self.ssh.get_port(),'username':'pi','parent':None})
        self.assertEqual(response.status,200)
        profile=(await response.json())['id']
        ws=await self.http.ws_connect(self.origin+'/api/terminal',headers=self.headers)
        await ws.send_json({'profile':profile,'password':'ssh-test-password'})
        msg=await ws.receive_json();self.assertEqual(msg['type'],'hostkey')
        await ws.send_json({'type':'trust','accept':True})
        msg=await ws.receive_json();self.assertEqual(msg['type'],'connected');terminal=msg['id']
        await ws.send_bytes(b'background-job\n')
        while True:
            msg=await asyncio.wait_for(ws.receive(),5)
            if msg.type==WSMsgType.BINARY and b'BACKGROUND-JOB-STARTED' in msg.data:break
        # Simulate an API crash, not a graceful log-out or session-worker restart.
        self.front.kill();await self.front.wait();await ws.close()
        await asyncio.sleep(.3)
        await self.start_front()
        response=await self.http.get(self.origin+'/api/session',headers=self.headers)
        self.assertEqual(response.status,200)
        response=await self.http.get(self.origin+'/api/terminals',headers=self.headers)
        self.assertEqual((await response.json())['terminals'][0]['id'],terminal)
        ws=await self.http.ws_connect(self.origin+'/api/terminal',headers=self.headers)
        await ws.send_json({'terminal':terminal})
        self.assertEqual((await ws.receive_json())['id'],terminal)
        output=b''
        for _ in range(10):
            msg=await asyncio.wait_for(ws.receive(),5)
            if msg.type==WSMsgType.BINARY:output+=msg.data
            if b'BACKGROUND-JOB-COMPLETED' in output:break
        self.assertIn(b'BACKGROUND-JOB-COMPLETED',output)
        await ws.send_bytes(b'still-running\n')
        msg=await asyncio.wait_for(ws.receive(),5)
        self.assertIn(b'ECHO:still-running',msg.data)
        await self.http.post(self.origin+'/api/logout',headers=self.headers,json={})
        while not ws.closed:
            msg=await asyncio.wait_for(ws.receive(),5)
            if msg.type in (WSMsgType.CLOSE,WSMsgType.CLOSED):break
        await ws.close()

    async def test_digest_cookie_and_internal_routes_rejected(self):
        import hashlib
        digest='sha256:'+hashlib.sha256(self.token.encode()).hexdigest()
        response=await self.http.get(self.origin+'/api/session',headers={'Cookie':'__Host-win2k='+digest})
        self.assertEqual(response.status,401)
        response=await self.http.post(self.origin+'/internal/control',headers=self.headers,json={'action':'status'})
        self.assertEqual(response.status,404)
        response=await self.http.get(self.origin+'/api/session',headers=self.headers)
        self.assertEqual(response.status,200)
