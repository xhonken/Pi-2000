"""Private Arduino projects and bounded CLI jobs. No client-supplied shell commands."""
import asyncio
import codecs
import fcntl
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import signal
import stat
import tempfile
import time

from aiohttp import web, ClientSession, UnixConnector

CLI = Path(os.environ.get('WIN2K_ARDUINO_CLI', '/opt/pi2000-arduino/arduino-cli'))
SOCKET = os.environ.get('WIN2K_ARDUINO_SOCKET', '')
ESP_INDEX = 'https://espressif.github.io/arduino-esp32/package_esp32_index.json'
CORES = {'esp32:esp32': 'ESP32 by Espressif Systems', 'arduino:avr': 'Arduino AVR Boards'}
MAX_SOURCE = 2 * 1024 * 1024
MAX_RUNTIME = 12 * 1024**3
BAUDS = (9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600)
TEMPLATES = {
    'empty': 'void setup() {\n  // Run once.\n}\n\nvoid loop() {\n  // Run repeatedly.\n}\n',
    'serial': 'void setup() {\n  Serial.begin(115200);\n}\n\nvoid loop() {\n  Serial.println("Hello from Pi-2000!");\n  delay(1000);\n}\n',
    'blink': '// Set this pin to match your board and LED wiring.\nconst int ledPin = 2;\n\nvoid setup() {\n  pinMode(ledPin, OUTPUT);\n}\n\nvoid loop() {\n  digitalWrite(ledPin, HIGH);\n  delay(500);\n  digitalWrite(ledPin, LOW);\n  delay(500);\n}\n',
}


def valid_name(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,63}', value):
        raise web.HTTPBadRequest(text='Use a name starting with a letter, followed by letters, numbers or underscores (up to 64 characters).')
    return value


def valid_fqbn(value):
    if not isinstance(value, str) or len(value) > 1000 or not re.fullmatch(r'[A-Za-z0-9_-]+:[A-Za-z0-9_-]+:[A-Za-z0-9_-]+(?::[A-Za-z0-9_=,.-]+)?', value) or ':'.join(value.split(':')[:2]) not in CORES:
        raise web.HTTPBadRequest(text='Select an installed ESP32 or Arduino AVR board.')
    return value


def library_name(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9 _.+()/-]{0,119}', value) or '/' in value:
        raise web.HTTPBadRequest(text='Select a library from Library Manager.')
    return value


def version(value):
    if value is None or value == '': return ''
    if not isinstance(value, str) or not re.fullmatch(r'[0-9][A-Za-z0-9.+-]{0,49}', value):
        raise web.HTTPBadRequest(text='Select a package version.')
    return '@' + value


