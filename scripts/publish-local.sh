#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
stage_dir="$(mktemp -d)"
trap 'rm -rf -- "$stage_dir"' EXIT
python3 "$project_dir/server/deployment.py" stage web "$project_dir" "$stage_dir/web"
sudo -n python3 "$project_dir/server/deployment.py" activate web "$stage_dir/web" /srv/win2k
python3 "$project_dir/server/build_info.py" "$project_dir" > "$stage_dir/build-info.json"
sudo -n install -m 644 "$stage_dir/build-info.json" /opt/win2k-admin/build-info.json
