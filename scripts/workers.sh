#!/usr/bin/env bash
set -euo pipefail
exec /opt/win2k-admin/venv/bin/python /opt/win2k-admin/maintenance.py "$@"
