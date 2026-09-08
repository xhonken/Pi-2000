"""Deployment configuration and failure-boundary regressions (no host mutations)."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys
import subprocess

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('pi2000_setup', ROOT / 'scripts/setup.py')
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


class SetupTests(unittest.TestCase):
    def parse(self, url='https://192.0.2.25', tls='internal', bind='', browser=True):
        config = {'network': {'public_url': url, 'tls': tls, 'bind_address': bind}, 'features': {'browser': browser}}
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'config.toml'
            p.write_text(setup.config_text(config))
            return setup.read_config(p)

    def test_one_origin_drives_caddy_and_both_services(self):
        config = self.parse('https://PI.EXAMPLE.COM/', 'public', '192.0.2.25')
        rendered = setup.render(config)
        self.assertIn('https://pi.example.com {', rendered['Caddyfile'])
        self.assertNotIn('tls internal', rendered['Caddyfile'])
        self.assertIn('bind 192.0.2.25', rendered['Caddyfile'])
        self.assertEqual(rendered['runtime.env'], 'WIN2K_ORIGIN=https://pi.example.com\n')
        for name in ['win2k-admin.service', 'win2k-sessions.service']:
            unit = (ROOT / 'server' / name).read_text()
            self.assertIn('EnvironmentFile=/etc/pi2000web/runtime.env', unit)
            self.assertNotIn('Environment=WIN2K_ORIGIN=', unit)

    def test_internal_ipv6_and_config_roundtrip(self):
        config = self.parse('https://[2001:db8::2]', bind='::1', browser=False)
        self.assertIn('tls internal', setup.render(config)['Caddyfile'])
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'roundtrip.toml'
            p.write_text(setup.config_text(config))
            self.assertEqual(setup.read_config(p), config)

    def test_reject_invalid_or_injected_settings(self):
        for url in ['http://pi.local', 'https://x/y', 'https://x?y', 'https://x#y',
                    'https://user:secret@x', 'https://x:444', 'https://0.0.0.0',
                    'https://224.0.0.1', 'https://x\nheader bad', 'https://x;touch',
                    'https://$(id)', 'https://[::]', 'https://[fe80::1%eth0]']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                self.parse(url)
        for tls, host in [('public', 'https://pi.local'), ('public', 'https://192.0.2.25'),
                          ('off', 'https://pi.local')]:
            with self.assertRaises(ValueError):
                self.parse(host, tls)
        with self.assertRaises(ValueError):
            self.parse(bind='eth0; command')

    def test_unknown_keys_and_non_boolean_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'config.toml'
            example = (ROOT / 'config/config.example.toml').read_text()
            for text in [example.replace('browser = true', 'browser = "true"'), example + '\npassword = "secret"\n']:
                p.write_text(text)
                with self.assertRaises(ValueError):
                    setup.read_config(p)

    def test_existing_caddy_sites_are_never_silently_replaced(self):
        setup.check_caddy_ownership(':80 {\n root * /usr/share/caddy\n file_server\n}', False)
        config = self.parse()
        setup.check_caddy_ownership(setup.render(config)['Caddyfile'], False)
        with self.assertRaises(ValueError):
            setup.check_caddy_ownership(setup.render(config)['Caddyfile'] + '\nother.example { respond \"other\" }', False)
        with patch.object(setup, 'existing_origin', return_value='https://192.0.2.25'):
            for text in ['example.com { reverse_proxy localhost:3000 }',
                         'example.com { root * /srv/win2k file_server }',
                         ':80 { root * /usr/share/caddy file_server }\nother.example { respond "other" }']:
                for adopt in (True, False):
                    with self.assertRaises(ValueError):
                        setup.check_caddy_ownership(text, adopt)

    def test_preview_requires_no_privileges_or_external_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run([sys.executable, str(ROOT / 'scripts/setup.py'), 'install',
                                     '--config', str(ROOT / 'config/config.example.toml'),
                                     '--render-dir', tmp], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((Path(tmp) / 'Caddyfile').exists())
            self.assertTrue((Path(tmp) / 'win2k-sessions.service').exists())
            self.assertIn('Browser build: enabled', result.stdout)

    def test_actual_caddy_adapter_accepts_lan_domain_and_ipv6(self):
        import shutil
        if not shutil.which('caddy'):
            self.skipTest('Caddy not installed')
        for config in [self.parse(), self.parse('https://desktop.example.com', 'public'),
                       self.parse('https://[2001:db8::2]', bind='::1')]:
            with tempfile.TemporaryDirectory() as tmp:
                p = Path(tmp) / 'Caddyfile'
                p.write_text(setup.render(config)['Caddyfile'])
                result = subprocess.run(['caddy', 'adapt', '--config', str(p), '--adapter', 'caddyfile'], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                import json
                adapted = json.loads(result.stdout)
                self.assertEqual(adapted['admin']['listen'], 'unix//var/lib/caddy/win2k-admin/control.sock')
                self.assertIn('127.0.0.1:8765', result.stdout)

    def test_untrusted_config_not_executed(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'evil.toml'
            target = Path(tmp) / 'executed'
            p.write_text((ROOT / 'config/config.example.toml').read_text().replace('https://pi2000.local', 'https://$(touch ' + str(target) + ')'))
            with self.assertRaises(ValueError):
                setup.read_config(p)
            self.assertFalse(target.exists())


if __name__ == '__main__':
    unittest.main()
