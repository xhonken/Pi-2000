"""Fresh 0.2 setup, repeat startup and rejection without touching old user data."""
from contextlib import closing
from pathlib import Path
import hashlib
import io
import json
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'server'))
import app
import installation as install
from backup import restore, checksum


class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_new_install_and_retry_use_explicit_data_line(self):
        config = self.root / 'config'
        install.check_installation(config, ())
        install.reserve_installation(config)
        install.check_installation(config, (), require=True)
        install.reserve_installation(config)
        self.assertEqual((config / 'installation-format').read_text(), install.FORMAT)
        with patch.object(app, 'STATE', self.root / 'state'):
            app.initialize(initial_password='disposable-fixture-password')
            with app.db() as db:
                before = dict(db.execute('SELECT * FROM users').fetchone())
                db.execute("INSERT INTO desktops VALUES(?,?)", (before['id'], '{"private":"fixture"}'))
            app.initialize(initial_password='another-fixture-password')
            with app.db() as db:
                self.assertEqual(dict(db.execute('SELECT * FROM users').fetchone()), before)
                self.assertEqual(db.execute('SELECT data FROM desktops').fetchone()[0], '{"private":"fixture"}')
            install.check_database(app.STATE / 'admin.sqlite3')

    def test_existing_configuration_or_state_is_never_adopted(self):
        config = self.root / 'config'
        state = self.root / 'state'
        state.mkdir()
        for paths in ((state,), ()):
            if not paths:
                config.mkdir()
                (config / 'runtime.env').write_text('fixture configuration\n')
            with self.assertRaisesRegex(RuntimeError, 'fresh installation'):
                install.check_installation(config, paths)
        self.assertEqual((config / 'runtime.env').read_text(), 'fixture configuration\n')
        (config / 'installation-format').write_text('unknown format\n')
        with self.assertRaisesRegex(RuntimeError, 'fresh installation'):
            install.check_installation(config, ())

    def test_old_database_refused_before_schema_or_credentials_change(self):
        state = self.root / 'state'
        state.mkdir()
        database = state / 'admin.sqlite3'
        with closing(sqlite3.connect(database)) as db:
            db.executescript("CREATE TABLE users(id, username); INSERT INTO users VALUES(1,'fixture-user');")
        before = hashlib.sha256(database.read_bytes()).digest()
        with patch.object(app, 'STATE', state):
            with self.assertRaisesRegex(RuntimeError, 'fresh installation'):
                app.initialize(initial_password='disposable-fixture-password')
        self.assertEqual(hashlib.sha256(database.read_bytes()).digest(), before)
        self.assertFalse((state / 'initial-password.txt').exists())

    def test_old_backup_refused_before_extraction(self):
        for version in (1, 2, 999):
            archive = self.root / f'fixture-{version}.tar'
            with tarfile.open(archive, 'w') as tar:
                for name, data in [('manifest.json', json.dumps({'format': version}).encode()),
                                   ('state/private.txt', b'fixture data')]:
                    member = tarfile.TarInfo(name)
                    member.size = len(data)
                    tar.addfile(member, io.BytesIO(data))
            archive.with_suffix('.tar.sha256').write_text(checksum(archive))
            destination = self.root / f'restore-{version}'
            with self.assertRaisesRegex(RuntimeError, 'fresh installation'):
                restore(archive, destination)
            self.assertEqual(list(destination.iterdir()), [])

    def test_kernel_process_names_in_child_only(self):
        code = "from process_identity import identify; from pathlib import Path; identify('pi2000-api'); print(Path('/proc/self/comm').read_text().strip())"
        result = subprocess.check_output([sys.executable, '-c', code], cwd=ROOT/'server', text=True)
        self.assertEqual(result.strip(), 'pi2000-api')

    def test_package_preinst_in_isolated_filesystem(self):
        if not shutil.which('bwrap'):
            self.skipTest('Bubblewrap is required for the package pre-install fixture')
        host = self.root / 'host'
        for name in ('etc', 'var', 'opt', 'srv'):
            (host / name).mkdir(parents=True)
        command = ['bwrap', '--unshare-all', '--die-with-parent', '--ro-bind', '/usr', '/usr',
                   '--symlink', 'usr/bin', '/bin', '--symlink', 'usr/lib', '/lib',
                   '--ro-bind-try', '/lib64', '/lib64', '--proc', '/proc', '--dev', '/dev', '--tmpfs', '/run']
        for name in ('etc', 'var', 'opt', 'srv'):
            command += ['--bind', str(host / name), '/' + name]
        command += ['--ro-bind', str(ROOT / 'packaging/preinst'), '/preinst', '--', '/bin/sh', '/preinst']
        def run(action, old=''):
            return subprocess.run(command + [action, old], capture_output=True, text=True)
        self.assertEqual(run('install').returncode, 0)
        for version in ('0.1.0~alpha.5-1', '0.1.0~alpha.6-1', '0.1.0~alpha.7-1'):
            for action in ('install', 'upgrade'):
                result = run(action, version)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('fresh installation', result.stderr)
        config = host / 'etc/pi2000web'
        config.mkdir()
        (config / 'config.toml').write_text('private fixture\n')
        self.assertNotEqual(run('install').returncode, 0)
        self.assertEqual((config / 'config.toml').read_text(), 'private fixture\n')
        install.reserve_installation(config)
        (host / 'opt/pi2000-admin').mkdir()
        self.assertNotEqual(run('install').returncode, 0)  # Source-managed host.
        managed = host / 'var/lib/pi2000web'
        managed.mkdir(parents=True)
        (managed / 'package-managed').write_text('1\n')
        self.assertEqual(run('upgrade', '0.2.0~alpha.8-1').returncode, 0)
        self.assertNotEqual(run('upgrade', '0.1.0~alpha.7-1').returncode, 0)
