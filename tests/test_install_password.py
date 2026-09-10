import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'server'))
import app


class InitialPasswordTests(unittest.TestCase):
    def test_chosen_password_is_hashed_and_existing_owner_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(app, 'STATE', Path(folder)):
            password = 'installer-fixture-password'
            app.initialize(initial_password=password)
            with app.db() as db:
                owner = dict(db.execute("SELECT * FROM users WHERE username='admin'").fetchone())
            self.assertEqual(owner['hash'], app.password_hash(password, owner['salt']))
            self.assertFalse((app.STATE / 'initial-password.txt').exists())
            self.assertNotIn(password.encode(), (app.STATE / 'admin.sqlite3').read_bytes())
            app.initialize(initial_password='different-fixture-password')
            with app.db() as db:
                self.assertEqual(owner, dict(db.execute("SELECT * FROM users WHERE username='admin'").fetchone()))

    def test_invalid_initial_password_does_not_create_state(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(app, 'STATE', Path(folder) / 'state'):
            with self.assertRaises(ValueError):
                app.initialize(initial_password='short')
            self.assertFalse(app.STATE.exists())


class DebconfPasswordTests(unittest.TestCase):
    def config(self, first, second, existing=False):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            if existing:
                (root / 'admin.sqlite3').touch()
            source = (ROOT / 'packaging/config').read_text()
            source = source.replace('/var/lib/win2k-admin/', folder + '/').replace('/var/lib/pi2000web/', folder + '/')
            script = root / 'config'
            script.write_text(source)
            env = {**os.environ, 'DEBIAN_HAS_FRONTEND': '1', 'DEBCONF_REDIR': '1', 'DEBIAN_FRONTEND': 'noninteractive'}
            proc = subprocess.Popen(['sh', '-c', 'exec 3>&1; exec sh "$1"', 'test', str(script)], env=env,
                                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            commands = []
            for line in proc.stdout:
                command = line.rstrip('\n')
                commands.append(command)
                answer = '0'
                if command == 'GET pi2000web/admin-password':
                    answer += ' ' + first
                elif command == 'GET pi2000web/admin-password-confirm':
                    answer += ' ' + second
                proc.stdin.write(answer + '\n')
                proc.stdin.flush()
            proc.stdin.close()
            error = proc.stderr.read()
            proc.stdout.close(); proc.stderr.close()
            return proc.wait(timeout=5), commands, error

    def test_confirmed_password_is_accepted(self):
        code, _, _ = self.config('fixture-pass-123', 'fixture-pass-123')
        self.assertEqual(code, 0)

    def test_missing_or_mismatched_password_fails_without_looping(self):
        for first, second in [('', ''), ('fixture-pass-123', 'fixture-pass-456')]:
            code, commands, _ = self.config(first, second)
            self.assertNotEqual(code, 0)
            self.assertIn('SET pi2000web/admin-password ', commands)
            self.assertIn('SET pi2000web/admin-password-confirm ', commands)

    def test_existing_installation_clears_answers_without_prompting(self):
        code, commands, _ = self.config('', '', existing=True)
        self.assertEqual(code, 0)
        self.assertFalse(any(c.startswith('INPUT ') for c in commands))


if __name__ == '__main__':
    unittest.main()
