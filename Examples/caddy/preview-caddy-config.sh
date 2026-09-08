#!/usr/bin/env bash
# Render deployment files without installing or reloading services.
set -euo pipefail
if [[ ${1:-} == --help ]]; then
  echo "Usage: $0 CONFIG.toml NEW_OUTPUT_DIRECTORY"
  exit 0
fi
if [[ $# -ne 2 ]]; then
  echo "Usage: $0 CONFIG.toml NEW_OUTPUT_DIRECTORY" >&2
  exit 2
fi
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
# Require a new directory so an earlier preview is not silently overwritten.
mkdir -m 700 -- "$2"
"$project_dir/scripts/install.sh" --config "$1" --render-dir "$2"
if command -v caddy >/dev/null 2>&1; then
  caddy adapt --adapter caddyfile --config "$2/Caddyfile" --pretty > "$2/caddy.json"
fi
printf 'Review the generated files in %s. No services were changed.\n' "$2"
