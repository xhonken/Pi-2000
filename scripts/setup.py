#!/usr/bin/env python3
"""Pi-2000Web deployment: validated data-only configuration, install and diagnostics."""
import argparse
import fcntl
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import pwd
import re
import shlex
import shutil
import socket
import sqlite3
import ssl
import subprocess
import sys
import tempfile
import time
import tomllib
from urllib.parse import urlsplit
from urllib.request import urlopen
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
CONFIG = Path('/etc/pi2000web/config.toml')
ENV = Path('/etc/pi2000web/runtime.env')
CADDY = Path('/etc/caddy/Caddyfile')
STATE = Path('/var/lib/win2k-admin')
APP = Path('/opt/win2k-admin')
SITE = Path('/srv/win2k')
CA = Path('/var/lib/caddy/.local/share/caddy/pki/authorities/local/root.crt')
BASE_PACKAGES = ['python3-venv', 'caddy', 'sqlite3', 'git', 'ca-certificates', 'sudo', 'iproute2', 'nodejs', 'bubblewrap']
BROWSER_PACKAGES = ['chromium', 'xvfb', 'pulseaudio', 'pulseaudio-utils', 'bubblewrap',
                    'openbox', 'xauth', 'x11-xserver-utils', 'dbus-x11', 'gnome-keyring',
                    'fonts-liberation', 'nodejs', 'npm', 'build-essential',
                    'libva-drm2', 'libva-x11-2', 'libxtst6']


def read_config(path):
    data = tomllib.loads(Path(path).read_text())
    if set(data) != {'network', 'features'}:
        raise ValueError('Configuration must contain only [network] and [features].')
    n, f = data['network'], data['features']
    if not isinstance(n, dict) or set(n) != {'public_url', 'tls', 'bind_address'}:
        raise ValueError('[network] requires public_url, tls and bind_address only.')
    if not isinstance(f, dict) or set(f) != {'browser'} or type(f['browser']) is not bool:
        raise ValueError('[features] requires browser = true or false.')
    if any(not isinstance(v, str) for v in n.values()):
        raise ValueError('Network settings must be strings.')
    raw = n['public_url']
    if re.search(r'[\s\x00-\x1f\x7f]', raw):
        raise ValueError('public_url must not contain whitespace or control characters.')
    url = urlsplit(raw)
    if (url.scheme != 'https' or not url.hostname or url.username or url.password or
            url.path not in ('', '/') or url.query or url.fragment or url.port not in (None, 443)):
        raise ValueError('public_url must be https://HOST with no credentials, path or custom port.')
    host = url.hostname.lower()
    try:
        address = ipaddress.ip_address(host)
        if address.is_unspecified or address.is_multicast or '%' in host:
            raise ValueError('Use a concrete unicast IP address.')
        host = '[' + str(address) + ']' if address.version == 6 else str(address)
    except ValueError:
        if not re.fullmatch(r'(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)*[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', host):
            raise ValueError('Invalid hostname or IP address.') from None
        # Numeric addresses must not sneak past IP validation as DNS names.
        if re.fullmatch(r'[0-9.]+', host):
            raise ValueError('Invalid IP address.')
    if n['tls'] not in ('internal', 'public'):
        raise ValueError('tls must be internal or public.')
    if n['tls'] == 'public':
        try:
            ipaddress.ip_address(host.strip('[]'))
        except ValueError:
            if '.' not in host or host.endswith(('.local', '.localhost', '.test', '.invalid', '.example', '.internal', '.lan')):
                raise ValueError('Public TLS requires a public DNS hostname; use internal for LAN names.')
        else:
            raise ValueError('Use internal TLS for IP addresses in this installer.')
    bind = n['bind_address']
    if bind:
        addr = ipaddress.ip_address(bind)
        if addr.is_multicast or '%' in bind:
            raise ValueError('bind_address must be a local unicast IP, not a scoped or multicast address.')
        bind = str(addr)
    return {'network': {'public_url': 'https://' + host, 'tls': n['tls'], 'bind_address': bind},
            'features': {'browser': f['browser']}}


def config_text(config):
    n = config['network']
    return ('# Pi-2000Web deployment settings. No passwords belong in this file.\n[network]\n' +
            ''.join(f'{k} = {json.dumps(v)}\n' for k, v in n.items()) +
            '\n[features]\nbrowser = ' + str(config['features']['browser']).lower() + '\n')


