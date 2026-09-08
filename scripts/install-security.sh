#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ $EUID -ne 0 ]]; then
  printf 'Run: sudo %s\n' "$0" >&2
  exit 1
fi
caddy validate --config "$project_dir/server/Caddyfile" --adapter caddyfile
bash "$project_dir/scripts/install-files.sh"
backup_dir="$(mktemp -d /var/backups/win2k-security-XXXXXXXX)"
cp -a /etc/caddy/Caddyfile "$backup_dir/Caddyfile"
install -d -o caddy -g caddy -m 700 /var/lib/caddy/win2k-admin
admin_address=127.0.0.1:2019
if [[ -S /var/lib/caddy/win2k-admin/control.sock ]]; then
  admin_address=unix//var/lib/caddy/win2k-admin/control.sock
fi
if ! caddy reload --config "$project_dir/server/Caddyfile" --adapter caddyfile --address "$admin_address"; then
  printf 'Caddy rejected the change; the previous configuration is preserved.\n' >&2
  exit 1
fi
install -o root -g root -m 644 "$project_dir/server/Caddyfile" /etc/caddy/Caddyfile
systemctl reload caddy
python3 - <<'PY'
import socket
from urllib.request import urlopen
import ssl
with socket.socket() as client:
    client.settimeout(2)
    assert client.connect_ex(('127.0.0.1',2019))!=0, 'The Caddy administration port is still open'
with urlopen('https://192.168.1.250/',context=ssl._create_unverified_context(),timeout=15) as response:
    assert response.status==200
    assert b'Content-Security-Policy' in response.read()
print('Verified: HTTPS works, desktop script protection is active and TCP port 2019 is closed.')
PY
if runuser -u win2k-admin -- test -r /var/lib/caddy/win2k-admin/control.sock; then
  printf 'Error: the application account can read the Caddy administration socket.\n' >&2
  exit 1
fi
printf 'Security update installed. Previous Caddy configuration: %s\n' "$backup_dir/Caddyfile"
