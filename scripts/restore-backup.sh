#!/usr/bin/env bash
set -euo pipefail
if [[ $EUID -ne 0 || $# -ne 1 ]]; then
  printf 'Usage: sudo %s /var/backups/win2k/win2k-DATUM.tar\n' "$0" >&2
  exit 1
fi
staging="$(mktemp -d /var/backups/win2k/restore-XXXXXXXX)"
saved_state=''
replaced=0
cleanup() {
  result=$?
  if [[ $result -ne 0 && $replaced -eq 1 ]]; then
    systemctl stop win2k-admin win2k-sessions || true
    if [[ -d /var/lib/win2k-admin ]]; then
      mv /var/lib/win2k-admin "${saved_state}-failed"
    fi
    mv "$saved_state" /var/lib/win2k-admin
    systemctl start win2k-sessions win2k-admin win2k-backup.timer
    printf 'Restore failed; previous data has been put back.\n' >&2
  fi
  rm -rf -- "$staging"
}
trap cleanup EXIT
/opt/win2k-admin/venv/bin/python /opt/win2k-admin/backup.py restore --archive "$1" --destination "$staging"
# Preserve the entire current state before replacing anything.
systemctl stop win2k-backup.timer win2k-backup.service
systemctl stop win2k-admin win2k-sessions
saved_state="/var/lib/win2k-before-restore-$(date +%Y%m%d-%H%M%S)"
mv /var/lib/win2k-admin "$saved_state"
replaced=1
install -d -o win2k-admin -g win2k-admin -m 700 /var/lib/win2k-admin
cp -a "$staging/state/." /var/lib/win2k-admin/
chown -R win2k-admin:win2k-admin /var/lib/win2k-admin
systemctl start win2k-sessions win2k-admin
systemctl start win2k-backup.timer
replaced=0
printf 'Restored. Previous data is in %s. All users must log in again.\n' "$saved_state"
