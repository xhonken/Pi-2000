"""Bounded, backwards-compatible per-account desktop document validation."""
import hashlib
import json
from urllib.parse import urlsplit

APPS = frozenset('computer files devices browser trash editor arduino cad calculator search links network displaystudio archive vault logviewer add localterminal notes database apitester git sftp taskmanager activities status about preferences settings help'.split())

def etag(data):
    raw=json.dumps(data,sort_keys=True,separators=(',',':')).encode()
    return '"'+hashlib.sha256(raw).hexdigest()+'"'

def validate(data):
    if not isinstance(data,dict) or not {'shortcuts','color'} <= data.keys() or data.keys()-{'shortcuts','color','positions','icons','view'}:
        raise ValueError('Invalid desktop settings.')
    if data['color'] not in ('#3a6ea5','#008080','#2d4739') or not isinstance(data['shortcuts'],list) or len(data['shortcuts'])>1000:
        raise ValueError('Invalid desktop settings.')
    positions=data.get('positions',{})
    if not isinstance(positions,dict) or len(positions)>5200:
        raise ValueError('Invalid icon positions.')
    for key,point in positions.items():
        if (not isinstance(key,str) or not 1<=len(key)<=160 or not isinstance(point,list) or len(point)!=2 or any(type(v) is not int or not 0<=v<=10000 for v in point)):
            raise ValueError('Invalid icon position.')
    ids=set()
    for item in data['shortcuts']:
        if (not isinstance(item,dict) or set(item)!={'id','name','url','desktop','start','deleted'} or any(not isinstance(item[k],str) for k in ('id','name','url')) or not 1<=len(item['id'])<=120 or item['id'] in ids or not 1<=len(item['name'].strip())<=80 or len(item['url'])>4096 or any(type(item[k]) is not bool for k in ('desktop','start','deleted'))):
            raise ValueError('Invalid shortcut.')
        try:
            url=urlsplit(item['url'])
            if url.scheme not in ('http','https') or not url.hostname:raise ValueError()
            _=url.port
        except ValueError:raise ValueError('Invalid shortcut address.') from None
        ids.add(item['id'])
    icons=data.get('icons',{})
    if not isinstance(icons,dict) or len(icons)>len(APPS):raise ValueError('Invalid application icons.')
    for action,settings in icons.items():
        if action not in APPS or not isinstance(settings,dict) or set(settings)!={'name','visible'} or not isinstance(settings['name'],str) or not 1<=len(settings['name'].strip())<=80 or type(settings['visible']) is not bool:
            raise ValueError('Invalid application icon.')
    view=data.get('view',{})
    if not isinstance(view,dict) or view.keys()-{'sort','direction','autoArrange','snap','showIcons','openMode'}:raise ValueError('Invalid desktop view.')
    for k,choices in [('sort',('manual','name','type','size','modified')),('direction',('asc','desc')),('openMode',('single','double'))]:
        if k in view and view[k] not in choices:raise ValueError('Invalid desktop view.')
    for k in ('autoArrange','snap','showIcons'):
        if k in view and type(view[k]) is not bool:raise ValueError('Invalid desktop view.')
    return data
