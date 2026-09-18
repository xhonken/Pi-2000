"""Offline system-name migration. Root CLI only; never an HTTP capability.

Preview is read-only. Apply checks leased worker state again, backs up data and
code, preserves numeric ownership, and rolls namespace/code/config back on error.
"""
import argparse
import asyncio
import fcntl
import grp
import json
import os
from pathlib import Path
import pwd
import runpy
import shutil
import subprocess
import tempfile
import time
from contextlib import asynccontextmanager
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
from deployment import stage, activate, verify
from build_info import generate
from session_proxy import control

RENAMES = {'win2k-admin':'pi2000-admin', 'win2k-sessions':'pi2000-sessions',
           'win2k-backup':'pi2000-backup', 'win2k-browser':'pi2000-browser',
           '/srv/win2k':'/srv/pi2000', '/var/backups/win2k':'/var/backups/pi2000'}
PATHS = ('/opt/win2k-admin', '/opt/win2k-browser', '/var/lib/win2k-admin',
         '/srv/win2k', '/var/backups/win2k', '/var/lib/caddy/win2k-admin')
OLD_UNITS = ('win2k-admin.service','win2k-sessions.service','win2k-backup.service','win2k-backup.timer')
# Stop listeners first; start in reverse dependency order below.
UNITS = ('caddy.service','win2k-backup.timer','win2k-admin.service',
         'pi2000-phpmyadmin.service','pi2000-arduino.service','win2k-sessions.service',
         'pi2000-terminal.service','pi2000-accounts.service')
START = tuple(reversed(UNITS))
SOCKETS = ('/run/win2k-sessions/worker.sock','/run/pi2000-arduino/worker.sock')


def renamed(text):
    for old,new in RENAMES.items(): text=text.replace(old,new)
    return text


