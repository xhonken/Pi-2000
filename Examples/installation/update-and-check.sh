#!/usr/bin/env bash
# Update from the current checkout, then verify the installed application.
set -euo pipefail
if [[ ${1:-} == --help ]]; then
  echo "Usage: sudo $0 [CONFIG.toml]"
  echo 'Default configuration: /etc/pi2000web/config.toml. Fetch code updates separately.'
  exit 0
fi
if [[ $# -gt 1 || $EUID -ne 0 ]]; then
  echo "Usage: sudo $0 [CONFIG.toml]" >&2
  exit 2
fi
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
config_path="${1:-/etc/pi2000web/config.toml}"
"$project_dir/scripts/update.sh" --config "$config_path"
exec "$project_dir/scripts/doctor.sh" --config "$config_path"
