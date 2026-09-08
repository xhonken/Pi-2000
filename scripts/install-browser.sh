#!/usr/bin/env bash
# Compatibility alias: use the unified installer with browser = true.
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
exec bash "$project_dir/scripts/install.sh" --config /etc/pi2000web/config.toml "$@"