class Host:
    def __init__(self,root=Path('/')): self.root=Path(root)
    def path(self,name): return self.root / str(name).lstrip('/')
    def run(self,*args):
        return subprocess.run(args,check=True,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=300).stdout.strip()
    def active(self,unit):
        return subprocess.run(['systemctl','is-active','--quiet',unit],stdout=subprocess.DEVNULL).returncode==0
    def enabled(self,unit):
        return subprocess.run(['systemctl','is-enabled','--quiet',unit],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==0
    def account(self,name):
        try:
            u=pwd.getpwnam(name);return (u.pw_uid,u.pw_gid,u.pw_dir)
        except KeyError:return None
    def group(self,name):
        try:return grp.getgrnam(name).gr_gid
        except KeyError:return None
    def rename_account(self,reverse=False):
        old,new=('pi2000-admin','win2k-admin') if reverse else ('win2k-admin','pi2000-admin')
        if self.group(old) is not None: self.run('groupmod','--new-name',new,old)
        if self.account(old) is not None: self.run('usermod','--login',new,'--home','/var/lib/'+new,old)
    def wait_ready(self,timeout=60):
        # Type=simple is active before aiohttp has bound its listener. Require
        # the anonymous session boundary before running the full doctor once.
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            try:
                with urlopen('http://127.0.0.1:8765/api/session',timeout=2):pass
            except HTTPError as error:
                if error.code==401:return
            except (URLError,TimeoutError):pass
            time.sleep(0.5)
        raise RuntimeError('API did not become ready within the migration startup deadline.')
    def verify_live(self,source):
        self.wait_ready()
        self.run('bash',str(source/'scripts/doctor.sh'))


class Migration:
    def __init__(self,source,host=None):
        self.source=Path(source).resolve();self.host=host or Host();self.backup=None
    def plan(self):
        h=self.host
        if h.path('/var/lib/pi2000web/package-managed').exists():
            raise RuntimeError('This source-install migration does not replace dpkg-owned paths. Packaged installations require a separate package migration; no changes made.')
        account=h.account('win2k-admin')
        if account is None:
            if h.account('pi2000-admin') and all(h.path(renamed(p)).is_dir() for p in PATHS if p!='/opt/win2k-browser'):
                return {'state':'already migrated','moves':[]}
            raise RuntimeError('No complete legacy source installation found.')
        if h.account('pi2000-admin') or h.group('pi2000-admin') is not None:
            raise RuntimeError('The destination service account/group already exists; no merging is allowed.')
        if account[0]==0 or account[2]!='/var/lib/win2k-admin' or h.group('win2k-admin')!=account[1]:
            raise RuntimeError('Unexpected legacy service identity; review it manually.')
        moves=[]
        for old in PATHS:
            a,b=h.path(old),h.path(renamed(old))
            if not a.exists() and old=='/opt/win2k-browser':continue
            if a.is_symlink() or not a.is_dir() or b.exists() or b.is_symlink():
                raise RuntimeError('Missing, linked or conflicting migration directory: '+old)
            if a.stat().st_dev!=b.parent.stat().st_dev:raise RuntimeError('Directory move crosses filesystems: '+old)
            moves.append(old)
        for unit in OLD_UNITS:
            if h.path('/etc/systemd/system/'+renamed(unit)).exists():raise RuntimeError('Destination unit exists: '+renamed(unit))
            if h.path('/etc/systemd/system/'+unit+'.d').exists():raise RuntimeError('Review custom legacy unit overrides before migration: '+unit)
            old=h.path('/etc/systemd/system/'+unit)
            if old.is_symlink() or not old.is_file():raise RuntimeError('Expected a regular source-installed unit: '+unit)
        verify(h.path('/opt/win2k-admin'),'server');verify(h.path('/srv/win2k'),'web')
        setup=runpy.run_path(str(self.source/'scripts/setup.py'))
        caddy=h.path('/etc/caddy/Caddyfile')
        setup['check_caddy_ownership'](renamed(caddy.read_text()),False)
        return {'state':'ready','moves':moves,'service_uid':account[0],'service_gid':account[1],
                'active':[u for u in UNITS if h.active(u)],'enabled':[u for u in UNITS if h.enabled(u)],
                'units':{u:renamed(u) for u in OLD_UNITS}}
    def _snapshot(self,plan):
        h=self.host
        parent=h.path('/var/backups/pi2000-namespace');parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        self.backup=Path(tempfile.mkdtemp(prefix=time.strftime('%Y%m%dT%H%M%S-'),dir=parent));self.backup.chmod(0o700)
        shutil.copytree(h.path('/opt/win2k-admin'),self.backup/'server',ignore=shutil.ignore_patterns('venv','__pycache__'))
        shutil.copytree(h.path('/srv/win2k'),self.backup/'web')
        names={'/etc/caddy/Caddyfile','/etc/pi2000web/runtime.env'}
        names.update('/etc/systemd/system/'+u for u in OLD_UNITS)
        names.update('/etc/systemd/system/'+p.name for p in (self.source/'server').glob('*.service'))
        names.update(('/etc/systemd/system/pi2000-backup.timer','/etc/systemd/system/pi2000-phpmyadmin.service'))
        originals=[]
        for name in sorted(names):
            p=h.path(name)
            if p.is_symlink():raise RuntimeError('Configuration symlink needs manual review: '+name)
            if p.exists():
                target=self.backup/'files'/name.lstrip('/');target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target);originals.append(name)
        record={'plan':plan,'files':sorted(names),'originals':originals,'state':'prepared'}
        self._record(record);return record
    def _record(self,record):
        p=self.backup/'migration.json';temp=p.with_suffix('.tmp');temp.write_text(json.dumps(record,indent=2)+'\n');temp.chmod(0o600);temp.replace(p)
    def _rollback(self,record):
        h=self.host;plan=record['plan']
        # Stop new services before restoring files and numeric identity mappings.
        for unit in UNITS:
            if h.active(renamed(unit)):h.run('systemctl','stop',renamed(unit))
        for unit in plan['enabled']:
            if h.enabled(renamed(unit)):h.run('systemctl','disable',renamed(unit))
        app=h.path('/opt/pi2000-admin') if h.path('/opt/pi2000-admin').is_dir() else h.path('/opt/win2k-admin')
        site=h.path('/srv/pi2000') if h.path('/srv/pi2000').is_dir() else h.path('/srv/win2k')
        activate(self.backup/'server',app,'server');activate(self.backup/'web',site,'web')
        for old in reversed(plan['moves']):
            a,b=h.path(old),h.path(renamed(old))
            if a.is_symlink():
                if a.resolve()!=b.resolve():raise RuntimeError('Unexpected rollback link: '+old)
                a.unlink()
            if b.exists() and not a.exists():b.rename(a)
        h.rename_account(reverse=True)
        for name in record['files']:
            target=h.path(name)
            if name in record['originals']:
                target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(self.backup/'files'/name.lstrip('/'),target)
            else:target.unlink(missing_ok=True)
        h.run('systemctl','daemon-reload')
        for unit in plan['enabled']:h.run('systemctl','enable',unit)
        for unit in START:
            if unit in plan['active']:h.run('systemctl','start',unit)
        record['state']='rolled back';self._record(record)
    def apply(self,before_stop=lambda:None):
        """Called only while the CLI owns both workers' admission leases."""
        plan=self.plan()
        if plan['state']=='already migrated':return plan
        h=self.host
        # Existing backup code runs before any namespace/identity mutation.
        h.run('systemctl','start','win2k-backup.service')
        record=self._snapshot(plan)
        with tempfile.TemporaryDirectory(prefix='pi2000-namespace-stage-') as tmp:
            info=generate(self.source)
            stage(self.source,Path(tmp)/'server','server',info);stage(self.source,Path(tmp)/'web','web',info)
            # Backup/staging can outlive the first lease. Recheck immediately
            # before stopping anything; never treat a stale idle report as consent.
            before_stop()
            record['state']='applying';self._record(record)
            try:
                for unit in UNITS:
                    if unit in plan['active']:h.run('systemctl','stop',unit)
                h.rename_account()
                if h.account('pi2000-admin')[:2]!=(plan['service_uid'],plan['service_gid']):raise RuntimeError('Numeric service ownership changed')
                for old in plan['moves']:
                    a,b=h.path(old),h.path(renamed(old));a.rename(b);a.symlink_to(b)
                activate(Path(tmp)/'server',h.path('/opt/pi2000-admin'),'server')
                activate(Path(tmp)/'web',h.path('/srv/pi2000'),'web')
                for name in ('/etc/caddy/Caddyfile','/etc/pi2000web/runtime.env'):
                    p=h.path(name);p.write_text(renamed(p.read_text()))
                for unit in OLD_UNITS:
                    if unit in plan['enabled']:h.run('systemctl','disable',unit)
                    h.path('/etc/systemd/system/'+unit).unlink()
                unit_sources=[*(self.source/'server').glob('*.service'),self.source/'server/pi2000-backup.timer',self.source/'server/phpmyadmin/pi2000-phpmyadmin.service']
                for source in unit_sources:shutil.copy2(source,h.path('/etc/systemd/system/'+source.name))
                h.run('systemctl','daemon-reload')
                for unit in plan['enabled']:h.run('systemctl','enable',renamed(unit))
                for unit in START:
                    if unit in plan['active']:h.run('systemctl','start',renamed(unit))
                h.verify_live(self.source)
                record['state']='complete';self._record(record)
            except BaseException as error:
                # Keep command diagnostics in the root-only recovery snapshot.
                # Do not discard the original failure after a successful rollback.
                details=str(error)+'\n'+str(getattr(error,'stdout','') or '')+'\n'+str(getattr(error,'stderr','') or '')
                diagnostic=self.backup/'failure.txt';diagnostic.write_text(details);diagnostic.chmod(0o600)
                try:self._rollback(record)
                except BaseException:
                    record['state']='rollback needs operator attention';self._record(record)
                    raise RuntimeError('Migration and rollback failed. Services may be stopped. Recovery snapshot: '+str(self.backup)) from None
                raise RuntimeError('Migration failed; previous code, paths, identity and services restored. Snapshot: '+str(self.backup)) from None
        return {'state':'complete','snapshot':str(self.backup),'service_uid':plan['service_uid'],'service_gid':plan['service_gid']}


