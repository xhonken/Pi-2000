"""Private persistent browser processes, with no publicly reachable debug ports."""
import asyncio
import os
from pathlib import Path
import shutil
import signal
import tempfile
import time
import sys
from resource_limits import BrowserLimits


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
            self.sessions[user_id] = entry
            for _ in range(300):
                if entry['socket'].exists():
                    return entry
                if process.returncode is not None:
                    await self._stop(user_id)
                    raise BrowserUnavailable('The browser could not start. Check the browser service log.')
                await asyncio.sleep(0.1)
            await self._stop(user_id)
            raise BrowserUnavailable('The browser took too long to start.')

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
            await self._stop(user_id)
            if remove:
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
