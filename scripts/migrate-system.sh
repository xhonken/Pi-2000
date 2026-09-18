#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
python=/opt/pi2000-admin/venv/bin/python
[ -x "$python" ] || python=/opt/win2k-admin/venv/bin/python
exec "$python" "$project_dir/server/system_migration.py" --source "$project_dir" "$@"
