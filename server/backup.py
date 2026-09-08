"""Local snapshots and verified staging restores; no backup is sent off the server."""
import argparse
from contextlib import closing
import asyncio
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tarfile
import tempfile
import time
from datetime import datetime, timezone
from session_proxy import control

EXCLUDED = {'Cache','Code Cache','GPUCache','ShaderCache','GrShaderCache','DawnCache','session.log', 'SingletonLock','SingletonSocket','SingletonCookie'}

def check_database(path):
    with closing(sqlite3.connect(path)) as conn:
        if conn.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise RuntimeError('Database validation failed')
        if conn.execute('PRAGMA foreign_key_check').fetchone():
            raise RuntimeError('The database contains broken relationships')

def checksum(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()

def restore(archive, destination):
    expected = archive.with_suffix(archive.suffix + '.sha256').read_text().split()[0]
    if checksum(archive) != expected: raise RuntimeError('The backup checksum does not match')
    if destination.exists() and any(destination.iterdir()): raise RuntimeError('The restore directory must be empty')
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tarfile.open(archive, 'r:') as tar:
        for member in tar.getmembers():
            if not (member.isfile() or member.isdir()) or member.name.startswith('/') or '..' in Path(member.name).parts:
                raise RuntimeError('Disallowed path in the backup')
        tar.extractall(destination, filter='data')
    check_database(destination/'state/admin.sqlite3')
    manifest=json.loads((destination/'manifest.json').read_text())
    if manifest['format'] != 1: raise RuntimeError('Unknown backup format')
    return manifest

async def snapshot(state, target, socket, code, site=None):
    target.mkdir(parents=True, exist_ok=True, mode=0o700)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    archive=target/f'win2k-{stamp}.tar'
    maintenance=state/'maintenance.json'
    frozen=False
    def status(value):
        temp=state/'backup-status.tmp';temp.write_text(json.dumps(value));temp.chmod(0o600);os.chown(temp,state.stat().st_uid,state.stat().st_gid);temp.replace(state/'backup-status.json')
    try:
        pending = state/'maintenance.tmp'
        pending.write_text(json.dumps({'expires':time.time()+300}))
        os.chown(pending,state.stat().st_uid,state.stat().st_gid)
        pending.replace(maintenance)
        if socket:
            await control(socket,'freeze');frozen=True
        files_lock = (state/'files.lock').open('a')
        os.chown(files_lock.fileno(),state.stat().st_uid,state.stat().st_gid)
        await asyncio.to_thread(fcntl.flock, files_lock, fcntl.LOCK_EX)
        with tempfile.TemporaryDirectory(dir=target) as staging:
            staging=Path(staging)
            (staging/'state').mkdir()
            with closing(sqlite3.connect(state/'admin.sqlite3')) as source, closing(sqlite3.connect(staging/'state/admin.sqlite3')) as dest:
                source.backup(dest)
                if dest.execute("SELECT 1 FROM sqlite_master WHERE name='login_sessions'").fetchone():
                    dest.execute('DELETE FROM login_sessions')
                if dest.execute("SELECT 1 FROM sqlite_master WHERE name='files'").fetchone():
                    dest.execute("DELETE FROM files WHERE state='upload'")
                dest.commit()
            check_database(staging/'state/admin.sqlite3')
            manifest={'format':1,'created':datetime.now(timezone.utc).isoformat(),
                      'profiles':'quiesced filesystem snapshot; Chromium recovers its journals on restore',
                      'sessions':'running processes are not included'}
            (staging/'manifest.json').write_text(json.dumps(manifest,indent=2))
            def include(info):
                if info.name.endswith('.part') or '/garbage' in info.name or any(part in EXCLUDED for part in Path(info.name).parts) or not (info.isfile() or info.isdir()): return None
                info.uid=info.gid=0;info.uname=info.gname='root'
                info.mode=0o700 if info.isdir() else 0o600
                return info
            partial=archive.with_suffix('.partial')
            with tarfile.open(partial,'w:') as tar:
                tar.add(staging/'manifest.json',arcname='manifest.json',filter=include)
                tar.add(staging/'state',arcname='state',filter=include)
                if (state/'browsers').exists(): tar.add(state/'browsers',arcname='state/browsers',filter=include)
                if (state/'files').exists(): tar.add(state/'files',arcname='state/files',filter=include)
                if site and site.exists(): tar.add(site,arcname='site',filter=include)
                if code and code.exists():
                    for path in code.iterdir():
                        if path.suffix in ('.py','.service','.timer','.txt') or path.name=='browser-config':
                            tar.add(path,arcname='code/'+path.name,filter=include)
            partial.chmod(0o600);partial.replace(archive)
        files_lock.close()
        if frozen:
            await control(socket,'thaw');frozen=False
        maintenance.unlink(missing_ok=True)
        archive.with_suffix('.tar.sha256').write_text(checksum(archive)+'\n')
        with tempfile.TemporaryDirectory(dir=target) as restored:
            restore(archive,Path(restored))
        status({'state':'ok','created':manifest['created'],'verified_restore':True,'bytes':archive.stat().st_size,'location':'local'})
        # Only prune after a complete snapshot has been restored and verified.
        for old in sorted(target.glob('win2k-*.tar'))[:-7]:
            old.unlink();old.with_suffix('.tar.sha256').unlink(missing_ok=True)
        return archive
    except Exception:
        archive.with_suffix('.partial').unlink(missing_ok=True)
        archive.unlink(missing_ok=True)
        archive.with_suffix('.tar.sha256').unlink(missing_ok=True)
        status({'state':'failed','checked':datetime.now(timezone.utc).isoformat()})
        raise
    finally:
        if 'files_lock' in locals(): files_lock.close()
        if frozen: await control(socket,'thaw')
        maintenance.unlink(missing_ok=True)

def main():
    os.umask(0o077)
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['create','restore','thaw'])
    parser.add_argument('--state',type=Path,default=Path('/var/lib/win2k-admin'))
    parser.add_argument('--target',type=Path,default=Path('/var/backups/win2k'))
    parser.add_argument('--socket',default='/run/win2k-sessions/worker.sock')
    parser.add_argument('--code',type=Path,default=Path('/opt/win2k-admin'))
    parser.add_argument('--site',type=Path,default=Path('/srv/win2k'))
    parser.add_argument('--archive',type=Path)
    parser.add_argument('--destination',type=Path)
    args=parser.parse_args()
    if args.action=='restore':
        if not args.archive or not args.destination: parser.error('restore requires --archive and --destination')
        restore(args.archive,args.destination);print('Restore verified:',args.destination)
    elif args.action=='thaw':
        asyncio.run(control(args.socket,'thaw'));(args.state/'maintenance.json').unlink(missing_ok=True)
    else:
        with (args.state/'backup.lock').open('w') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            print(asyncio.run(snapshot(args.state,args.target,args.socket,args.code,args.site)))

if __name__=='__main__':main()
