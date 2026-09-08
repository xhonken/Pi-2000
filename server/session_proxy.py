"""Private Unix-socket transport between the API and long-lived session worker."""
import asyncio
from aiohttp import web, ClientSession, UnixConnector, ClientError, ClientTimeout, WSMsgType
from yarl import URL

async def control(socket, action, **data):
    async with ClientSession(connector=UnixConnector(path=socket), timeout=ClientTimeout(total=30)) as client:
        async with client.post('http://worker/internal/control', json={'action': action, **data}) as response:
            response.raise_for_status()
            return await response.json()

async def proxy(request, socket):
    websocket = request.headers.get('Upgrade', '').lower() == 'websocket'
    headers = {key: value for key, value in request.headers.items()
               if key.lower() in ('cookie', 'origin', 'content-type', 'accept', 'range')}
    try:
        async with ClientSession(connector=UnixConnector(path=socket), auto_decompress=False,
                                 timeout=ClientTimeout(total=None, connect=10)) as client:
            url = URL('http://worker' + request.raw_path, encoded=True)
            if websocket:
                async with client.ws_connect(url, headers=headers, max_msg_size=32*1024*1024, heartbeat=25) as upstream:
                    downstream = web.WebSocketResponse(max_msg_size=32*1024*1024, heartbeat=25)
                    await downstream.prepare(request)
                    async def forward(source, target):
                        async for message in source:
                            if message.type == WSMsgType.TEXT:
                                await target.send_str(message.data)
                            elif message.type == WSMsgType.BINARY:
                                await target.send_bytes(message.data)
                            else:
                                break
                    tasks = [asyncio.create_task(forward(upstream, downstream)), asyncio.create_task(forward(downstream, upstream))]
                    try:
                        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                    finally:
                        for task in tasks: task.cancel()
                        await asyncio.gather(*tasks, return_exceptions=True)
                        await downstream.close()
                    return downstream
            async with client.request(request.method, url, headers=headers, data=await request.read()) as upstream:
                response = web.StreamResponse(status=upstream.status, headers={k:v for k,v in upstream.headers.items()
                    if k.lower() in ('content-type','content-encoding','content-length','content-range','accept-ranges','x-frame-options')})
                response.headers['Cache-Control'] = 'no-store'
                await response.prepare(request)
                async for chunk in upstream.content.iter_chunked(65536): await response.write(chunk)
                await response.write_eof()
                return response
    except (ClientError, OSError, asyncio.TimeoutError):
        if websocket and 'downstream' in locals() and downstream.prepared:
            await downstream.close()
            return downstream
        return web.json_response({'error':'The session service is temporarily unavailable. Try reconnecting shortly.'}, status=503)
