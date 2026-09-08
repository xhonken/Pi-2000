#!/usr/bin/env bash
# Compatibility alias. New installations use install.sh; updates use update.sh.
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
exec bash "$project_dir/scripts/update.sh" "$@"
