#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ $EUID -ne 0 ]]; then
  printf 'Run: sudo %s\n' "$0" >&2
  exit 1
fi
backup_dir="/var/backups/win2k-foundation-$(date +%Y%m%d-%H%M%S)"
install -d -m 700 "$backup_dir/code" "$backup_dir/site"
cp -a /opt/win2k-admin/*.py /opt/win2k-admin/requirements.txt "$backup_dir/code/"
cp -a /srv/win2k/. "$backup_dir/site/"
cp -a /etc/systemd/system/win2k-admin.service "$backup_dir/"
rollback() {
  result=$?
  if [[ $result -ne 0 ]]; then
    systemctl stop win2k-backup.timer win2k-backup.service win2k-admin win2k-sessions || true
    systemctl disable win2k-backup.timer win2k-sessions || true
    cp -a "$backup_dir/code/." /opt/win2k-admin/
    cp -a "$backup_dir/site/." /srv/win2k/
    cp -a "$backup_dir/win2k-admin.service" /etc/systemd/system/
    systemctl daemon-reload
    systemctl start win2k-admin
    printf 'Deployment failed; the previous version was restored. Backup: %s\n' "$backup_dir" >&2
  fi
}
trap rollback EXIT
printf 'Switching to a separate session service. Existing sessions will end once.\n'
systemctl stop win2k-admin
"$project_dir/.venv/bin/python" "$project_dir/server/backup.py" create --socket '' --code /opt/win2k-admin
bash "$project_dir/scripts/publish-server.sh"
bash "$project_dir/scripts/publish-local.sh"
/opt/win2k-admin/venv/bin/python - <<'PY'
import asyncio
import sys
sys.path.insert(0,'/opt/win2k-admin')
from session_proxy import control
async def verify():
    for _ in range(30):
        try:
            status=await control('/run/win2k-sessions/worker.sock','status')
            assert status['session_worker']
            return
        except (OSError, AssertionError):
            await asyncio.sleep(.2)
    raise RuntimeError('The session service is not responding')
asyncio.run(verify())
PY
systemctl is-active --quiet win2k-admin win2k-sessions win2k-backup.timer
printf 'Deployment complete. Previous application version: %s\n' "$backup_dir"