def render(config):
    n = config['network']
    caddy = (ROOT / 'server/Caddyfile.template').read_text()
    caddy = caddy.replace('@PUBLIC_URL@', n['public_url']).replace('@BIND@',
        '    bind ' + n['bind_address'] + '\n' if n['bind_address'] else '')
    caddy = caddy.replace('@TLS@', 'tls internal' if n['tls'] == 'internal' else '# Public certificate: automatic HTTPS')
    return {'Caddyfile': caddy, 'runtime.env': 'WIN2K_ORIGIN=' + n['public_url'] + '\n',
            'config.toml': config_text(config)}


def run(*args, capture=False, **kwargs):
    result = subprocess.run([str(a) for a in args], check=True, text=True,
                            stdout=subprocess.PIPE if capture else None, **kwargs)
    return result.stdout.strip() if capture else ''


def active(unit):
    return subprocess.run(['systemctl', 'is-active', '--quiet', unit]).returncode == 0


def atomic(path, text, mode=0o644):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def existing_origin():
    if ENV.exists():
        for line in ENV.read_text().splitlines():
            if line.startswith('WIN2K_ORIGIN='):
                return line.split('=', 1)[1].strip('"')
    values = run('systemctl', 'show', 'win2k-admin', '--property=Environment', '--value', capture=True)
    return next((v.split('=', 1)[1] for v in shlex.split(values) if v.startswith('WIN2K_ORIGIN=')), None)


def check_caddy_ownership(text, adopt):
    if not text.strip():
        return
    # Accept the packaged default welcome site, but never another user's site.
    lines = '\n'.join(line.split('#', 1)[0].strip() for line in text.splitlines())
    compact = re.sub(r'\s+', ' ', lines).strip()
    if text.startswith('# Managed by Pi-2000Web.'):
        host = re.search(r'https://[^\s{]+', compact)
        bind = re.search(r'\bbind ([^ ]+)', compact)
        if host:
            candidate = {'network': {'public_url': host[0], 'bind_address': bind[1] if bind else '',
                                     'tls': 'internal' if 'tls internal' in compact else 'public'},
                         'features': {'browser': True}}
            expected = render(candidate)['Caddyfile']
            expected = re.sub(r'\s+', ' ', '\n'.join(line.split('#', 1)[0].strip() for line in expected.splitlines())).strip()
            if compact == expected:
                return
    if compact == ':80 { root * /usr/share/caddy file_server }':
        return
    if adopt:
        # Legacy adoption is narrow: compare the complete non-comment token sequence.
        origin = existing_origin()
        if origin:
            host = urlsplit(origin).hostname
            expected = ('{ admin unix//var/lib/caddy/win2k-admin/control.sock } '
                        f'http://{host} {{ bind {host} redir https://{host}{{uri}} permanent }} '
                        f'https://{host} {{ bind {host} tls internal header {{ '
                        'X-Content-Type-Options nosniff X-Frame-Options SAMEORIGIN Referrer-Policy same-origin } '
                        'handle /api/* { reverse_proxy 127.0.0.1:8765 } '
                        'handle { root * /srv/win2k file_server } }')
            if compact == expected:
                return
    raise ValueError('Existing Caddyfile is not managed by Pi-2000Web. It was not changed. '
                     'Use a dedicated Pi or integrate the generated site manually; see docs/CADDY.md. '
                     'For the original single-site deployment, use --adopt-existing.')


