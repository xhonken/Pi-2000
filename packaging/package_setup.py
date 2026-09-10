#!/usr/bin/env python3
"""Idempotent .deb configuration. Never invokes apt/pip or changes distro conffiles."""
import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import pwd
import shutil
import sqlite3
import ssl
import subprocess
import sys
import time
import tomllib
import urllib.request

CONFIG=Path('/etc/pi2000web')
STATE=Path('/var/lib/win2k-admin')
MARKER=Path('/var/lib/pi2000web')
UNITS=('win2k-sessions','pi2000-phpmyadmin','win2k-admin','pi2000-web','win2k-backup.timer')

def run(*args,capture=False):
    r=subprocess.run(list(map(str,args)),check=True,text=True,stdout=subprocess.PIPE if capture else None)
    return r.stdout.strip() if capture else None

def active(name):return subprocess.run(['systemctl','is-active','--quiet',name]).returncode==0

def account(name,home):
    try:return pwd.getpwnam(name)
    except KeyError:
        run('useradd','--system','--no-create-home','--home-dir',home,'--shell','/usr/sbin/nologin',name)
        return pwd.getpwnam(name)

def directory(path,mode=0o700,owner=None):
    path=Path(path);path.mkdir(parents=True,exist_ok=True);path.chmod(mode)
    if owner:os.chown(path,owner.pw_uid,owner.pw_gid)

def atomic(path,text,mode=0o600):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.new');temp.write_text(text);temp.chmod(mode);temp.replace(path)

def address():
    route=json.loads(run('ip','-j','route','get','1.1.1.1',capture=True))[0]
    value=route.get('prefsrc') or route.get('src')
    ip=ipaddress.ip_address(value)
    if ip.is_loopback or ip.is_unspecified:raise RuntimeError('Configure a LAN address with pi2000web configure --url https://HOST.')
    return 'https://'+('['+str(ip)+']' if ip.version==6 else str(ip))

def configure(args):
    if not Path('/run/systemd/system').exists():raise RuntimeError('Configuration requires a running systemd Raspberry Pi OS host.')
    directory(CONFIG,0o755);directory(MARKER)
    path=CONFIG/'config.toml'
    from source_setup import read_config, config_text
    old=read_config(path) if path.exists() else None
    data=old or {'network':{'public_url':args.url or address(),'tls':'internal','bind_address':''},'features':{'browser':True}}
    previous_url=data['network']['public_url']
    if args.url:data['network']['public_url']=args.url
    import tempfile
    with tempfile.TemporaryDirectory() as temp:
        candidate=Path(temp)/'config.toml';candidate.write_text(config_text(data));data=read_config(candidate)
    url=data['network']['public_url'];tls=data['network']['tls']
    if old and previous_url!=url and active('win2k-sessions') and not args.restart_sessions:
        raise RuntimeError('Changing the URL requires --restart-sessions after finishing live jobs.')
    atomic(path,config_text(data))
    owner=account('win2k-admin',STATE);account('pi2000-phpmyadmin','/var/lib/pi2000-phpmyadmin')
    directory(STATE,owner=owner);directory('/var/backups/win2k');directory('/var/lib/caddy/win2k-admin',owner=pwd.getpwnam('caddy'))
    runtime='WIN2K_ORIGIN='+url+'\n'
    total=int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemTotal:')))//1024
    if total<3072:
        runtime+='WIN2K_BROWSER_MEMORY_MIB=1024\nWIN2K_BROWSER_RESERVE_MIB=256\n'
        atomic('/etc/systemd/system/win2k-sessions.service.d/pi2000-memory.conf','[Service]\nMemoryHigh=1152M\nMemoryMax=1280M\nTasksMax=500\nCPUQuota=200%\n',0o644)
    atomic(CONFIG/'runtime.env',runtime)
    caddy=(Path(__file__).with_name('Caddyfile.template')).read_text().replace('@PUBLIC_URL@',url).replace('@TLS@','tls internal' if tls=='internal' else '# Automatic public HTTPS').replace('@BIND@','    bind '+data['network']['bind_address']+'\n' if data['network']['bind_address'] else '')
    atomic(CONFIG/'Caddyfile',caddy,0o644)
    # Caddy's package starts its sample site on installation. Preserve its file;
    # only retire that exact, unchanged sample, never an existing custom server.
    if active('caddy') and not active('pi2000-web'):
        conffiles=run('dpkg-query','-W','-f=${Conffiles}','caddy',capture=True)
        expected=next((line.split()[1] for line in conffiles.splitlines() if line.split() and line.split()[0]=='/etc/caddy/Caddyfile'),None)
        current=Path('/etc/caddy/Caddyfile')
        if not expected or hashlib.md5(current.read_bytes()).hexdigest()!=expected:
            raise RuntimeError('A custom Caddy service is active. Free ports 80/443 or configure a separate host before enabling Pi-2000.')
        run('systemctl','disable','--now','caddy');atomic(MARKER/'default-caddy-stopped','1\n')
    atomic(MARKER/'package-managed','1\n')
    if args.bootstrap_stdin:
        parts=sys.stdin.buffer.read(32768).split(b'\0')
        if len(parts)!=5:raise RuntimeError('Invalid installer input.')
        payload=dict(zip(('admin_password','linux_password','local_mode','local_user','local_port'),(part.decode() for part in parts)))
        if payload['admin_password']:
            run('systemctl','enable','--now','mariadb')
            subprocess.run(['/opt/win2k-admin/venv/bin/python',str(Path(__file__).with_name('provision.py'))],input=json.dumps(payload).encode(),check=True)
        elif not (STATE/'admin.sqlite3').exists() or (MARKER/'bootstrap-pending.json').exists():
            raise RuntimeError('Complete account setup with sudo pi2000web setup before starting services.')
    run('systemctl','daemon-reload')
    run('systemctl','enable','--now','win2k-sessions','pi2000-phpmyadmin')
    if args.restart_sessions:run('systemctl','restart','win2k-sessions')
    run('systemctl','restart','pi2000-phpmyadmin','win2k-admin')
    run('systemctl','enable','--now','win2k-admin','pi2000-web','win2k-backup.timer')
    run('systemctl','reload-or-restart','pi2000-web')
    print('Pi-2000Web installed at '+url,flush=True)
    if (STATE/'initial-password.txt').exists():print('First login: admin. Read the existing generated password locally with sudo cat /var/lib/win2k-admin/initial-password.txt.',flush=True)
    else:print('Sign in as admin with the password chosen during installation.',flush=True)
    if 'memory' not in Path('/sys/fs/cgroup/cgroup.controllers').read_text().split():print('Browser requires the memory controller: run sudo pi2000web enable-memory-controller and reboot when convenient.',flush=True)
    print('Account data is retained on remove/purge. Package upgrades preserve the session worker; restart sessions separately when worker code changes.',flush=True)

