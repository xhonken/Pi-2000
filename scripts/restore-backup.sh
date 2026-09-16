#!/usr/bin/env bash
set -euo pipefail
# Recovery now requires a reviewed plan; never stop jobs implicitly.
exec /opt/win2k-admin/venv/bin/python /opt/win2k-admin/recovery.py "$@"
