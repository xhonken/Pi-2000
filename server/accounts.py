"""Unprivileged client for the fixed-operation local account service."""
import asyncio
import json
import os
from aiohttp import web

SOCKET = os.environ.get('WIN2K_ACCOUNTS_SOCKET', '')

def enabled(): return bool(SOCKET)

async def call(operation, **data):
    if not SOCKET: raise web.HTTPServiceUnavailable(text='System accounts are not configured.')
    reader, writer = await asyncio.wait_for(asyncio.open_unix_connection(SOCKET, limit=32768), 5)
    try:
        writer.write(json.dumps({'operation': operation, **data}).encode() + b'\n')
        await writer.drain()
        reply = json.loads(await asyncio.wait_for(reader.readline(), 45))
    finally:
        writer.close(); await writer.wait_closed()
    if not reply.get('ok'):
        status = reply.get('status', 409)
        raise {401:web.HTTPUnauthorized, 403:web.HTTPForbidden, 404:web.HTTPNotFound, 409:web.HTTPConflict}.get(status, web.HTTPServiceUnavailable)(text=reply.get('error', 'Account service unavailable.'))
    return reply