def preflight(config, adopt=False, restart=False):
    if os.geteuid() != 0:
        raise ValueError('Run with sudo. Use --check or --render-dir without sudo for a preview.')
    if not Path('/run/systemd/system').exists():
        raise ValueError('This installer requires a running systemd host.')
    os_info = dict(line.split('=', 1) for line in Path('/etc/os-release').read_text().splitlines() if '=' in line)
    if os_info.get('VERSION_ID', '').strip('"') != '13' or os_info.get('ID', '').strip('"') not in ('debian', 'raspbian'):
        raise ValueError('Supported target: 64-bit Debian 13 / Raspberry Pi OS based on Debian 13.')
    if run('dpkg', '--print-architecture', capture=True) != 'arm64':
        raise ValueError('This installer currently supports arm64 (64-bit Raspberry Pi 5).')
    try:
        socket.getaddrinfo(urlsplit(config['network']['public_url']).hostname, 443)
    except socket.gaierror as exc:
        raise ValueError('The public hostname does not resolve on the Pi. Configure DNS or use its LAN IP.') from exc
    if CADDY.exists():
        check_caddy_ownership(CADDY.read_text(), adopt)
    if active('win2k-sessions'):
        old = existing_origin()
        if old != config['network']['public_url'] and not restart:
            raise ValueError('Changing the public URL requires a worker restart. Re-run with '
                             '--restart-sessions when running jobs may be ended.')
    if shutil.disk_usage('/var').free < (6 if config['features']['browser'] else 2) * 1024**3:
        raise ValueError('Insufficient free space: allow 6 GiB with Browser, or 2 GiB without it.')
    # Fail before package installation when a different daemon owns web ports.
    listeners = run('ss', '-H', '-ltnp', capture=True)
    for line in listeners.splitlines():
        fields = line.split()
        if len(fields) > 3 and fields[3].rsplit(':', 1)[-1] in ('80', '443') and '"caddy"' not in line:
            raise ValueError('Port 80 or 443 is occupied by another process. Resolve it before installation.')
    if not active('win2k-admin') and any(len(line.split()) > 3 and line.split()[3].rsplit(':', 1)[-1] == '8765' for line in listeners.splitlines()):
        raise ValueError('API port 8765 is occupied. Resolve it before installation.')
    bind = config['network']['bind_address']
    if bind:
        family = socket.AF_INET6 if ':' in bind else socket.AF_INET
        with socket.socket(family) as sock:
            try:
                sock.bind((bind, 0))
            except OSError as exc:
                raise ValueError('bind_address is not available on this Pi: ' + str(exc)) from exc


def ensure_account(name, home):
    try:
        entry = pwd.getpwnam(name)
    except KeyError:
        run('useradd', '--system', '--user-group', '--home-dir', home, '--shell', '/usr/sbin/nologin', name)
        entry = pwd.getpwnam(name)
    if entry.pw_uid == 0:
        raise ValueError('Refusing to use a privileged service account: ' + name)
    run('install', '-d', '-o', name, '-g', str(entry.pw_gid), '-m', '700', home)


def install_browser():
    build_home = Path('/var/cache/pi2000web/build')
    ensure_account('pi2000-build', build_home)
    checkout = build_home / 'source'
    (checkout / 'scripts').mkdir(parents=True, exist_ok=True)
    (checkout / 'server').mkdir(exist_ok=True)
    for name in ['browser-requirements.txt', 'browser-source-revision.txt']:
        shutil.copy2(ROOT / 'server' / name, checkout / 'server' / name)
    shutil.copy2(ROOT / 'scripts/build-browser.sh', checkout / 'scripts/build-browser.sh')
    run('chown', '-R', 'pi2000-build:pi2000-build', checkout)
    print('Building the pinned browser client as an unprivileged account; this may take several minutes.', flush=True)
    run('runuser', '-u', 'pi2000-build', '--', 'env', 'HOME=' + str(build_home),
        'bash', checkout / 'scripts/build-browser.sh')
    build = checkout / '.browser-build'
    run('sha256sum', '--check', '--quiet', 'SHA256SUMS', cwd=build)
    if (build / 'architecture').read_text().strip() != os.uname().machine:
        raise ValueError('Browser build architecture mismatch.')
    venv = Path('/opt/win2k-browser/venv')
    run('python3', '-m', 'venv', venv)
    run(venv / 'bin/pip', 'install', '--no-index', '--find-links', build / 'wheels',
        '-r', ROOT / 'server/browser-requirements.txt')
    run(venv / 'bin/pip', 'check')
    for name in ['browser-requirements.txt', 'browser-source-revision.txt']:
        shutil.copy2(ROOT / 'server' / name, venv.parent / name)


def tls_context(config):
    if config['network']['tls'] == 'internal':
        if not CA.exists():
            raise ValueError('Local Caddy CA is not ready. Check journalctl -u caddy.')
        return ssl.create_default_context(cafile=str(CA))
    return ssl.create_default_context()


