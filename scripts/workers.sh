#!/usr/bin/env bash
set -euo pipefail
exec /opt/pi2000-admin/venv/bin/python /opt/pi2000-admin/maintenance.py "$@"
