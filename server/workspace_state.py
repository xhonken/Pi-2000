"""Account-private, bounded desktop checkpoints. Never contains live processes."""
import json
import re

MAX_BYTES = 4 * 1024**2
TYPES = frozenset((name+'-window') for name in 'explorer users terminal browser status files trash editor preview search activities notes preferences sftp cad calculator taskmanager phpmyadmin database api git arduino network display archive log vault iptv'.split())
STATE_TYPES = {'iptv-window', 'arduino-window', 'display-window', 'cad-window', 'calculator-window', 'editor-window'}

def validate(data):
    if not isinstance(data, dict) or set(data) != {'windows'} or not isinstance(data['windows'], list) or len(data['windows']) > 12:
        raise ValueError('Invalid window layout.')
    for window in data['windows']:
        if (not isinstance(window, dict) or window.get('type') not in TYPES
                or window.keys() - {'type','terminal','profile','folder','left','top','width','height','hidden','maximized','editorFiles','state'}
                or any(type(window.get(k)) not in (int,float) or not -10000 <= window[k] <= 10000 for k in ('left','top','width','height'))
                or any(type(window.get(k)) is not bool for k in ('hidden','maximized'))
                or any(window.get(k) is not None and (not isinstance(window[k],str) or len(window[k])>128) for k in ('terminal','folder','profile'))):
            raise ValueError('Invalid window layout.')
        if 'profile' in window and window['type'] != 'terminal-window':
            raise ValueError('Only terminals have connection references.')
        if 'editorFiles' in window and (not isinstance(window['editorFiles'],list) or len(window['editorFiles'])>100 or any(not isinstance(k,str) or not re.fullmatch(r'[a-f0-9]{32}',k) for k in window['editorFiles'])):
            raise ValueError('Invalid editor tabs.')
        if 'state' in window and (window['type'] not in STATE_TYPES or not isinstance(window['state'],dict)):
            raise ValueError('This application does not support checkpoint content.')
    # Reject non-JSON numbers and oversized snapshots before writing any data.
    encoded=json.dumps(data,allow_nan=False,separators=(',',':'),ensure_ascii=False).encode()
    if len(encoded)>MAX_BYTES: raise ValueError('Workspace recovery data exceeds 4 MB. Save large projects as files.')
    return encoded.decode()
