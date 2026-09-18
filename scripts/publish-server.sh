#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
[ -f /etc/pi2000web/runtime.env ] || { echo "Run scripts/install.sh with your configuration first." >&2; exit 1; }
python3 "$project_dir/server/installation.py" --require
stage_dir="$(mktemp -d)"
trap 'rm -rf -- "$stage_dir"' EXIT
python3 "$project_dir/server/deployment.py" stage server "$project_dir" "$stage_dir/server"
sudo -n python3 "$project_dir/server/deployment.py" activate server "$stage_dir/server" /opt/pi2000-admin
sudo -n /opt/pi2000-admin/venv/bin/pip install -r /opt/pi2000-admin/requirements.txt
sudo -n /opt/pi2000-admin/venv/bin/pip check
sudo -n install -m 644 "$project_dir/server/pi2000-admin.service" "$project_dir/server/pi2000-sessions.service" "$project_dir/server/pi2000-backup.service" "$project_dir/server/pi2000-backup.timer" /etc/systemd/system/
sudo -n install -m 644 "$project_dir/server/pi2000-accounts.service" "$project_dir/server/pi2000-terminal.service" /etc/systemd/system/
sudo -n runuser -u pi2000-admin -- /opt/pi2000-admin/venv/bin/python -c "import sys;sys.path.insert(0,'/opt/pi2000-admin');import app;app.initialize()"
sudo -n /opt/pi2000-admin/venv/bin/python /opt/pi2000-admin/account_install.py
sudo -n systemctl restart pi2000-accounts
sudo -n install -d -m 700 /var/backups/pi2000
sudo -n systemctl daemon-reload
# Deliberately start rather than restart: live jobs belong to this worker.
sudo -n systemctl enable --now pi2000-sessions
sudo -n systemctl is-active --quiet pi2000-sessions
sudo -n python3 "$project_dir/scripts/arduino-tools.py" /opt/pi2000-arduino
sudo -n install -m 644 "$project_dir/server/pi2000-arduino.service" /etc/systemd/system/
sudo -n systemctl daemon-reload
# Keep a running Arduino worker intact; upgrades are scheduled after its jobs finish.
sudo -n systemctl enable --now pi2000-arduino
sudo -n systemctl restart pi2000-admin
sudo -n systemctl enable --now pi2000-backup.timer
