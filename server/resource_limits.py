"""Per-browser cgroup v2 limits within the session service's delegated subtree."""
import os
import time
from pathlib import Path

BROWSER_MEMORY_MAX = max(512, min(1536, int(os.environ.get('WIN2K_BROWSER_MEMORY_MIB', '1536')))) * 1024**2
# Small hosts need headroom for cold Chromium/Selkies imports and extraction.
BROWSER_MEMORY_HIGH = BROWSER_MEMORY_MAX - 128*1024**2 if BROWSER_MEMORY_MAX <= 1024**3 else BROWSER_MEMORY_MAX * 2 // 3
BROWSER_SWAP_MAX = 128*1024**2 if BROWSER_MEMORY_MAX <= 1024**3 else 256*1024**2
BROWSER_WARNING = min(1200 * 1024**2, BROWSER_MEMORY_MAX * 4 // 5)
BROWSER_START_RESERVE = BROWSER_MEMORY_MAX + max(128, int(os.environ.get('WIN2K_BROWSER_RESERVE_MIB', '512'))) * 1024**2


def available_memory(path=Path('/proc/meminfo')):
    # MemAvailable includes reclaimable cache; MemFree alone rejects healthy hosts.
    try:
        for line in path.read_text().splitlines():
            if line.startswith('MemAvailable:'):
                return int(line.split()[1]) * 1024
    except (OSError, ValueError):
        pass
    return None


class BrowserLimits:
    def __init__(self):
        self.root = None
        if os.environ.get('WIN2K_CGROUP_LIMITS') != '1':
            return
        path = next(line.split('::',1)[1] for line in Path('/proc/self/cgroup').read_text().splitlines() if line.startswith('0::'))
        self.root = Path('/sys/fs/cgroup') / path.lstrip('/')
        control = self.root / 'supervisor'
        control.mkdir(exist_ok=True)
        (control / 'cgroup.procs').write_text(str(os.getpid()))
        self.controllers = set((self.root / 'cgroup.controllers').read_text().split())
        (self.root / 'cgroup.subtree_control').write_text(' '.join('+' + c for c in ('memory','pids','cpu') if c in self.controllers))

    def create(self, user_id):
        if self.root is None:
            return None
        group = self.root / f'browser-{int(user_id)}'
        group.mkdir(exist_ok=True)
        if 'memory' in self.controllers:
            (group / 'memory.high').write_text(str(BROWSER_MEMORY_HIGH))
            (group / 'memory.max').write_text(str(BROWSER_MEMORY_MAX))
            (group / 'memory.swap.max').write_text(str(BROWSER_SWAP_MAX))
            (group / 'memory.oom.group').write_text('1')
        (group / 'pids.max').write_text('256')
        (group / 'cpu.max').write_text('150000 100000')
        return group

    def usage(self, user_id):
        if self.root is None:
            return {}
        group = self.root / f'browser-{int(user_id)}'
        try:
            if (group/'memory.current').exists():
                memory = int((group/'memory.current').read_text())
            else:
                memory = 0
                for pid in (group/'cgroup.procs').read_text().split():
                    try:
                        fields = Path('/proc',pid,'smaps_rollup').read_text().splitlines()
                        memory += sum(int(line.split()[1])*1024 for line in fields if line.startswith('Pss:'))
                    except (FileNotFoundError, ProcessLookupError, PermissionError): pass
            events = {}
            if (group/'memory.events').exists():
                events = dict(line.split() for line in (group/'memory.events').read_text().splitlines())
            return {'oom_kills': int(events.get('oom_kill', 0)), 'memory_bytes': memory, 'memory_hard_limit': 'memory' in self.controllers,
                    'processes': int((group/'pids.current').read_text())}
        except FileNotFoundError:
            return {}

    def remove(self, user_id):
        if self.root is None: return
        group = self.root / f'browser-{int(user_id)}'
        try:
            (group/'cgroup.kill').write_text('1')
            group.rmdir()
        except OSError:
            pass  # A draining cgroup is reused on the next start.

    def freeze(self, frozen):
        if self.root is None: return
        for group in self.root.glob('browser-*'):
            (group/'cgroup.freeze').write_text('1' if frozen else '0')
            if frozen:
                for _ in range(100):
                    if 'frozen 1' in (group/'cgroup.events').read_text(): break
                    time.sleep(.01)
                else: raise RuntimeError('Browser freeze timed out')
