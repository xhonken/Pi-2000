#!/usr/bin/env python3
"""Fetch the pinned upstream CLI, verify SHA-256, and extract only executable/license."""
import argparse
import hashlib
import io
import os
from pathlib import Path
import platform
import tarfile
import urllib.request

VERSION = '1.5.1'
ARCHIVE = 'arduino-cli_1.5.1_Linux_ARM64.tar.gz'
SHA256 = '1e69e077479f300614d4551334e0a33f08ee40b04315d83b8e7e0e94f0d0ee62'
URL = 'https://github.com/arduino/arduino-cli/releases/download/v' + VERSION + '/' + ARCHIVE

def install(destination):
    if platform.machine() not in ('aarch64', 'arm64'):
        raise SystemExit('This pinned Arduino Workshop tool bundle supports Linux ARM64.')
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(URL, timeout=120) as response: data = response.read(64*1024*1024)
    if hashlib.sha256(data).hexdigest() != SHA256: raise SystemExit('Arduino CLI checksum verification failed.')
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
        for name in ('arduino-cli', 'LICENSE.txt'):
            member = archive.getmember(name)
            if not member.isfile(): raise SystemExit('Unexpected Arduino archive entry.')
            target = destination/name; temporary = destination/(name+'.part')
            temporary.write_bytes(archive.extractfile(member).read())
            temporary.chmod(0o755 if name == 'arduino-cli' else 0o644)
            os.replace(temporary, target)
    (destination/'VERSION').write_text(VERSION+'\n')
    print('Installed checksum-verified Arduino CLI '+VERSION+' in '+str(destination))

if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('destination');args=p.parse_args();install(args.destination)
