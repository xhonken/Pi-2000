#!/usr/bin/env bash
# Restoring replaces user data and ends all running sessions.
set -euo pipefail
if [[ ${1:-} == --help ]]; then
  echo "Usage: sudo $0 --end-running-sessions /absolute/path/to/backup.tar"
  echo 'Replaces user data, ends jobs and requires all users to log in again.'
  echo 'Use with the compatible application version described in docs/INSTALLATION.md.'
  exit 0
fi
if [[ $# -ne 2 || ${1:-} != --end-running-sessions || $EUID -ne 0 ]]; then
  echo "Usage: sudo $0 --end-running-sessions /absolute/path/to/backup.tar" >&2
  exit 2
fi
if [[ $2 != /* || ! -f $2 ]]; then
  echo 'Supply an existing backup file using an absolute path.' >&2
  exit 2
fi
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
exec "$project_dir/scripts/restore-backup.sh" "$2"
