#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
[ -f /etc/pi2000web/runtime.env ] || { echo "Run scripts/install.sh with your configuration first." >&2; exit 1; }
sudo -n install -m 644 "$project_dir"/server/*.py "$project_dir/server/requirements.txt" /opt/win2k-admin/
sudo -n install -d -m 755 /opt/win2k-admin/browser-config/policies/managed
sudo -n install -m 644 "$project_dir/server/browser-config/policies/managed/adblock.json" /opt/win2k-admin/browser-config/policies/managed/
sudo -n /opt/win2k-admin/venv/bin/pip install -r /opt/win2k-admin/requirements.txt
sudo -n /opt/win2k-admin/venv/bin/pip check
sudo -n install -m 644 "$project_dir/server/win2k-admin.service" "$project_dir/server/win2k-sessions.service" "$project_dir/server/win2k-backup.service" "$project_dir/server/win2k-backup.timer" /etc/systemd/system/
sudo -n install -d -m 700 /var/backups/win2k
sudo -n systemctl daemon-reload
# Deliberately start rather than restart: live jobs belong to this worker.
sudo -n systemctl enable --now win2k-sessions
sudo -n systemctl is-active --quiet win2k-sessions
build_file="$(mktemp)"
trap 'rm -f "$build_file"' EXIT
python3 "$project_dir/server/build_info.py" "$project_dir" > "$build_file"
sudo -n install -m 644 "$build_file" /opt/win2k-admin/build-info.json
sudo -n systemctl restart win2k-admin
sudo -n systemctl enable --now win2k-backup.timer
