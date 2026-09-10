"""Private persistent browser processes, with no publicly reachable debug ports."""
import asyncio
import logging
import os
from pathlib import Path
import shutil
import signal
import tempfile
import time
import sys
import uuid
from urllib.parse import urlsplit
from resource_limits import BrowserLimits, available_memory, BROWSER_START_RESERVE, BROWSER_MEMORY_MAX, BROWSER_WARNING


def valid_browser_url(url):
    if not isinstance(url, str) or not url or len(url) > 4096 or any(ord(c) < 33 or ord(c) == 127 for c in url):
        return False
    try:
        parsed = urlsplit(url)
        return parsed.scheme in ('http', 'https') and bool(parsed.hostname) and parsed.port != 0
    except ValueError:
        return False


class BrowserUnavailable(Exception):
    pass


class BrowserRuntime:
    def __init__(self, state, venv=None, deps=None, limit=3):
        self.root = Path(state) / 'browsers'
        self.venv = Path(venv or os.environ.get('WIN2K_BROWSER_VENV', '/opt/win2k-browser/venv'))
        self.deps = deps or os.environ.get('WIN2K_BROWSER_DEPS')
        self.limit = limit
        self.sessions = {}
        self.lock = asyncio.Lock()
        self.resources = BrowserLimits()
        self.frozen = False
        self.last_stops = {}

    def command(self, profile, runtime):
        args = ['/usr/bin/bwrap', '--unshare-user', '--unshare-pid', '--unshare-ipc', '--unshare-uts',
                '--die-with-parent', '--new-session', '--clearenv', '--ro-bind', '/usr', '/usr',
                '--ro-bind', '/etc', '/etc', '--symlink', 'usr/lib', '/lib', '--symlink', 'usr/bin', '/bin',
                '--symlink', 'usr/sbin', '/sbin', '--proc', '/proc', '--dev', '/dev', '--tmpfs', '/dev/shm',
                '--tmpfs', '/tmp', '--dir', '/run', '--dir', '/home',
                '--bind', str(profile), '/home/browser', '--bind', str(runtime), '/run/browser',
                '--ro-bind', str(self.venv), '/opt/browser-venv',
                '--ro-bind', str(Path(__file__).with_name('browser_session.py')), '/opt/browser_session.py',
                '--setenv', 'HOME', '/home/browser', '--setenv', 'USER', 'browser',
                '--setenv', 'BROWSER_DISPLAY', ':' + str(100 + int(profile.name)), '--setenv', 'PATH', '/usr/bin:/bin', '--setenv', 'LANG', 'C.UTF-8',
                '--setenv', 'PYTHONDONTWRITEBYTECODE', '1', '--chdir', '/home/browser']
        policy = Path(__file__).with_name('browser-config')
        if policy.is_dir():
            args += ['--ro-bind', str(policy), '/etc/chromium']
        if Path('/lib64').exists():
            args += ['--ro-bind', '/lib64', '/lib64']
        if self.deps:
            arch = os.uname().machine + '-linux-gnu'
            args += ['--ro-bind', self.deps, '/opt/browser-deps', '--setenv', 'LD_LIBRARY_PATH',
                     f'/opt/browser-deps/usr/lib/{arch}/pulseaudio:/opt/browser-deps/usr/lib/{arch}:' + ':'.join('/opt/browser-deps/' + str(p.relative_to(self.deps)) for p in Path(self.deps).glob('usr/lib/pulse-*/modules'))]
        args += ['/usr/bin/dbus-run-session', '--', '/opt/browser-venv/bin/python', '/opt/browser_session.py']
        return args

    async def start(self, user_id):
        async with self.lock:
            existing = self.sessions.get(user_id)
            if existing and existing['process'].returncode is None:
                return existing
            if existing:
                await self._stop(user_id)
            if not (self.venv / 'bin/python').exists():
                raise BrowserUnavailable('The browser service is not installed yet.')
            if sum(s['process'].returncode is None for s in self.sessions.values()) >= self.limit:
                raise BrowserUnavailable('Three browser sessions are already running. End a session to free up a slot.')
            if shutil.disk_usage(self.root.parent).free < 512 * 1024**2:
                raise BrowserUnavailable('Server storage is almost full. Free some space before starting the browser.')
            if self.resources.root is not None and 'memory' not in self.resources.controllers:
                raise BrowserUnavailable('Browser requires the memory controller. Enable it and reboot the Pi before starting Browser.')
            available = available_memory()
            if available is not None and available < BROWSER_START_RESERVE:
                raise BrowserUnavailable('Not enough available server memory to start Browser safely. Close unused browser sessions or server applications and try again. Your saved browser profile is unchanged.')
            self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
            profile = self.root / str(int(user_id))
            profile.mkdir(exist_ok=True, mode=0o700)
            runtime = Path(tempfile.mkdtemp(prefix='win2k-browser-'))
            log = open(profile / 'session.log', 'wb')
            try:
                command = self.command(profile, runtime)
                group = self.resources.create(user_id)
                if group:
                    command = [sys.executable, str(Path(__file__).with_name('browser_launcher.py')), str(group), *command]
                process = await asyncio.create_subprocess_exec(*command,
                    stdout=log, stderr=asyncio.subprocess.STDOUT, start_new_session=True)
            except OSError as exc:
                shutil.rmtree(runtime, ignore_errors=True)
                raise BrowserUnavailable('The browser system components could not start.') from exc
            finally:
                log.close()
            entry = {'process': process, 'runtime': runtime, 'socket': runtime / 'stream.sock', 'last_seen': time.monotonic(), 'clients': 0}
            entry['oom_baseline'] = self.resources.usage(user_id).get('oom_kills', 0)
            self.sessions[user_id] = entry
            # Cold imports and stream-client extraction on a Pi 4 SD card can
            # exceed 30 seconds. Bound elapsed time without relaxing resources.
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                if entry['socket'].exists() and (runtime / 'url-ready').exists():
                    self.last_stops.pop(user_id, None)
                    return entry
                if process.returncode is not None:
                    await self._stop(user_id)
                    raise BrowserUnavailable('The browser could not start. Check the browser service log.')
                await asyncio.sleep(0.1)
            await self._stop(user_id)
            raise BrowserUnavailable('The browser took too long to start.')

    def status(self, user_id):
        entry = self.sessions.get(user_id)
        if entry and entry['process'].returncode is None:
            usage = self.resources.usage(user_id)
            warning = 'Browser is approaching its memory limit. Close unused tabs.' if usage.get('memory_bytes', 0) >= BROWSER_WARNING else None
            return {'state': 'running', 'reason': None, 'warning': warning, **usage}
        if entry:
            usage = self.resources.usage(user_id)
            reason = 'memory_limit' if usage.get('oom_kills', 0) > entry.get('oom_baseline', 0) else 'crashed'
        else:
            reason = self.last_stops.get(user_id, 'not_started')
        return {'state': 'stopped', 'reason': reason, 'warning': None}

    async def monitor(self):
        # Serialize with start/stop so an old watchdog observation cannot kill a new session.
        async with self.lock:
            for uid, entry in list(self.sessions.items()):
                usage = self.resources.usage(uid)
                reason = None
                if entry['process'].returncode is not None:
                    reason = 'memory_limit' if usage.get('oom_kills', 0) > entry.get('oom_baseline', 0) else 'crashed'
                elif usage.get('memory_bytes', 0) > BROWSER_MEMORY_MAX:
                    reason = 'memory_limit'
                elif shutil.disk_usage(self.root.parent).free < 512 * 1024**2:
                    reason = 'disk_full'
                elif not entry.get('clients', 0) and time.monotonic() - entry.get('last_seen', time.monotonic()) > 86400:
                    reason = 'idle_timeout'
                if reason:
                    logging.warning('Browser stopped: user %s, reason %s', uid, reason)
                    self.last_stops[uid] = reason
                    await self._stop(uid)

    async def open_url(self, user_id, url):
        if not valid_browser_url(url):
            raise BrowserUnavailable('Enter a valid HTTP or HTTPS address.')
        async with self.lock:
            entry = self.sessions.get(user_id)
            if not entry or entry['process'].returncode is not None:
                raise BrowserUnavailable('The browser session ended. Reopen Browser.')
            runtime = entry['runtime']
            if not (runtime / 'url-ready').exists():
                raise BrowserUnavailable('End your Browser session and reopen it to enable shortcuts after this update.')
            if len(list(runtime.glob('open-*.url'))) >= 32:
                raise BrowserUnavailable('Too many pending browser shortcuts. Try again shortly.')
            temporary = runtime / ('pending-' + uuid.uuid4().hex)
            temporary.write_text(url)
            temporary.chmod(0o600)
            temporary.rename(runtime / ('open-' + uuid.uuid4().hex + '.url'))

    async def _stop(self, user_id):
        entry = self.sessions.pop(user_id, None)
        if not entry:
            return
        process = entry['process']
        if process.returncode is None:
            # TERM reaches the supervisor inside the PID namespace as well.
            (entry['runtime'] / 'stop').touch()
            try:
                await asyncio.wait_for(process.wait(), 8)
            except asyncio.TimeoutError:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                await process.wait()
        self.resources.remove(user_id)
        shutil.rmtree(entry['runtime'], ignore_errors=True)

    async def stop(self, user_id, remove=False):
        async with self.lock:
            self.last_stops[user_id] = 'ended'
            await self._stop(user_id)
            if remove:
                self.last_stops.pop(user_id, None)
                await asyncio.to_thread(shutil.rmtree, self.root / str(int(user_id)), True)

    async def freeze(self):
        await self.lock.acquire()
        try:
            self.resources.freeze(True)
            self.frozen = True
        except BaseException:
            self.resources.freeze(False)
            self.lock.release()
            raise

    async def thaw(self):
        self.resources.freeze(False)
        if self.frozen:
            self.frozen = False
            self.lock.release()

    async def shutdown(self):
        await self.thaw()
        async with self.lock:
            await asyncio.gather(*(self._stop(user_id) for user_id in list(self.sessions)))
