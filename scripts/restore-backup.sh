#!/usr/bin/env bash
set -euo pipefail
# Recovery now requires a reviewed plan; never stop jobs implicitly.
exec /opt/pi2000-admin/venv/bin/python /opt/pi2000-admin/recovery.py "$@"
