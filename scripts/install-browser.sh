#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
build_dir="$project_dir/.browser-build"
if [[ $EUID -ne 0 ]]; then
  printf 'Installation requires system privileges. Run: sudo %s\n' "$0" >&2
  exit 1
fi
if [[ ! -f "$build_dir/SHA256SUMS" ]]; then
  printf 'First build the packages as a regular user: %s/scripts/build-browser.sh\n' "$project_dir" >&2
  exit 1
fi
[[ "$(cat "$build_dir/architecture")" == "$(uname -m)" ]]
(cd "$build_dir" && sha256sum --check --quiet SHA256SUMS)
backup_dir="/var/backups/win2k-browser-$(date +%Y%m%d-%H%M%S)"
install -d -m 700 "$backup_dir"
cp -a /etc/caddy/Caddyfile "$backup_dir/Caddyfile"
cp -a /etc/systemd/system/win2k-admin.service "$backup_dir/win2k-admin.service"
cp -a /opt/win2k-admin/app.py "$backup_dir/app.py"
cp -a /srv/win2k/index.html /srv/win2k/assets/devices.js /srv/win2k/assets/desktop.js /srv/win2k/assets/devices.css "$backup_dir/"
python3 - "$backup_dir" <<'PY'
from pathlib import Path
import sqlite3,sys
backup=Path(sys.argv[1])/'admin.sqlite3'
with sqlite3.connect('/var/lib/win2k-admin/admin.sqlite3') as source, sqlite3.connect(backup) as target:
    source.backup(target)
backup.chmod(0o600)
PY
deployed=0
rollback() {
  result=$?
  if [[ $result -ne 0 ]]; then
    cp -a "$backup_dir/Caddyfile" /etc/caddy/Caddyfile
    if [[ $deployed -eq 1 ]]; then
      cp -a "$backup_dir/app.py" /opt/win2k-admin/app.py
      cp -a "$backup_dir/win2k-admin.service" /etc/systemd/system/win2k-admin.service
      cp -a "$backup_dir/index.html" /srv/win2k/index.html
      cp -a "$backup_dir/devices.js" "$backup_dir/desktop.js" "$backup_dir/devices.css" /srv/win2k/assets/
      systemctl daemon-reload
      systemctl restart win2k-admin || true
      systemctl reload caddy || true
    fi
    printf 'Installation failed. Previous application files were preserved/restored. Backup: %s\n' "$backup_dir" >&2
  fi
}
trap rollback EXIT
apt-get update
apt-get install --yes --no-upgrade --no-install-recommends chromium xvfb pulseaudio pulseaudio-utils bubblewrap openbox xauth x11-xserver-utils dbus-x11 gnome-keyring python3-venv fonts-liberation
install -d -m 755 /opt/win2k-browser
python3 -m venv /opt/win2k-browser/venv
/opt/win2k-browser/venv/bin/pip install --no-index --find-links "$build_dir/wheels" -r "$project_dir/server/browser-requirements.txt"
install -m 644 "$project_dir/server/browser-requirements.txt" "$project_dir/server/browser-source-revision.txt" "$build_dir/SHA256SUMS" /opt/win2k-browser/
# Only this application's pages may embed the streaming view; external origins remain blocked.
python3 - <<'PY'
from pathlib import Path
path=Path('/etc/caddy/Caddyfile')
text=path.read_text()
if 'X-Frame-Options DENY' in text:
    path.write_text(text.replace('X-Frame-Options DENY','X-Frame-Options SAMEORIGIN'))
elif 'X-Frame-Options SAMEORIGIN' not in text:
    raise SystemExit('Unrecognised Caddy frame configuration. Review the configuration.')
PY
if ! caddy validate --config /etc/caddy/Caddyfile; then
  cp -a "$backup_dir/Caddyfile" /etc/caddy/Caddyfile
  exit 1
fi
printf 'Publishing the browser. The terminal service will restart and existing SSH terminals will end.\n'
deployed=1
bash "$project_dir/scripts/publish-server.sh"
bash "$project_dir/scripts/publish-local.sh"
systemctl reload caddy
systemctl is-active --quiet win2k-admin caddy
printf 'Browser installed. Reload with Ctrl+F5. Backup: %s\n' "$backup_dir"