def doctor():
    data=tomllib.loads((CONFIG/'config.toml').read_text());url=data['network']['public_url']
    for unit in UNITS:
        if not active(unit):raise RuntimeError('Inactive service: '+unit)
    ca='/var/lib/caddy/.local/share/caddy/pki/authorities/local/root.crt'
    context=ssl.create_default_context(cafile=ca) if data['network']['tls']=='internal' else ssl.create_default_context()
    with urllib.request.urlopen(url,context=context,timeout=10) as response:page=response.read()
    if page!=Path('/srv/win2k/index.html').read_bytes():raise RuntimeError('HTTPS entry page differs from installed files.')
    import re
    for asset in re.findall(r'(?:src|href)="((?:assets|dist)/[^"#]+)"',page.decode()):
        with urllib.request.urlopen(url+'/'+asset,context=context,timeout=10) as response:
            if response.read()!=(Path('/srv/win2k')/asset.split('?')[0]).read_bytes():raise RuntimeError('Asset mismatch: '+asset)
    with sqlite3.connect('file:'+str(STATE/'admin.sqlite3')+'?mode=ro',uri=True) as db:
        if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or db.execute('PRAGMA foreign_key_check').fetchall():raise RuntimeError('Database integrity check failed.')
    if run('dpkg','--verify','pi2000web',capture=True):raise RuntimeError('Package files differ from the installed checksums.')
    print('PASS: installed package, services, trusted HTTPS assets and SQLite integrity.')

def memory():
    path=Path('/boot/firmware/cmdline.txt');text=path.read_text().strip()
    if '\n' in text:raise RuntimeError('Expected one boot command line.')
    if not (MARKER/'cmdline-before-memory.txt').exists():atomic(MARKER/'cmdline-before-memory.txt',text+'\n')
    tokens=[t for t in text.split() if t not in ('cgroup_disable=memory','cgroup_enable=memory')]+['cgroup_enable=memory']
    path.write_text(' '.join(tokens)+'\n');print('Memory controller configured. Reboot to activate it; no reboot has been performed.')

def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['configure','doctor','enable-memory-controller','restart-sessions','setup']);p.add_argument('--bootstrap-stdin',action='store_true',help=argparse.SUPPRESS);p.add_argument('--url');p.add_argument('--restart-sessions',action='store_true');args=p.parse_args()
    if os.geteuid()!=0:p.error('Run with sudo.')
    if args.command=='configure':configure(args)
    elif args.command=='doctor':doctor()
    elif args.command=='enable-memory-controller':memory()
    elif args.command=='setup':run('env','DEBIAN_FRONTEND=dialog','dpkg-reconfigure','-p','critical','pi2000web')
    else:run('systemctl','restart','win2k-sessions');print('Session worker restarted; previous live jobs ended.')
if __name__=='__main__':
    try:main()
    except Exception as exc:print('Pi-2000 configuration failed: '+str(exc),file=sys.stderr);sys.exit(1)
