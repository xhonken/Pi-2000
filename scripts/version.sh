#!/usr/bin/env bash
# Report this source checkout, not the state of an independently deployed server.
set -euo pipefail
if [[ ${1:-} == --help ]]; then
  echo "Usage: $0"
  echo 'Reports the source version and Git revision when available.'
  exit 0
fi
if [[ $# -ne 0 ]]; then
  echo "Usage: $0" >&2
  exit 2
fi
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
printf 'Pi-2000Web %s (source)\n' "$(cat "$project_dir/VERSION")"
if [[ -e $project_dir/.git ]] && command -v git >/dev/null 2>&1; then
  git -C "$project_dir" log -1 --format='Commit: %H'
  git -C "$project_dir" describe --tags --always --dirty
  if [[ -n $(git -C "$project_dir" status --porcelain) ]]; then
    echo 'Local changes are present (including untracked files).'
  fi
fi