def verify(config, compare=True):
    origin = config['network']['public_url']
    context = tls_context(config)
    def fetch(path):
        with urlopen(origin + '/' + path, context=context, timeout=10) as response:
            if urlsplit(response.url).netloc != urlsplit(origin).netloc:
                raise ValueError('Unexpected redirect to another host.')
            return response.read()
    page = fetch('')
    if b'Pi-2000Web' not in page or b'Content-Security-Policy' not in page:
        raise ValueError('HTTPS did not return the Pi-2000Web desktop.')
    if compare:
        for source in (ROOT / 'server').glob('*.py'):
            if source.read_bytes() != (APP / source.name).read_bytes():
                raise ValueError('Installed API source differs from checkout: ' + source.name)
        if page != (SITE / 'index.html').read_bytes():
            raise ValueError('HTTPS entry page differs from the installed page.')
        assets = re.findall(r'(?:src|href)="((?:assets|dist)/[^"#]+)"', page.decode())
        for asset in assets:
            if fetch(asset) != (ROOT / asset.split('?')[0]).read_bytes():
                raise ValueError('HTTPS asset mismatch: ' + asset)
    try:
        fetch('api/taskmanager')
    except HTTPError as exc:
        if exc.code != 401:
            raise ValueError('Unexpected unauthenticated API status: ' + str(exc.code)) from exc
    else:
        raise ValueError('Unauthenticated API request was not rejected.')
    with sqlite3.connect('file:' + str(STATE / 'admin.sqlite3') + '?mode=ro', uri=True) as db:
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or db.execute('PRAGMA foreign_key_check').fetchone():
            raise ValueError('Database integrity check failed.')
    for unit in ('win2k-admin', 'win2k-sessions', 'caddy', 'win2k-backup.timer'):
        if not active(unit):
            raise ValueError('Service is not active: ' + unit)
    if subprocess.run(['runuser', '-u', 'win2k-admin', '--', 'test', '-r',
                       '/var/lib/caddy/win2k-admin/control.sock']).returncode == 0:
        raise ValueError('Application can access Caddy administration socket.')
    print('PASS: trusted HTTPS, desktop assets, private API, SQLite integrity and services.', flush=True)


