#!/usr/bin/env bash
# Uses the same verified backup and retention policy as the nightly timer.
set -euo pipefail
if [[ ${1:-} == --help ]]; then
  echo "Usage: sudo $0"
  echo 'Creates a local backup in /var/backups/pi2000 using the installed service.'
  exit 0
fi
if [[ $# -ne 0 || $EUID -ne 0 ]]; then
  echo "Usage: sudo $0" >&2
  exit 2
fi
systemctl start pi2000-backup.service
systemctl show pi2000-backup.service --property=Result --property=ExecMainStatus
printf 'Backup service completed. Archives: /var/backups/pi2000\n'
