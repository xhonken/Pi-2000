"""Fail closed on browser engines older than the reviewed security baseline.

This is a minimum known-fix floor, not a claim that later builds have no CVEs.
Review the floor with browser updates; do not add a web-configurable bypass.
"""
from functools import lru_cache
from pathlib import Path
import re
import subprocess

MINIMUM = (153, 0, 8010, 52)
BINARY = Path('/usr/lib/chromium/chromium')


def supported(value):
    match = re.search(r'\b(\d+)\.(\d+)\.(\d+)\.(\d+)\b', value)
    return bool(match and tuple(map(int, match.groups())) >= MINIMUM)


@lru_cache(maxsize=2)
def _inspect(signature):
    result = subprocess.run([str(BINARY), '--version'], stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            text=True, timeout=5, check=True,
                            env={'PATH':'/usr/bin:/bin','LANG':'C'})
    return supported(result.stdout)


def check():
    try:
        value = BINARY.stat()
        ok = _inspect((value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns))
    except (OSError, subprocess.SubprocessError):
        ok = False
    if not ok:
        required = '.'.join(map(str, MINIMUM))
        raise RuntimeError('Browser is paused for a security update. The Pi operator must install Chromium '
                           + required + ' or newer, then reopen Browser. Your saved profile is unchanged.')
