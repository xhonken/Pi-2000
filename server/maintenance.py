#!/usr/bin/env python3
"""OS-root maintenance. Never exposed as a web-admin restart capability."""
from aiohttp import ClientError
import argparse
import asyncio
import json
import os
import secrets
import time
from session_proxy import control
from runtime_health import compare
import build_info

WORKERS = {'sessions': ('pi2000-sessions', '/run/pi2000-sessions/worker.sock'),
           'arduino': ('pi2000-arduino', '/run/pi2000-arduino/worker.sock')}

async def restart_idle(socket, restart, wait=0):
    lease = secrets.token_hex(16)
    deadline = time.monotonic() + wait
    drained = False
    try:
        while True:
            response = await control(socket, 'drain', lease=lease)
            runtime = response.get('runtime')
            if not runtime or runtime.get('protocol') != 1 or not runtime.get('draining'):
                raise RuntimeError('Worker does not support safe draining; use a planned maintenance window.')
            drained = True
            if not runtime['busy']:
                await restart()
                return
            if time.monotonic() >= deadline:
                raise RuntimeError('Worker is busy; no restart performed. Finish its jobs and try again.')
            await asyncio.sleep(min(2, max(0, deadline-time.monotonic())))
    finally:
        if drained:
            try: await control(socket, 'resume', lease=lease)
            except Exception: pass  # Successful restart has a new instance/lease.

async def main_async(args):
    installed = build_info.installed()
    for name in ([args.worker] if args.worker else WORKERS):
        unit, socket = WORKERS[name]
        if args.action == 'status':
            try: result = compare((await control(socket, 'status')).get('runtime'), installed)
            except Exception: result = {'state': 'unavailable'}
            print(json.dumps({'worker': name, **result}))
        else:
            async def restart():
                process = await asyncio.create_subprocess_exec('systemctl', 'restart', unit)
                if await asyncio.wait_for(process.wait(), 45): raise RuntimeError('Service restart failed.')
            await restart_idle(socket, restart, args.wait)
            deadline = time.monotonic()+20
            while True:
                try:
                    report = compare((await control(socket,'status')).get('runtime'),installed)
                    if report['state'] != 'current': raise RuntimeError('Worker did not load the installed build.')
                    print(name+': restarted while idle; installed build active')
                    break
                except (OSError, ClientError, TimeoutError):
                    if time.monotonic() >= deadline: raise
                    await asyncio.sleep(.5)

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['status','restart-idle'])
    parser.add_argument('worker',choices=list(WORKERS),nargs='?')
    parser.add_argument('--wait',type=int,default=0,help='Wait at most this many seconds, rejecting new jobs meanwhile.')
    args=parser.parse_args()
    if os.geteuid()!=0:parser.error('Run as OS root; web roles cannot restart services.')
    if not 0 <= args.wait <= 3600:parser.error('Wait must be between 0 and 3600 seconds.')
    if args.action=='restart-idle' and not args.worker:parser.error('Select one worker to restart.')
    asyncio.run(main_async(args))