@asynccontextmanager
async def workers(allow_stop=False):
    import secrets
    leases=[]
    try:
        for socket in SOCKETS:
            lease=secrets.token_hex(16)
            result=await control(socket,'drain',lease=lease);runtime=result.get('runtime',{})
            leases.append((socket,lease))
            if runtime.get('protocol')!=1 or not runtime.get('draining'):raise RuntimeError('Worker cannot safely drain: '+socket)
            if runtime.get('busy') and not allow_stop:raise RuntimeError('Live jobs exist. No service was stopped. Finish them first, or explicitly approve --allow-session-stop.')
        async def recheck():
            for socket,lease in leases:
                runtime=(await control(socket,'drain',lease=lease)).get('runtime',{})
                if runtime.get('protocol')!=1 or not runtime.get('draining') or (runtime.get('busy') and not allow_stop):
                    raise RuntimeError('Worker state changed; no service was stopped. Retry when idle or explicitly approve live-job interruption.')
        yield recheck
    finally:
        for socket,lease in leases:
            for candidate in dict.fromkeys((socket,renamed(socket))):
                try:await control(candidate,'resume',lease=lease)
                except Exception:pass


async def main(args):
    migration=Migration(args.source)
    plan=migration.plan()
    if not args.apply or plan['state']=='already migrated':
        print(json.dumps(plan,indent=2))
        if plan['state']=='ready':
            for socket in SOCKETS:
                runtime=(await control(socket,'status')).get('runtime',{})
                print(json.dumps({'worker':runtime.get('component'),'busy':runtime.get('busy'),'work':runtime.get('work')}))
        return
    async with workers(args.allow_session_stop) as recheck:
        loop=asyncio.get_running_loop()
        def before_stop():asyncio.run_coroutine_threadsafe(recheck(),loop).result(timeout=90)
        print(json.dumps(await asyncio.to_thread(migration.apply,before_stop),indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    mode=parser.add_mutually_exclusive_group();mode.add_argument('--plan',action='store_true');mode.add_argument('--apply',action='store_true')
    parser.add_argument('--allow-session-stop',action='store_true',help='Explicitly accept ending running terminals/browser/Arduino jobs during this maintenance window.')
    args=parser.parse_args()
    if os.geteuid()!=0:parser.error('Run as OS root; web administrator roles cannot migrate the host.')
    if args.allow_session_stop and not args.apply:parser.error('--allow-session-stop requires --apply')
    os.umask(0o077)
    with open('/run/lock/pi2000web-install.lock','w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        asyncio.run(main(args))
