"""Request admission limits independent of user-supplied content and login count."""
from contextlib import contextmanager
import asyncio
import logging
from aiohttp import web

BUDGET = web.AppKey('request_budget', object)
AUDIT = logging.getLogger('pi2000.security')
AUDIT.setLevel(logging.INFO)

async def body_chunks(request):
    """Bound idle body reads, including upload routes using streaming APIs."""
    iterator = request.content.iter_chunked(65536).__aiter__()
    while True:
        try:
            async with asyncio.timeout(30):
                chunk = await anext(iterator)
        except StopAsyncIteration:
            return
        except TimeoutError:
            raise web.HTTPRequestTimeout(text='The request body stopped arriving.') from None
        yield chunk

class RequestBudget:
    def __init__(self):
        self.total = 0
        self.accounts = {}

    @contextmanager
    def slot(self, uid):
        limit = 8 if uid is None else 16
        if self.total >= 64 or self.accounts.get(uid, 0) >= limit:
            raise web.HTTPTooManyRequests(text='Too many active requests. Finish an operation and try again.', headers={'Retry-After':'5'})
        self.total += 1
        self.accounts[uid] = self.accounts.get(uid, 0) + 1
        try:
            yield
        finally:
            self.total -= 1
            self.accounts[uid] -= 1
            if not self.accounts[uid]:
                del self.accounts[uid]

async def response_headers(request, response):
    # on_response_prepare also covers early authentication errors and streams.
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'same-origin'
    if response.content_type == 'application/json':
        response.headers['Content-Security-Policy'] = "default-src 'none'; frame-ancestors 'none'"

def audit_response(request, response, uid=None):
    # Fixed event names and numeric IDs only. Never log bodies, passwords,
    # tokens, query strings, private document names or database commands.
    path = request.path
    if path == '/api/login': event = 'login'
    elif path == '/api/logout': event = 'logout'
    elif path == '/api/password': event = 'password_change'
    elif path.startswith('/api/users') and request.method not in ('GET','HEAD'):
        event = {'POST':'account_create_or_reset','PATCH':'account_update','DELETE':'account_delete'}.get(request.method,'account_mutation')
    else: return
    target = path.split('/')[3:4] if path.startswith('/api/users/') else []
    target = target[0] if target and target[0].isascii() and target[0].isdigit() and len(target[0]) <= 18 else '-'
    AUDIT.info('event=%s actor=%s target=%s status=%s',event,uid if type(uid) is int else '-',target,response.status)