class ArduinoWorkshop:
    def __init__(self, app):
        self.app = app
        self.root = app.STATE / 'arduino-runtime'
        self.jobs = {}
        self.monitors = {}
        self.busy = False
        self.closing = False

    def initialize(self):
        self.root.mkdir(mode=0o700, exist_ok=True)
        with self.app.db() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS arduino_projects(
                id TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name TEXT NOT NULL, data TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1,
                updated REAL NOT NULL)''')
            db.execute('''CREATE TABLE IF NOT EXISTS arduino_jobs(
                user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE, data TEXT NOT NULL)''')
            for row in db.execute('SELECT user_id,data FROM arduino_jobs').fetchall():
                job = json.loads(row['data'])
                if job['state'] == 'running':
                    job['state'] = 'interrupted'
                    job['output'] += '\nArduino service restarted. The operation was interrupted; verify or upload again.\n'
                    db.execute('UPDATE arduino_jobs SET data=? WHERE user_id=?', (json.dumps(job), row['user_id']))
        for path in self.app.STATE.glob('arduino-job-*'):
            if path.is_dir() and not path.is_symlink(): shutil.rmtree(path)

    def project(self, uid, key):
        with self.app.db() as db:
            row = db.execute('SELECT * FROM arduino_projects WHERE id=? AND user_id=?', (key, uid)).fetchone()
        if not row: raise web.HTTPNotFound(text='Arduino project not found in your account.')
        return {**dict(row), **json.loads(row['data']), 'data': None}

    def source(self, data):
        name = valid_name(data.get('name'))
        files = data.get('files')
        if not isinstance(files, dict) or not 1 <= len(files) <= 40 or name + '.ino' not in files:
            raise web.HTTPBadRequest(text='A project needs its matching main .ino file and supports up to 40 files.')
        for path, content in files.items():
            if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]{0,100}\.(ino|h|hpp|c|cpp|S|txt)', path) or '..' in path or not isinstance(content, str):
                raise web.HTTPBadRequest(text='Use plain sketch file names ending in .ino, .h, .hpp, .c, .cpp, .S or .txt.')
        if sum(len(content.encode()) for content in files.values()) > MAX_SOURCE:
            raise web.HTTPBadRequest(text='A project supports up to 2 MB of source text.')
        fqbn = data.get('fqbn', '')
        if fqbn: valid_fqbn(fqbn)
        board_name = data.get('board_name', '')
        if not isinstance(board_name, str) or len(board_name) > 150: raise web.HTTPBadRequest(text='Invalid board name.')
        return name, {'files': files, 'fqbn': fqbn, 'board_name': board_name}

    def live(self, token):
        return self.app.session_valid(self.app.SESSIONS.get(token))

    def usb(self, user):
        if user['role'] != 'admin':
            raise web.HTTPForbidden(text='USB upload and Serial Monitor require a Pi-2000 administrator account. Projects and Verify are available to every user.')

    def ports(self):
        result = []
        for base in ('ttyUSB*', 'ttyACM*'):
            for p in sorted(Path('/dev').glob(base)):
                if not re.fullmatch(r'tty(?:USB|ACM)[0-9]+', p.name): continue
                sys = Path('/sys/class/tty') / p.name / 'device'
                if not sys.exists() or not any((parent/'idVendor').exists() for parent in sys.resolve().parents): continue
                info = {}
                for parent in sys.resolve().parents:
                    for key in ('manufacturer', 'product', 'serial'):
                        if key not in info and (parent/key).is_file():
                            info[key] = (parent/key).read_text(errors='replace').strip()[:150]
                result.append({'path': str(p), 'label': ' '.join(info.get(k, '') for k in ('manufacturer', 'product')).strip() or p.name,
                               'serial': info.get('serial', ''), 'accessible': os.access(p, os.R_OK | os.W_OK)})
        return result

    def port(self, value):
        if value not in {p['path'] for p in self.ports()}:
            raise web.HTTPBadRequest(text='Select a currently connected USB serial port on the Pi. Reconnect and refresh ports if the device changed.')
        p = Path(value)
        if p.is_symlink() or not stat.S_ISCHR(p.stat().st_mode):
            raise web.HTTPBadRequest(text='The selected USB device is no longer available.')
        if not os.access(p, os.R_OK | os.W_OK):
            raise web.HTTPConflict(text='The Arduino service cannot open this USB port. Check the installed service USB permissions.')
        return value

    @staticmethod
    def port_identity(port):
        value = Path(port).stat()
        return (value.st_rdev, value.st_ino, value.st_ctime_ns)

    def runtime(self, uid):
        root = self.root / str(uid)
        root.mkdir(mode=0o700, exist_ok=True)
        for part in ('data', 'downloads', 'user', 'cache'):
            (root/part).mkdir(mode=0o700, exist_ok=True)
        return root

    def command(self, uid, args, *, network=False, work=None, port=None):
        if not CLI.is_file() or not Path('/usr/bin/bwrap').is_file():
            raise web.HTTPServiceUnavailable(text='Arduino tools are not installed yet. Ask the Pi operator to finish the Arduino Workshop installation.')
        root = self.runtime(uid)
        cmd = ['/usr/bin/prlimit', '--cpu=900', '--as=4294967296', '--fsize=2147483648', '--nofile=256', '--',
               '/usr/bin/bwrap', '--unshare-all', '--die-with-parent', '--new-session']
        if network: cmd += ['--share-net']
        cmd += ['--ro-bind', '/usr', '/usr', '--symlink', 'usr/bin', '/bin', '--symlink', 'usr/lib', '/lib',
                '--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp', '--dir', '/etc',
                '--ro-bind', '/etc/ssl/certs', '/etc/ssl/certs', '--ro-bind', '/etc/resolv.conf', '/etc/resolv.conf',
                '--ro-bind', '/etc/hosts', '/etc/hosts', '--ro-bind', str(CLI), '/arduino-cli',
                '--bind', str(root), '/arduino', '--chdir', '/tmp']
        if work:
            cmd += ['--ro-bind', str(work/'sketch'), '/sketch', '--bind', str(work/'build'), '/build']
        if port: cmd += ['--dev-bind', port, port]
        cmd += ['--', '/arduino-cli', '--no-color', *args]
        env = {'PATH': '/usr/bin:/bin', 'HOME': '/tmp', 'LANG': 'C.UTF-8', 'GOMAXPROCS': '2',
               'ARDUINO_DIRECTORIES_DATA': '/arduino/data', 'ARDUINO_DIRECTORIES_DOWNLOADS': '/arduino/downloads',
               'ARDUINO_DIRECTORIES_USER': '/arduino/user', 'ARDUINO_BUILD_CACHE_PATH': '/arduino/cache',
               'ARDUINO_BOARD_MANAGER_ADDITIONAL_URLS': ESP_INDEX,
               'ARDUINO_UPDATER_ENABLE_NOTIFICATION': 'false', 'ARDUINO_LIBRARY_ENABLE_UNSAFE_INSTALL': 'false'}
        return cmd, env

    @staticmethod
    def disk_size(root):
        total = 0
        for directory, _, files in os.walk(root, followlinks=False):
            for name in files:
                try: total += (Path(directory)/name).lstat().st_size
                except FileNotFoundError: pass
        return total

    async def execute(self, uid, args, token, *, job=None, network=False, work=None, port=None, timeout=120):
        cmd, env = self.command(uid, args, network=network, work=work, port=port)
        proc = await asyncio.create_subprocess_exec(*cmd, stdin=asyncio.subprocess.DEVNULL,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=env, start_new_session=True)
        chunks = {'out': bytearray(), 'err': bytearray()}
        async def read(stream, key):
            decoder = codecs.getincrementaldecoder('utf-8')('replace')
            while chunk := await stream.read(8192):
                chunks[key].extend(chunk)
                if len(chunks[key]) > 32*1024*1024: raise RuntimeError('Command output exceeded its limit.')
                if job: job['output'] = (job['output'] + decoder.decode(chunk))[-128*1024:]
        async def watch():
            tick = 0
            while True:
                await asyncio.sleep(1)
                user = self.live(token)
                if not user or user['id'] != uid or (port and user['role'] != 'admin'):
                    raise RuntimeError('The login or account permission ended. The operation was stopped.')
                if job: self.persist_job(uid, job)
                tick += 1
                if tick % 5 == 0:
                    size = await asyncio.to_thread(self.disk_size, self.root/str(uid))
                    if size > MAX_RUNTIME or shutil.disk_usage(self.root).free < 1024**3:
                        raise RuntimeError('Arduino storage limit reached or less than 1 GB free. Remove unused packages in the managers.')
        readers = [asyncio.create_task(read(proc.stdout, 'out')), asyncio.create_task(read(proc.stderr, 'err'))]
        watcher = asyncio.create_task(watch())
        async def finish():
            await asyncio.gather(*readers)
            await proc.wait()
        finished = asyncio.create_task(finish())
        try:
            async with asyncio.timeout(timeout):
                done, _ = await asyncio.wait((watcher, finished), return_when=asyncio.FIRST_COMPLETED)
                for task in done: await task
            if proc.returncode:
                message = bytes(chunks['err'] or chunks['out']).decode(errors='replace')[-6000:]
                raise RuntimeError(message or f'Arduino command failed (exit {proc.returncode}).')
            return bytes(chunks['out']).decode(errors='replace')
        finally:
            if proc.returncode is None:
                try: os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError: pass
            await proc.wait()
            for task in [*readers, watcher, finished]: task.cancel()
            await asyncio.gather(*readers, watcher, finished, return_exceptions=True)

    async def query(self, uid, args, token):
        if self.busy: raise web.HTTPConflict(text='Arduino tools are busy. Wait for the current job or stop it before refreshing the manager.')
        self.busy = True
        try:
            result = await self.execute(uid, ['--format', 'json', *args], token)
            return json.loads(result)
        except RuntimeError as exc: raise web.HTTPBadRequest(text=str(exc))
        finally: self.busy = False

    @staticmethod
    def public_job(job):
        return {k: job.get(k) for k in ('id', 'action', 'state', 'output', 'started', 'project')}

    def persist_job(self, uid, job):
        with self.app.db() as db:
            if db.execute('SELECT 1 FROM users WHERE id=?', (uid,)).fetchone():
                db.execute('INSERT INTO arduino_jobs VALUES (?,?) ON CONFLICT(user_id) DO UPDATE SET data=excluded.data',
                           (uid, json.dumps(self.public_job(job))))

    def job_view(self, uid):
        job = self.jobs.get(uid)
        if job: return self.public_job(job)
        with self.app.db() as db: row = db.execute('SELECT data FROM arduino_jobs WHERE user_id=?', (uid,)).fetchone()
        return json.loads(row['data']) if row else None

    async def run_job(self, uid, data, token, job):
        lock = None
        try:
            lock = (self.app.STATE/'files.lock').open('a')
            try: fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
            except BlockingIOError: raise RuntimeError('A backup is in progress. Try again shortly.')
            action = data['action']
            if action == 'clean_cache':
                root = self.runtime(uid)
                for name in ('downloads', 'cache'):
                    await asyncio.to_thread(shutil.rmtree, root/name)
                    (root/name).mkdir(mode=0o700)
                job['output'] += 'Download and compilation caches cleared. Installed packages and project files are preserved.\n'
            elif action == 'refresh_indexes':
                for command in (['core', 'update-index'], ['lib', 'update-index']):
                    await self.execute(uid, command, token, job=job, network=True, timeout=600)
            elif action in ('core_install', 'core_uninstall', 'lib_install', 'lib_uninstall'):
                kind, operation = action.split('_')
                package = data['package'] + (version(data.get('version')) if operation == 'install' else '')
                args = [kind, operation, package]
                if kind == 'core' and operation == 'install': args += ['--skip-post-install']
                await self.execute(uid, args, token, job=job, network=True, timeout=1800)
            else:
                project = data.get('_snapshot') or self.project(uid, data.get('project'))
                fqbn = valid_fqbn(project['fqbn'])
                with tempfile.TemporaryDirectory(prefix='arduino-job-', dir=self.app.STATE) as temp:
                    work = Path(temp); (work/'sketch'/project['name']).mkdir(parents=True); (work/'build').mkdir()
                    for name, content in project['files'].items(): (work/'sketch'/project['name']/name).write_text(content)
                    sketch = '/sketch/' + project['name']
                    job['output'] += 'Compiling saved project revision ' + str(project['revision']) + '…\n'
                    await self.execute(uid, ['compile', '--fqbn', fqbn, '--jobs', '1', '--warnings', 'default', '--build-path', '/build', sketch], token, job=job, work=work, timeout=1200)
                    if action == 'upload':
                        user = self.live(token)
                        if not user: raise RuntimeError('Log in again before uploading.')
                        self.usb(user)
                        port = self.port(data['port'])
                        if data.get('_port_identity') != self.port_identity(port):
                            raise RuntimeError('The USB device changed during compilation. Select the port again before uploading.')
                        job['output'] += '\nUploading. If connection fails, hold BOOT while connecting, then release it.\n'
                        await self.execute(uid, ['upload', '--fqbn', fqbn, '--port', port, '--input-dir', '/build', sketch], token, job=job, work=work, port=port, timeout=180)
            job['state'] = 'succeeded'; job['output'] += '\nCompleted successfully.\n'
        except asyncio.CancelledError:
            job['state'] = 'cancelled'; job['output'] += '\nStopped. If an upload was interrupted, upload again before using the board.\n'
        except (Exception,) as exc:
            job['state'] = 'failed'
            detail = exc.text if isinstance(exc, web.HTTPException) else str(exc)
            job['output'] += '\n' + (detail or 'The operation exceeded its time limit.') + '\n'
        finally:
            job['output'] = job['output'][-128*1024:]
            if lock: lock.close()
            self.busy = False
            self.persist_job(uid, job)

    async def start_job(self, uid, data, token, user):
        if self.busy: raise web.HTTPConflict(text='Another Arduino operation is running. Wait for it to finish.')
        action = data['action']
        if action.startswith('core_') and data.get('package') not in CORES:
            raise web.HTTPBadRequest(text='Choose ESP32 or Arduino AVR in Boards Manager.')
        if action.startswith('lib_'): library_name(data.get('package'))
        if action.endswith('_install'): version(data.get('version'))
        if action in ('compile', 'upload'):
            project = self.project(uid, data.get('project')); valid_fqbn(project['fqbn'])
            if data.get('revision') != project['revision']:
                raise web.HTTPConflict(text='The project changed. Save or reload it before building.')
            data = {**data, '_snapshot': project}
        if action == 'upload':
            self.usb(user); port = self.port(data.get('port'))
            data = {**data, '_port_identity': self.port_identity(port)}
            for owner, mon in list(self.monitors.items()):
                if mon['port'] == port:
                    if owner != uid: raise web.HTTPConflict(text='This USB port is in use by another user.')
                    await self.stop_monitor(uid)
        # Check installation before accepting a background job.
        self.command(uid, ['version'])
        self.busy = True
        job = {'id': secrets.token_hex(16), 'action': action, 'project': data.get('project'),
               'state': 'running', 'output': '', 'started': time.time()}
        self.persist_job(uid, job)
        self.jobs[uid] = job
        job['task'] = asyncio.create_task(self.run_job(uid, data, token, job))
        return {'job': self.job_view(uid)}

    async def stop_monitor(self, uid):
        mon = self.monitors.get(uid)
        if mon:
            mon['task'].cancel()
            await asyncio.gather(mon['task'], return_exceptions=True)
            self.monitors.pop(uid, None)

    async def monitor_loop(self, uid, mon, token):
        decoder = codecs.getincrementaldecoder('utf-8')('replace')
        try:
            while True:
                user = self.live(token)
                if not user or user['role'] != 'admin' or time.monotonic() - mon['seen'] > 60:
                    raise RuntimeError('Serial Monitor disconnected because its login or viewer ended.')
                chunk = mon['serial'].read(min(8192, mon['serial'].in_waiting or 1))
                mon['output'] = (mon['output'] + decoder.decode(chunk))[-65536:]
                await asyncio.sleep(.05)
        except asyncio.CancelledError: pass
        except Exception as exc:
            mon['error'] = str(exc)
        finally:
            mon['serial'].close(); mon['state'] = 'closed'

    async def handle(self, request):
        raw = bytearray()
        async for chunk in request.content.iter_chunked(65536):
            raw.extend(chunk)
            if len(raw) > MAX_SOURCE + 65536:
                raise web.HTTPRequestEntityTooLarge(max_size=MAX_SOURCE+65536, actual_size=len(raw))
        data = json.loads(raw)
        if not isinstance(data, dict): raise web.HTTPBadRequest(text='Enter an Arduino command.')
        user = self.app.require_current(request); uid = user['id']; token = request[self.app.TOKEN]
        action = data.get('action')
        if action == 'status':
            with self.app.db() as db:
                projects = [dict(r) for r in db.execute('SELECT id,name,revision,updated FROM arduino_projects WHERE user_id=? ORDER BY name', (uid,))]
            return web.json_response({'projects': projects, 'job': self.job_view(uid), 'busy': self.busy,
                                      'ready': CLI.is_file(), 'usb_allowed': user['role'] == 'admin', 'cores': CORES})
        if action == 'open': return web.json_response(self.project(uid, data.get('project')))
        if action in ('create', 'save'):
            if action == 'create':
                name = valid_name(data.get('name'))
                if 'files' not in data: data['files'] = {name+'.ino': TEMPLATES.get(data.get('template'), TEMPLATES['serial'])}
            name, source = self.source(data)
            encoded = json.dumps(source)
            with self.app.db() as db:
                if action == 'create':
                    if db.execute('SELECT COUNT(*) FROM arduino_projects WHERE user_id=?', (uid,)).fetchone()[0] >= 30:
                        raise web.HTTPConflict(text='Each account supports up to 30 Arduino projects.')
                    key = secrets.token_hex(16)
                    db.execute('INSERT INTO arduino_projects VALUES (?,?,?,?,1,?)', (key, uid, name, encoded, time.time()))
                    rev = 1
                else:
                    key = data.get('project'); self.project(uid, key)
                    result = db.execute('UPDATE arduino_projects SET name=?,data=?,revision=revision+1,updated=? WHERE id=? AND user_id=? AND revision=?',
                                        (name, encoded, time.time(), key, uid, data.get('revision')))
                    if not result.rowcount: raise web.HTTPConflict(text='This project changed in another window. Export your changes, then reopen the saved project.')
                    rev = data['revision'] + 1
            return web.json_response({'id': key, 'revision': rev})
        if action == 'delete':
            project = self.project(uid, data.get('project'))
            if data.get('revision') != project['revision']: raise web.HTTPConflict(text='The project changed. Reopen it before deleting.')
            job = self.jobs.get(uid)
            if job and job['state'] == 'running' and job['project'] == project['id']:
                raise web.HTTPConflict(text='Stop this project’s job before deleting it.')
            with self.app.db() as db: db.execute('DELETE FROM arduino_projects WHERE id=? AND user_id=?', (project['id'], uid))
            return web.json_response({'ok': True})
        if action == 'ports':
            self.usb(user)
            return web.json_response({'ports': self.ports()})
        if action == 'storage':
            used = await asyncio.to_thread(self.disk_size, self.root/str(uid))
            self.app.require_current(request)
            return web.json_response({'used': used, 'limit': MAX_RUNTIME})
        if action in ('clean_cache', 'refresh_indexes', 'core_install', 'core_uninstall', 'lib_install', 'lib_uninstall', 'compile', 'upload'):
            return web.json_response(await self.start_job(uid, data, token, user))
        if action == 'cancel':
            job = self.jobs.get(uid)
            if not job or job['id'] != data.get('job'): raise web.HTTPNotFound(text='Job not found in your account.')
            if job['state'] == 'running':
                job['task'].cancel(); await asyncio.gather(job['task'], return_exceptions=True)
            return web.json_response({'job': self.job_view(uid)})
        if action in ('boards', 'board_details', 'cores', 'libraries', 'library_search'):
            if action == 'boards': args = ['board', 'listall']
            elif action == 'board_details': args = ['board', 'details', '--fqbn', valid_fqbn(data.get('fqbn'))]
            elif action == 'cores': args = ['core', 'search', '--all']
            elif action == 'libraries': args = ['lib', 'list'] + (['--fqbn', valid_fqbn(data['fqbn'])] if data.get('fqbn') else [])
            else:
                term = data.get('query', '')
                if not isinstance(term, str) or not 2 <= len(term.strip()) <= 100 or term.startswith('-'):
                    raise web.HTTPBadRequest(text='Search using 2–100 characters.')
                args = ['lib', 'search', '--', term]
            result = await self.query(uid, args, token)
            self.app.require_current(request)
            if action == 'cores':
                result = {'platforms': [{'id': p['id'], 'name': CORES[p['id']],
                    'installed': p.get('installed_version', ''), 'latest': p.get('latest_version', ''),
                    'versions': [v for v,r in p.get('releases', {}).items() if r.get('compatible')]}
                    for p in result.get('platforms', []) if p['id'] in CORES]}
            elif action == 'boards':
                result = {'boards': [{'name': b['name'], 'fqbn': b['fqbn']} for b in result.get('boards', [])]}
            elif action == 'library_search':
                result = {'libraries': [{**{k:r[k] for k in ('name','latest') if k in r},
                    'releases': dict.fromkeys(r.get('releases', {}))} for r in result.get('libraries', [])[:250]]}
            return web.json_response({'result': result})
        if action == 'monitor_open':
            self.usb(user)
            if self.busy: raise web.HTTPConflict(text='Wait for the Arduino job before opening Serial Monitor.')
            port = self.port(data.get('port')); baud = data.get('baud', 115200)
            if baud not in BAUDS: raise web.HTTPBadRequest(text='Select a supported baud rate.')
            if any(m['port'] == port and other != uid and m['state'] == 'open' for other, m in self.monitors.items()):
                raise web.HTTPConflict(text='This USB port is in use by another user.')
            await self.stop_monitor(uid)
            import serial
            try:
                device = serial.Serial(port, baudrate=baud, timeout=0, write_timeout=.25, exclusive=True)
            except serial.SerialException as exc: raise web.HTTPConflict(text='Cannot open the USB port: '+str(exc))
            mon = {'port': port, 'serial': device, 'state': 'open', 'output': '', 'error': '', 'seen': time.monotonic()}
            self.monitors[uid] = mon; mon['task'] = asyncio.create_task(self.monitor_loop(uid, mon, token))
            return web.json_response({'ok': True})
        if action == 'monitor_close':
            await self.stop_monitor(uid); return web.json_response({'ok': True})
        if action in ('monitor_poll', 'monitor_send', 'monitor_clear'):
            self.usb(user); mon = self.monitors.get(uid)
            if not mon: return web.json_response({'state': 'closed', 'output': '', 'error': ''})
            mon['seen'] = time.monotonic()
            if action == 'monitor_send':
                content = data.get('text'); ending = data.get('ending', '\n')
                if not isinstance(content, str) or len(content.encode()) > 4096 or ending not in ('', '\n', '\r', '\r\n'):
                    raise web.HTTPBadRequest(text='Send up to 4 KB of text and choose a line ending.')
                if mon['state'] != 'open': raise web.HTTPConflict(text='Connect Serial Monitor first.')
                try: mon['serial'].write((content+ending).encode())
                except Exception as exc: raise web.HTTPConflict(text='Serial write failed: '+str(exc))
            if action == 'monitor_clear': mon['output'] = ''
            return web.json_response({k: mon[k] for k in ('state', 'output', 'error', 'port')})
        raise web.HTTPBadRequest(text='Unknown Arduino command.')

    async def lifecycle(self, app):
        async def cleanup_users():
            while True:
                await asyncio.sleep(2)
                with self.app.db() as db: uids = {str(r[0]) for r in db.execute('SELECT id FROM users')}
                for path in self.root.iterdir():
                    if path.is_dir() and path.name.isdecimal() and path.name not in uids:
                        uid = int(path.name)
                        job = self.jobs.get(uid)
                        if job and job['state'] == 'running':
                            job['task'].cancel(); await asyncio.gather(job['task'], return_exceptions=True)
                        await self.stop_monitor(uid)
                        self.jobs.pop(uid, None)
                        await asyncio.to_thread(shutil.rmtree, path, True)
        cleaner = asyncio.create_task(cleanup_users())
        yield
        self.closing = True; cleaner.cancel()
        tasks = [job['task'] for job in self.jobs.values()]
        for task in tasks: task.cancel()
        await asyncio.gather(cleaner, *tasks, return_exceptions=True)
        for uid in list(self.monitors): await self.stop_monitor(uid)


async def proxy(request):
    # The worker revalidates the same account cookie using the shared session DB.
    raw = bytearray()
    async for chunk in request.content.iter_chunked(65536):
        raw.extend(chunk)
        if len(raw) > MAX_SOURCE+65536: raise web.HTTPRequestEntityTooLarge(max_size=MAX_SOURCE+65536, actual_size=len(raw))
    async with ClientSession(connector=UnixConnector(path=SOCKET)) as client:
        async with client.post('http://localhost/api/development/arduino', data=raw,
                               headers={'Origin': request.headers.get('Origin', ''), 'Cookie': request.headers.get('Cookie', ''), 'Content-Type': 'application/json'}) as response:
            return web.Response(body=await response.read(), status=response.status, content_type='application/json')
