"""OS-managed mapping for administrators' local SSH terminal; never a web setting."""
import json
import accounts
from pathlib import Path
import re
from aiohttp import web

CONFIG = Path('/etc/pi2000web/local-terminal.json')

def profile(user):
    if user['role'] != 'admin':
        raise web.HTTPForbidden(text='Only administrators can open Local Terminal.')
    if accounts.enabled():
        if user.get('auth_backend')!='pam' or not user.get('linux_username'):
            raise web.HTTPConflict(text='Log out and sign in again to finish your system account migration.')
        return {'id':'local-terminal','name':'Local Terminal','kind':'profile','host':'127.0.0.1',
                'port':2222 if user.get('linux_managed',1) else 22,'username':user['linux_username'],'local':True}
    try:
        data = json.loads(CONFIG.read_text())
    except FileNotFoundError:
        raise web.HTTPConflict(text='Local Terminal is not configured. Run sudo pi2000web setup on the Pi.')
    username = data.get('username', '')
    port = data.get('port', 22)
    if not re.fullmatch(r'[a-z_][a-z0-9_-]{0,31}', username) or username in ('root', 'win2k-admin', 'pi2000-phpmyadmin') or type(port) is not int or not 1 <= port <= 65535:
        raise web.HTTPConflict(text='The OS administrator must correct the Local Terminal configuration.')
    return {'id': 'local-terminal', 'name': 'Local Terminal', 'kind': 'profile',
            'host': '127.0.0.1', 'port': port, 'username': username, 'local': True}

async def status(request, user):
    return web.json_response(profile(user))

def host_keys():
    keys=json.loads(CONFIG.read_text()).get('host_keys',[])
    if not isinstance(keys,list) or not keys or any(not isinstance(key,str) or len(key.split())<2 for key in keys):
        raise web.HTTPConflict(text='Run sudo pi2000web setup to register the local SSH host keys.')
    return [' '.join(key.split()[:2]) for key in keys]
