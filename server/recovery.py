#!/usr/bin/env python3
"""Root-only recovery planning, guarded application and encrypted export.

No web endpoint. Plans contain summaries/digests, never credentials. Application
requires stopped services and an unchanged plan. Older format-1 backups remain
inspectable; they cannot promise home ownership/executable-mode recovery.
"""
import argparse
from contextlib import closing
import ctypes
import fcntl
import grp
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import sqlite3
import subprocess
import tempfile
import time
from backup import restore, checksum

SERVICES = ('pi2000-backup.timer','pi2000-backup.service','pi2000-admin','pi2000-sessions',
            'pi2000-arduino','pi2000-accounts','pi2000-terminal','pi2000-phpmyadmin')
STATE = Path('/var/lib/pi2000-admin')
ACCOUNTS = Path('/var/lib/pi2000-accounts')


def rows(path, table):
    with closing(sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True)) as conn:
        conn.row_factory=sqlite3.Row
        return [dict(r) for r in conn.execute('SELECT * FROM '+table)]


def write_json(path, data):
    path=Path(path)
    with open(path,'x',opener=lambda p,f:os.open(p,f,0o600)) as out:
        json.dump(data,out,indent=2);out.write('\n');out.flush();os.fsync(out.fileno())


def safe_members(stage, manifest):
    for name, meta in manifest.get('metadata',{}).items():
        path=Path(name)
        if path.is_absolute() or '..' in path.parts or not (stage/path).resolve().is_relative_to(stage.resolve()):
            raise RuntimeError('Unsafe recovery metadata')
        if not all(type(meta.get(k)) is int and meta[k]>=0 for k in ('uid','gid','mode')) or meta['mode']>0o777:
            raise RuntimeError('Invalid ownership/mode metadata')


