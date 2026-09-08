#!/usr/bin/env bash
# Run from this checkout; configuration is TOML data, never sourced as shell code.
set -euo pipefail
if [[ ${1:-} == --help ]]; then
  echo "Usage: sudo $0 CONFIG.toml"
  exit 0
fi
if [[ $# -ne 1 || $EUID -ne 0 ]]; then
  echo "Usage: sudo $0 CONFIG.toml" >&2
  exit 2
fi
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
"$project_dir/scripts/install.sh" --config "$1" --check
exec "$project_dir/scripts/install.sh" --config "$1"