def deploy(config, args):
    preflight(config, args.adopt_existing, args.restart_sessions)
    old_origin = existing_origin()
    old_config = read_config(CONFIG) if CONFIG.exists() else None
    if args.command == 'update' and not (APP / 'venv/bin/python').exists():
        raise ValueError('No existing installation. Run scripts/install.sh first.')
    if old_config and old_config['features']['browser'] and not config['features']['browser']:
        raise ValueError('browser=false skips installation on a new Pi; it does not uninstall an existing browser.')
    if args.command == 'update' and config['features']['browser']:
        browser_root = Path('/opt/win2k-browser')
        required = ['browser-requirements.txt', 'browser-source-revision.txt']
        if not (browser_root / 'venv/bin/python').exists() or any(
                not (browser_root / name).exists() or (browser_root / name).read_bytes() != (ROOT / 'server' / name).read_bytes()
                for name in required):
            raise ValueError('Browser dependencies differ or are missing. Run install.sh with the installed configuration first.')
    backup = None
    if (STATE / 'admin.sqlite3').exists():
        run('systemctl', 'start', 'win2k-backup.service')
        backup = Path(tempfile.mkdtemp(prefix='pi2000web-update-', dir='/var/backups'))
        for name, source in [('app', APP), ('site', SITE)]:
            shutil.copytree(source, backup / name, ignore=shutil.ignore_patterns('venv', '__pycache__'))
        for name, source in [('Caddyfile', CADDY), ('config.toml', CONFIG), ('runtime.env', ENV)]:
            if source.exists():
                shutil.copy2(source, backup / name)
        print('Verified data backup and previous code snapshot:', backup, flush=True)
    if args.command == 'install':
        run('apt-get', 'update')
        run('apt-get', 'install', '--yes', '--no-install-recommends', *(BASE_PACKAGES + (BROWSER_PACKAGES if config['features']['browser'] else [])))
    ensure_account('win2k-admin', STATE)
    run('install', '-d', '-m', '755', APP, SITE)
    run('install', '-d', '-m', '700', '/var/backups/win2k')
    run('install', '-d', '-o', 'caddy', '-g', 'caddy', '-m', '700', '/var/lib/caddy/win2k-admin')
    if config['features']['browser'] and (args.command == 'install' or not Path('/opt/win2k-browser/venv/bin/python').exists()):
        if args.command == 'update':
            raise ValueError('Browser dependencies are missing. Run install.sh with this configuration.')
        install_browser()
    run('python3', '-m', 'venv', APP / 'venv')
    output = render(config)
    with tempfile.TemporaryDirectory(prefix='pi2000web-caddy-') as temporary:
        candidate = Path(temporary) / 'Caddyfile'
        candidate.write_text(output['Caddyfile'])
        output['Caddyfile'] = run('caddy', 'fmt', candidate, capture=True) + '\n'
        candidate.write_text(output['Caddyfile'])
        Path(temporary).chmod(0o755)
        run('runuser', '-u', 'caddy', '--', 'caddy', 'validate', '--config', candidate, '--adapter', 'caddyfile')
    # Keep metadata and locks owned by the service account, never recursively chown existing data.
    lock = STATE / 'files.lock'
    lock.touch(exist_ok=True)
    entry = pwd.getpwnam('win2k-admin')
    os.chown(lock, entry.pw_uid, entry.pw_gid)
    lock.chmod(0o600)
    atomic(ENV, output['runtime.env'])
    atomic(CONFIG, output['config.toml'], 0o600)
    try:
        run('bash', ROOT / 'scripts/publish-server.sh')
        run('bash', ROOT / 'scripts/publish-local.sh')
        if args.restart_sessions:
            print('Restarting session worker: existing terminal and browser jobs will end.', flush=True)
            run('systemctl', 'restart', 'win2k-sessions')
        atomic(CADDY, output['Caddyfile'])
        run('systemctl', 'enable', '--now', 'win2k-admin', 'caddy')
        # Explicit address handles migration from a previously enabled TCP admin endpoint.
        address = 'unix//var/lib/caddy/win2k-admin/control.sock'
        if not Path('/var/lib/caddy/win2k-admin/control.sock').exists():
            address = '127.0.0.1:2019'
        run('caddy', 'reload', '--config', CADDY, '--adapter', 'caddyfile', '--address', address)
        for attempt in range(30):
            try:
                verify(config)
                break
            except (OSError, ValueError, sqlite3.Error) as exc:
                if attempt == 29:
                    raise ValueError('Post-install check failed: ' + str(exc)) from exc
                time.sleep(2)
        run('systemctl', 'start', 'win2k-backup.service')
    except BaseException:
        # Retain backups and report the failure; never silently roll back a migrated DB.
        print('Installation did not complete. Check the error above and run doctor.sh after correcting it.', file=sys.stderr)
        if backup:
            print('Previous code/configuration:', backup, '; verified data archives: /var/backups/win2k', file=sys.stderr)
        raise
    print('\nPi-2000Web is ready at ' + config['network']['public_url'])
    print('Configuration: /etc/pi2000web/config.toml')
    if (STATE / 'initial-password.txt').exists():
        print('First login: admin. Read the generated password with:')
        print('  sudo cat /var/lib/win2k-admin/initial-password.txt')
    else:
        print('Existing accounts and passwords are unchanged.')
    if config['network']['tls'] == 'internal':
        print('Trust the local CA on each client; copy only root.crt, never root.key: ' + str(CA))
    if active('win2k-sessions') and old_origin and not args.restart_sessions:
        print('Existing terminal/browser sessions were preserved. Worker code changes apply on its next restart.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('install', 'update', 'doctor'))
    parser.add_argument('--config', type=Path, help='TOML file (install: ./pi2000.toml; update/doctor: installed config)')
    parser.add_argument('--check', action='store_true', help='Validate configuration and print the plan without changes')
    parser.add_argument('--render-dir', type=Path, help='Write reviewable configuration templates here; do not install')
    parser.add_argument('--adopt-existing', action='store_true', help='Adopt the original single-site Pi-2000Web Caddyfile')
    parser.add_argument('--restart-sessions', action='store_true', help='Explicitly allow ending worker jobs to apply its changes')
    args = parser.parse_args()
    path = args.config or (Path('pi2000.toml') if args.command == 'install' else CONFIG)
    try:
        config = read_config(path)
        if args.check or args.render_dir:
            print(config_text(config))
            print('Plan: install Debian packages, private service account, Python API, SQLite, Caddy HTTPS and backups.')
            print('Browser build:', 'enabled (npm/Python build as pi2000-build)' if config['features']['browser'] else 'skipped')
            if args.render_dir:
                args.render_dir.mkdir(parents=True, exist_ok=True)
                for name, text in render(config).items():
                    atomic(args.render_dir / name, text)
                for source in (ROOT / 'server').glob('win2k-*.*'):
                    shutil.copy2(source, args.render_dir / source.name)
            return 0
        if args.command == 'doctor':
            if os.geteuid() != 0:
                raise ValueError('Run doctor.sh with sudo to inspect private state and the local CA.')
            verify(config, compare=True)
            return 0
        if os.geteuid() != 0:
            raise ValueError('Run install/update with sudo, or use --check for a preview.')
        with open('/run/lock/pi2000web-install.lock', 'w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            deploy(config, args)
        return 0
    except (ValueError, OSError, subprocess.CalledProcessError, tomllib.TOMLDecodeError) as exc:
        print('ERROR:', exc, file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
