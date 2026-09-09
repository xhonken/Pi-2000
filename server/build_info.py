"""Installed build identity, generated during publication rather than at request time."""
import hashlib
import json
from pathlib import Path
import subprocess


def generate(root):
    root = Path(root)
    files = subprocess.check_output(['git', 'ls-files', '-z'], cwd=root).decode().split('\0')
    digest = hashlib.sha256()
    for name in sorted(filter(None, files)):
        path = root / name
        if path.is_file():
            digest.update(name.encode() + b'\0' + path.read_bytes() + b'\0')
    revision = subprocess.check_output(['git', 'rev-parse', '--short=12', 'HEAD'], cwd=root).decode().strip()
    dirty = bool(subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=root))
    return {'version': (root / 'VERSION').read_text().strip(),
            'revision': revision, 'modified': dirty, 'build': digest.hexdigest()[:16]}


def installed():
    path = Path(__file__).with_name('build-info.json')
    if path.is_file():
        data = json.loads(path.read_text())
        return {key: data[key] for key in ('version', 'revision', 'modified', 'build')}
    version = Path(__file__).resolve().parents[1] / 'VERSION'
    return {'version': version.read_text().strip() if version.exists() else 'Unknown',
            'revision': 'Not published', 'modified': False, 'build': 'Development checkout'}


if __name__ == '__main__':
    import sys
    print(json.dumps(generate(Path(sys.argv[1]))))