class Host:
    """OS operations isolated behind an injectable host for recovery rehearsals."""
    root=Path('/')
    def path(self, absolute):return self.root/str(absolute).lstrip('/')
    def user(self,name):
        try:
            u=pwd.getpwnam(name)
            return {'name':u.pw_name,'uid':u.pw_uid,'gid':u.pw_gid,'home':u.pw_dir,'shell':u.pw_shell,'groups':[grp.getgrgid(g).gr_name for g in os.getgrouplist(name,u.pw_gid)]}
        except KeyError:return None
    def uid(self,uid):
        try:return pwd.getpwuid(uid).pw_name
        except KeyError:return None
    def group(self,name):
        try:return grp.getgrnam(name).gr_gid
        except KeyError:return None
    def gid(self,gid):
        try:return grp.getgrgid(gid).gr_name
        except KeyError:return None
    def run(self,*args):subprocess.run(args,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    def stopped(self):
        for service in SERVICES:
            result=subprocess.run(['systemctl','show','--property=ActiveState','--value',service],capture_output=True,text=True,timeout=10)
            if result.returncode or result.stdout.strip() not in ('inactive','failed'):
                raise RuntimeError('Stop all recovery services and verify systemd state first: '+service)
    def idle_users(self, names):
        ids={self.user(n)['uid'] for n in names if self.user(n)}
        for path in Path('/proc').glob('[0-9]*/status'):
            try:
                line=next(l for l in path.read_text().splitlines() if l.startswith('Uid:'))
                if any(int(v) in ids for v in line.split()[1:]):
                    raise RuntimeError('A managed user still has running processes; finish them before recovery.')
            except (OSError,StopIteration):continue
    def shadow(self):return self.path('/etc/shadow').read_text()
    def set_shadow(self, records):
        libc=ctypes.CDLL(None)
        if libc.lckpwdf()!=0:raise RuntimeError('Cannot lock the OS password database')
        try:
            path=self.path('/etc/shadow');stat=path.stat()
            text=replace_shadow(path.read_text(),records)
            with tempfile.NamedTemporaryFile(dir=path.parent,delete=False) as stream:
                temp=Path(stream.name)
                try:
                    stream.write(text.encode());stream.flush();os.fsync(stream.fileno())
                    os.chmod(temp,stat.st_mode & 0o777);os.chown(temp,stat.st_uid,stat.st_gid)
                    temp.replace(path)
                finally:temp.unlink(missing_ok=True)
        finally:libc.ulckpwdf()


def replace_shadow(text, records):
    existing={line.split(':',1)[0] for line in text.splitlines()}
    if not set(records)<=existing:raise RuntimeError('Recovery identity missing from OS password database')
    for name,line in records.items():
        if len(line.split(':'))!=9 or line.split(':')[0]!=name or '\n' in line or '\r' in line:
            raise RuntimeError('Invalid managed password recovery record')
    return '\n'.join(records.get(line.split(':',1)[0],line) for line in text.splitlines())+'\n'


def make_plan(stage, manifest, host, archive_digest):
    safe_members(stage,manifest)
    state=host.path(STATE);registry=host.path(ACCOUNTS)/'accounts.sqlite3'
    users={r['id']:r for r in rows(stage/'state/admin.sqlite3','users')}
    bindings=rows(stage/'system-accounts/accounts.sqlite3','bindings') if (stage/'system-accounts/accounts.sqlite3').exists() else []
    current={r['web_id']:r for r in rows(registry,'bindings')} if registry.exists() else {}
    ids={r['name']:r for r in json.loads((stage/'system-accounts/identities.json').read_text())} if (stage/'system-accounts/identities.json').exists() else {}
    blockers=[];accounts=[]
    backed_up={b['web_id'] for b in bindings}
    for key,binding in current.items():
        if binding['managed'] and key not in backed_up:
            blockers.append('Target has a managed identity absent from this backup: '+binding['name'])
    if manifest['format']<2 and any(b['managed'] for b in bindings):
        blockers.append('Old backup lacks managed-home ownership metadata; use documented manual recovery.')
    for b in bindings:
        name=b['name'];u=users.get(b['web_id'],{})
        if not u:
            blockers.append('Binding has no matching web account: '+name)
        if not b['managed']:
            # Never modify linked OS accounts; verify their mapping before reuse.
            actual=host.user(name)
            if not actual or actual['uid']!=b['uid'] or actual['home']!=b['home']:
                blockers.append('Linked account requires manual mapping: '+name)
            accounts.append({'name':name,'action':'preserve-linked'});continue
        if not re.fullmatch(r'pi2k_[1-9][0-9]*',name) or name!='pi2k_'+str(b['web_id']) or b['home']!='/home/'+name or b['phase']!='ready' or b['uid'] is None or not 1000<=b['uid']<65534:
            blockers.append('Incomplete or invalid managed binding: '+name);continue
        ident=ids.get(name)
        if not ident or ident['uid']!=b['uid'] or ident['group']!=name or not 1000<=ident['gid']<65534:
            blockers.append('Missing or invalid managed identity metadata: '+name);continue
        actual=host.user(name);home=host.path(b['home'])
        if actual:
            previous=current.get(b['web_id'],{})
            if not previous.get('managed') or previous.get('name')!=name or actual['uid']!=b['uid'] or actual['gid']!=ident['gid'] or actual['home']!=b['home']:
                blockers.append('Existing account is not the same managed identity: '+name)
        elif host.uid(b['uid']) or home.exists() or home.is_symlink():
            blockers.append('UID or home is already occupied: '+name)
        if host.group(name) not in (None,ident['gid']) or host.gid(ident['gid']) not in (None,name):
            blockers.append('Primary group conflict: '+name)
        if home.is_symlink():blockers.append('Managed home is a symlink: '+name)
        accounts.append({'name':name,'uid':b['uid'],'gid':ident['gid'],'home':b['home'],
                         'action':'restore' if actual else 'create','active':bool(u.get('active')),
                         'terminal':bool(u.get('active') and u.get('role')=='admin')})
    managed={a['name']:a for a in accounts if a['action']!='preserve-linked'}
    for name,meta in manifest.get('metadata',{}).items():
        parts=Path(name).parts
        if len(parts)>=3 and parts[:2]==('system-accounts','homes'):
            a=managed.get(parts[2])
            if not a or meta['uid'] not in (0,a['uid']) or meta['gid'] not in (0,a['gid']):
                blockers.append('Home has ownership requiring manual recovery: '+name)
    for name in managed:
        home=stage/'system-accounts/homes'/name
        for path in [home,*home.rglob('*')] if home.exists() else []:
            if path.relative_to(stage).as_posix() not in manifest.get('metadata',{}):
                blockers.append('Missing home ownership metadata: '+path.relative_to(stage).as_posix())
    if bindings:
        if not (stage/'system-accounts/generation.key').is_file():blockers.append('Missing account generation key')
        shadow_path=stage/'system-accounts/shadow'
        shadow={line.split(':')[0]:line for line in shadow_path.read_text().splitlines() if line} if shadow_path.exists() else {}
        if not set(managed)<=set(shadow):blockers.append('Missing managed password recovery records')
        for name in managed:
            if name in shadow and len(shadow[name].split(':'))!=9:blockers.append('Invalid password recovery metadata')
            if not (stage/'system-accounts/homes'/name).is_dir():blockers.append('Missing managed home: '+name)
    if state.is_symlink() or host.path(ACCOUNTS).is_symlink():blockers.append('Platform data root is a symlink')
    # Bind approval to the target identities/registry and database as well as the archive.
    target={'database':checksum(state/'admin.sqlite3') if (state/'admin.sqlite3').exists() else None,
            'registry':checksum(registry) if registry.exists() else None,
            'identities':{a['name']:host.user(a['name']) for a in accounts}}
    plan={'format':1,'archive_sha256':archive_digest,'backup_created':manifest['created'],
          'backup_format':manifest['format'],'application':manifest.get('application'),
          'accounts':accounts,'blockers':sorted(set(blockers)),'target':target,
          'changes':['Replace private application state; discard login tokens.',
                     'Restore the managed account registry, passwords and homes; preserve linked OS accounts.',
                     'Preserve current directories for rollback; keep services stopped for verification.']}
    plan['id']=hashlib.sha256(json.dumps(plan,sort_keys=True).encode()).hexdigest()
    return plan


def apply_plan(stage, manifest, plan, host):
    if plan['blockers']:raise RuntimeError('Resolve recovery plan blockers first.')
    host.stopped()
    accounts=[a for a in plan['accounts'] if a['action']!='preserve-linked']
    host.idle_users([a['name'] for a in accounts])
    fresh=make_plan(stage,manifest,host,plan['archive_sha256'])
    if any(plan.get(key)!=value for key,value in fresh.items()):
        raise RuntimeError('Target changed or plan modified; generate and review a new plan.')
    owner=host.user('pi2000-admin')
    if not owner:raise RuntimeError('Install the matching application and service account first.')
    if any(host.group(name) is None for name in ('pi2000-users','pi2000-terminal')) and accounts:
        raise RuntimeError('Install the account/SSH policy before recovery.')
    installed=host.path('/opt/pi2000-admin/build-info.json')
    if manifest.get('application') and (not installed.exists() or json.loads(installed.read_text()).get('build')!=manifest['application'].get('build')):
        raise RuntimeError('Install the matching application build before restoring its data.')
    rollback=host.path('/var/backups/pi2000')/('recovery-'+time.strftime('%Y%m%dT%H%M%S')+'-'+plan['id'][:8])
    rollback.parent.mkdir(parents=True,mode=0o700,exist_ok=True)
    for destination in [STATE,ACCOUNTS,*[a['home'] for a in accounts]]:
        target=host.path(destination)
        existing=target if target.exists() else target.parent
        while not existing.exists():existing=existing.parent
        if existing.stat().st_dev!=rollback.parent.stat().st_dev:
            raise RuntimeError('Cross-filesystem recovery needs manual staging; no changes made: '+str(destination))
    rollback.mkdir(mode=0o700,exist_ok=False)
    write_json(rollback/'plan.json',plan)
    # Write intent before each mutation; preserve a private audit after a crash.
    def journal(event, **fields):
        with open(rollback/'journal.jsonl','a',opener=lambda p,f:os.open(p,f,0o600)) as out:
            out.write(json.dumps({'event':event,**fields})+'\n');out.flush();os.fsync(out.fileno())
    moved=[];created=[];groups=[]
    old_shadow={line.split(':')[0]:line for line in host.shadow().splitlines() if line.split(':')[0] in {a['name'] for a in accounts if a['action']=='restore'}}
    write_json(rollback/'previous-passwords.json',old_shadow)
    def replace(source,destination):
        destination=host.path(destination);saved=rollback/str(len(moved))
        existed=destination.exists()
        journal('replace-intent',destination=str(destination),saved=str(saved),existed=existed)
        if existed:destination.rename(saved)
        moved.append((destination,saved,existed))
        shutil.copytree(source,destination)
        journal('replaced',destination=str(destination))
    try:
        for a in accounts:
            if a['action']=='create':
                if host.group(a['name']) is None:
                    journal('create-group',name=a['name'])
                    host.run('groupadd','--gid',str(a['gid']),a['name']);groups.append(a['name'])
                journal('create-user',name=a['name'])
                host.run('useradd','--uid',str(a['uid']),'--gid',str(a['gid']),'--no-create-home','--home-dir',a['home'],'--shell','/usr/sbin/nologin','--groups','pi2000-users',a['name']);created.append(a['name'])
        replace(stage/'state',STATE)
        for path in [host.path(STATE),*host.path(STATE).rglob('*')]:
            os.chown(path,owner['uid'],owner['gid'])
            path.chmod(0o700 if path.is_dir() else 0o600)
        if (stage/'system-accounts').exists():
            account_stage=stage/'account-registry';account_stage.mkdir(mode=0o700)
            for name in ('accounts.sqlite3','generation.key'):shutil.copy2(stage/'system-accounts'/name,account_stage/name)
            replace(account_stage,ACCOUNTS)
        for a in accounts:
            replace(stage/'system-accounts/homes'/a['name'],a['home'])
        for name,meta in manifest.get('metadata',{}).items():
            if name.startswith('state/git-workspaces/'):
                path=host.path(STATE)/name.removeprefix('state/')
                if path.exists():path.chmod(meta['mode'])
            elif name.startswith('system-accounts/homes/'):
                parts=Path(name).parts;path=host.path('/home')/Path(*parts[2:])
                if path.exists():os.chown(path,meta['uid'],meta['gid']);path.chmod(meta['mode'])
        if accounts:
            # Restore password records without placing hashes in argv or logs.
            shadow={line.split(':')[0]:line for line in (stage/'system-accounts/shadow').read_text().splitlines() if line}
            for a in accounts:
                host.run('usermod','--shell','/bin/bash' if a['terminal'] else '/usr/sbin/nologin','--append','--groups','pi2000-users',a['name'])
                membership = 'pi2000-terminal' in host.user(a['name']).get('groups',[])
                if membership != a['terminal']:
                    host.run('gpasswd','-a' if a['terminal'] else '-d',a['name'],'pi2000-terminal')
            host.set_shadow({a['name']:shadow[a['name']] for a in accounts})
        write_json(rollback/'result.json',{'state':'restored-services-stopped','plan':plan['id'],
                    'previous':[{'destination':str(d),'saved':str(s),'existed':e} for d,s,e in moved]})
        journal('complete')
        return rollback
    except BaseException:
        journal('rollback-start')
        for dest,saved,existed in reversed(moved):
            if dest.exists():shutil.rmtree(dest)
            if existed:saved.rename(dest)
        if old_shadow:host.set_shadow(old_shadow)
        for name in reversed(created):host.run('userdel',name)
        for name in reversed(groups):host.run('groupdel',name)
        for a in accounts:
            previous=plan['target']['identities'].get(a['name'])
            if previous:
                host.run('usermod','--shell',previous['shell'],a['name'])
                membership = 'pi2000-terminal' in host.user(a['name']).get('groups',[])
                old_membership = 'pi2000-terminal' in previous.get('groups',[])
                if membership != old_membership:host.run('gpasswd','-a' if old_membership else '-d',a['name'],'pi2000-terminal')
        journal('rolled-back')
        raise


def export_encrypted(archive, destination, recipient, allow_same_device=False):
    if not shutil.which('age'):raise RuntimeError('Install the age package before encrypted export.')
    if not recipient.startswith('age1') or '\n' in recipient:raise RuntimeError('Use an age public recipient, never its private key.')
    if destination.with_suffix(destination.suffix+'.sha256').exists():raise RuntimeError('Export checksum destination already exists.')
    if destination.exists() or destination.is_symlink():raise RuntimeError('Export destination already exists.')
    with tempfile.TemporaryDirectory(prefix='pi2000-export-') as tmp:
        restore(archive,Path(tmp)/'verified')
    # Never silently fall back to an unmounted external destination.
    if not destination.parent.is_dir():raise RuntimeError('Mount/create the external destination first.')
    if not allow_same_device and archive.stat().st_dev==destination.parent.stat().st_dev:
        raise RuntimeError('Choose a different mounted filesystem; a copy on the same device cannot protect against disk failure.')
    with tempfile.NamedTemporaryFile(dir=destination.parent,prefix='.pi2000-export-',delete=False) as stream:temp=Path(stream.name)
    try:
        subprocess.run(['age','--recipient',recipient,'--output',str(temp),str(archive)],check=True)
        with temp.open('rb') as stream:os.fsync(stream.fileno())
        os.link(temp,destination)
        checksum_file=destination.with_suffix(destination.suffix+'.sha256')
        with checksum_file.open('x') as out:out.write(checksum(destination)+'  '+destination.name+'\n')
    finally:temp.unlink(missing_ok=True)


def main():
    os.umask(0o077)
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='action',required=True)
    plan=sub.add_parser('plan');plan.add_argument('archive',type=Path);plan.add_argument('--output',type=Path,required=True)
    apply=sub.add_parser('apply');apply.add_argument('archive',type=Path);apply.add_argument('--plan',type=Path,required=True);apply.add_argument('--confirm',required=True)
    export=sub.add_parser('export');export.add_argument('archive',type=Path);export.add_argument('--to',type=Path,required=True);export.add_argument('--recipient',required=True);export.add_argument('--allow-same-device',action='store_true',help='Explicitly allow a local rehearsal copy, not off-device protection.')
    a=p.parse_args()
    if os.geteuid()!=0:p.error('Run as OS root; no web account grants recovery access.')
    if a.action=='export':export_encrypted(a.archive,a.to,a.recipient,a.allow_same_device);print('Encrypted export and checksum created.');return
    with tempfile.TemporaryDirectory(prefix='pi2000-recovery-') as tmp:
        stage=Path(tmp)/'verified';manifest=restore(a.archive,stage)
        host=Host();digest=checksum(a.archive)
        if a.action=='plan':
            result=make_plan(stage,manifest,host,digest);result['archive']=str(a.archive.resolve())
            write_json(a.output,result)
            print(json.dumps({k:v for k,v in result.items() if k!='target'},indent=2))
        else:
            saved=json.loads(a.plan.read_text())
            if a.confirm!=saved['id'] or saved['archive_sha256']!=digest:raise RuntimeError('Plan confirmation/archive mismatch')
            with open('/run/lock/pi2000-recovery.lock','w') as lock:
                fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                rollback=apply_plan(stage,manifest,saved,host)
            print('Restored; services remain stopped. Verify accounts and start services explicitly. Previous data:',rollback)

if __name__=='__main__':main()
