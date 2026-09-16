"""Shared, data-only file inventory for staging, installation and code backup."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

EXCLUDED = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 'AGENTS.md',
            'PROJECT-HISTORY.local.md', 'PROJECT-HANDOVER.local.md', 'initial-password.txt'}
PRIVATE_SUFFIXES = ('.local.md', '.key', '.pem', '.sqlite', '.sqlite3', '.db', '.pyc', '.log', '.part')


def safe_path(name):
    path = Path(name)
    return (bool(name) and not path.is_absolute() and '..' not in path.parts
            and all(not p.startswith('.') and p not in EXCLUDED for p in path.parts)
            and not name.endswith(PRIVATE_SUFFIXES))


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def selected(root, component):
    root = Path(root)
    spec = json.loads((root / 'deployment.json').read_text())
    if spec['format'] != 1 or component not in ('server', 'web'):
        raise ValueError('Unknown deployment format/component')
    result = {}
    for pattern in spec[component]:
        if not safe_path(pattern):
            raise ValueError('Unsafe deployment pattern')
        for path in root.glob(pattern):
            name = path.relative_to(root).as_posix()
            if not safe_path(name):
                continue
            if path.is_symlink() or any(p.is_symlink() for p in path.parents if p != root and root in p.parents):
                raise ValueError('Deployment cannot follow symlinks: ' + name)
            if path.is_file():
                target = name.removeprefix('server/') if component == 'server' else name
                result[target] = path
    if not result:
        raise ValueError('Empty deployment component: ' + component)
    return dict(sorted(result.items()))


def stage(root, target, component, info):
    target = Path(target)
    target.mkdir(parents=True, exist_ok=True)
    if any(target.iterdir()):
        raise ValueError('Staging directory must be empty')
    for name, source in selected(root, component).items():
        dest = target / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
        dest.chmod(0o644)
    if component == 'web':
        def hashed(match):
            name = match[2].split('?')[0]
            return f'{match[1]}="{name}?v={digest(target / name)[:16]}"'
        page = target / 'index.html'
        page.write_text(re.sub(r'(src|href)="((?:assets|dist)/[^"#]+)"', hashed, page.read_text()))
    else:
        (target / 'build-info.json').write_text(json.dumps(info) + '\n')
    inventory = {'format': 1, 'component': component, 'build': info,
                 'files': {p.relative_to(target).as_posix(): digest(p)
                           for p in sorted(target.rglob('*')) if p.is_file() and p.name != 'build-info.json'}}
    (target / ('deployment-' + component + '.json')).write_text(json.dumps(inventory, indent=2) + '\n')
    verify(target, component)
    return inventory


def inventory(root, component):
    data = json.loads((Path(root) / ('deployment-' + component + '.json')).read_text())
    if data.get('format') != 1 or data.get('component') != component or not data.get('files'):
        raise ValueError('Invalid installed deployment manifest')
    for name in data['files']:
        if not safe_path(name):
            raise ValueError('Unsafe installed manifest path')
    return data


def verify(root, component):
    root = Path(root)
    data = inventory(root, component)
    for name, expected in data['files'].items():
        path = root / name
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()) or digest(path) != expected:
            raise ValueError('Deployment checksum mismatch: ' + name)
    return data


def activate(staging, target, component):
    """Verify the complete stage before replacing files; preserve unrelated data."""
    staging, target = Path(staging), Path(target)
    data = verify(staging, component)
    if target.is_symlink():
        raise ValueError('Deployment destination is a symlink')
    target.mkdir(parents=True, exist_ok=True)
    old_file = target / ('deployment-' + component + '.json')
    old = inventory(target, component)['files'] if old_file.exists() else {}
    names = [*data['files']]
    if component == 'server': names.append('build-info.json')
    # Entry page and inventory become visible after all versioned assets.
    if 'index.html' in names: names.remove('index.html'); names.append('index.html')
    names.append(old_file.name)
    # Preflight every target before writing anything.
    for name in set(names) | set(old):
        path = target / name
        if path.is_symlink() or not path.resolve().is_relative_to(target.resolve()):
            raise ValueError('Unsafe installed target: ' + name)
    for name in names:
        dest = target / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=dest.parent, delete=False) as stream:
            temp = Path(stream.name)
            try:
                stream.write((staging / name).read_bytes())
                stream.flush()
                os.fsync(stream.fileno())
                temp.chmod(0o644)
                temp.replace(dest)
            finally:
                temp.unlink(missing_ok=True)
    for name in set(old) - set(data['files']):
        (target / name).unlink(missing_ok=True)
    verify(target, component)


def backup_files(root, component):
    root = Path(root)
    manifest = root / ('deployment-' + component + '.json')
    if manifest.exists():
        data = verify(root, component)
        return [root / name for name in sorted(data['files'])] + [manifest] + ([root / 'build-info.json'] if component == 'server' and (root / 'build-info.json').exists() else [])
    # Compatibility for installations made before deployment manifests existed.
    files = []
    for path in sorted(root.rglob('*')):
        name = path.relative_to(root).as_posix()
        if not safe_path(name) or path.is_symlink() or not path.is_file():
            continue
        if not path.resolve().is_relative_to(root.resolve()):
            raise ValueError('Backup source escapes component')
        if component == 'web' or path.suffix == '.py' or (len(path.relative_to(root).parts) == 1 and path.suffix in ('.txt','.service','.timer')) or name.startswith(('phpmyadmin/','browser-config/')) or name == 'build-info.json':
            files.append(path)
    return files


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['stage', 'activate', 'verify'])
    parser.add_argument('component', choices=['server', 'web'])
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path, nargs='?')
    args = parser.parse_args()
    if args.action == 'stage':
        from build_info import generate
        stage(args.source, args.destination, args.component, generate(args.source))
    elif args.action == 'activate':
        activate(args.source, args.destination, args.component)
    else:
        verify(args.source, args.component)


if __name__ == '__main__':
    main()
