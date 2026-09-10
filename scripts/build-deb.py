#!/usr/bin/env python3
"""Build the arm64/Trixie package, with offline, pinned Python runtimes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
from build_info import generate

ROOT=Path(__file__).resolve().parents[1]

def run(*args,**kw):subprocess.run(list(map(str,args)),check=True,**kw)

def runtime(name,requirements,wheels,work):
    cache=work/name
    fingerprint=hashlib.sha256(requirements.read_bytes()).hexdigest()
    if not (cache/'ready').exists() or (cache/'ready').read_text()!=fingerprint:
        shutil.rmtree(cache,ignore_errors=True);cache.mkdir(parents=True)
        run(sys.executable,'-m','venv','--without-pip',cache/'venv')
        run(ROOT/'.venv/bin/python','-m','pip','--python',cache/'venv/bin/python','install','--no-index','--find-links',wheels,'-r',requirements)
        run(ROOT/'.venv/bin/python','-m','pip','--python',cache/'venv/bin/python','check')
        # Console scripts must refer to the installed location, not the builder.
        installed='/opt/win2k-admin/venv' if name=='api' else '/opt/win2k-browser/venv'
        for path in (cache/'venv/bin').iterdir():
            if path.is_symlink():continue
            if path.name.startswith('activate') or path.name=='Activate.ps1':path.unlink();continue
            if path.read_bytes().startswith(b'#!'):
                path.write_bytes(path.read_bytes().replace(str(cache/'venv').encode(),installed.encode()))
        (cache/'venv/pyvenv.cfg').write_text('home = /usr/bin\ninclude-system-site-packages = false\nversion = 3.13\nexecutable = /usr/bin/python3.13\n')
        for directory in cache.rglob('__pycache__'):shutil.rmtree(directory)
        (cache/'ready').write_text(fingerprint)
    return cache/'venv'


def main():
    p=argparse.ArgumentParser();p.add_argument('--version',default='0.1.0~alpha.4-6');a=p.parse_args()
    if os.uname().machine!='aarch64' or sys.version_info[:2]!=(3,13):p.error('Build on arm64 with Python 3.13.')
    run('dpkg','--validate-version',a.version)
    work=ROOT/'.deb-build';work.mkdir(exist_ok=True)
    wheels=work/'wheels';wheels.mkdir(exist_ok=True)
    run(ROOT/'.venv/bin/python','-m','pip','download','--only-binary=:all:','--dest',wheels,'-r',ROOT/'server/requirements.txt')
    browser=ROOT/'.browser-build/wheels'
    if not browser.exists():p.error('Run scripts/build-browser.sh first.')
    run('sha256sum','--check','--quiet','SHA256SUMS',cwd=browser.parent)
    api_runtime=runtime('api',ROOT/'server/requirements.txt',wheels,work)
    browser_runtime=runtime('browser',ROOT/'server/browser-requirements.txt',browser,work)
    stage=work/'root';shutil.rmtree(stage,ignore_errors=True);stage.mkdir()
    def copy(source,dest):
        dest=stage/dest.lstrip('/');dest.parent.mkdir(parents=True,exist_ok=True)
        if source.is_dir():shutil.copytree(source,dest,symlinks=True)
        else:shutil.copy2(source,dest)
    for source in (ROOT/'server').glob('*.py'):copy(source,'/opt/win2k-admin/'+source.name)
    for name in ('requirements.txt','browser-config','phpmyadmin'):copy(ROOT/'server'/name,'/opt/win2k-admin/'+name)
    copy(api_runtime,'/opt/win2k-admin/venv');copy(browser_runtime,'/opt/win2k-browser/venv')
    for name in ('browser-requirements.txt','browser-source-revision.txt'):copy(ROOT/'server'/name,'/opt/win2k-browser/'+name)
    files=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
    for name in files:
        if name.startswith(('assets/','dist/')) and (ROOT/name).is_file():copy(ROOT/name,'/srv/win2k/'+name)
    import re
    page=(ROOT/'index.html').read_text()
    def hashed(m):return m[1]+'="'+m[2]+'?v='+hashlib.sha256((ROOT/m[2]).read_bytes()).hexdigest()[:16]+'"'
    page=re.sub(r'(src|href)="((?:assets|dist)/[^"?#]+)"',hashed,page)
    (stage/'srv/win2k/index.html').write_text(page)
    info=generate(ROOT);info['version']=a.version
    (stage/'opt/win2k-admin/build-info.json').write_text(json.dumps(info)+'\n')
    for source in (ROOT/'server').glob('*.service'):copy(source,'/usr/lib/systemd/system/'+source.name)
    copy(ROOT/'server/win2k-backup.timer','/usr/lib/systemd/system/win2k-backup.timer')
    copy(ROOT/'server/phpmyadmin/pi2000-phpmyadmin.service','/usr/lib/systemd/system/pi2000-phpmyadmin.service')
    unit=stage/'usr/lib/systemd/system/pi2000-phpmyadmin.service'
    unit.write_text(unit.read_text().replace('[Service]','[Service]\nBindReadOnlyPaths=/opt/win2k-admin/phpmyadmin/config.inc.php:/etc/phpmyadmin/config.inc.php'))
    copy(ROOT/'server/phpmyadmin/config.header.inc.php','/usr/share/phpmyadmin/config.header.inc.php')
    copy(ROOT/'packaging/pi2000-web.service','/usr/lib/systemd/system/pi2000-web.service')
    for name in ('package_setup.py','provision.py','Caddyfile.template'):copy(ROOT/'packaging'/name,'/usr/lib/pi2000web/'+name)
    copy(ROOT/'packaging/pi2000web','/usr/sbin/pi2000web')
    copy(ROOT/'scripts/setup.py','/usr/lib/pi2000web/source_setup.py')
    for name in ('README.md',):copy(ROOT/name,'/usr/share/doc/pi2000web/'+name)
    copy(ROOT/'docs/DEB-INSTALLATION.md','/usr/share/doc/pi2000web/DEB-INSTALLATION.md')
    control=stage/'DEBIAN';control.mkdir()
    size=sum(f.stat().st_size for f in stage.rglob('*') if f.is_file())//1024
    dependencies='debconf (>= 0.5), whiptail, mariadb-server, openssh-server, sudo, python3 (>= 3.13), python3 (<< 3.14), caddy, sqlite3, git, ca-certificates, iproute2, nodejs, bubblewrap, phpmyadmin, php8.4-fpm, php8.4-mysql, php8.4-mbstring, php8.4-xml, php8.4-zip, php8.4-gd, chromium, xvfb, pulseaudio, pulseaudio-utils, openbox, xauth, x11-xserver-utils, dbus-x11, gnome-keyring, fonts-liberation, libva-drm2, libva-x11-2, libxtst6, libffi8, libssl3t64'
    (control/'control').write_text(f'Package: pi2000web\nVersion: {a.version}\nArchitecture: arm64\nMaintainer: Pi-2000Web maintainers <noreply@github.com>\nSection: web\nPriority: optional\nInstalled-Size: {size}\nDepends: {dependencies}\nHomepage: https://github.com/xhonken/Pi-2000\nDescription: Private Windows 2000-inspired web desktop for Raspberry Pi\n Includes SSH, files, development tools, phpMyAdmin and a private Browser.\n Targets 64-bit Raspberry Pi OS based on Debian 13.\n')
    for name in ('preinst','postinst','prerm','postrm','config'):
        shutil.copy2(ROOT/'packaging'/name,control/name);(control/name).chmod(0o755)
    shutil.copy2(ROOT/'packaging/templates',control/'templates')
    (control/'md5sums').write_text(''.join(hashlib.md5(f.read_bytes()).hexdigest()+'  '+str(f.relative_to(stage))+'\n' for f in sorted(stage.rglob('*')) if f.is_file() and not f.is_symlink() and not f.is_relative_to(control)))
    output=ROOT/'build/packages';output.mkdir(parents=True,exist_ok=True)
    package=output/f'pi2000web_{a.version}_arm64.deb'
    run('dpkg-deb','--root-owner-group','-Zxz','--build',stage,package)
    package.with_suffix('.deb.sha256').write_text(hashlib.sha256(package.read_bytes()).hexdigest()+'  '+package.name+'\n')
    print(package)
if __name__=='__main__':main()
