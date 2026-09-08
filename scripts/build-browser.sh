#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
# Resolve/pin the full revision recorded with the tested bundle.
revision="$(cat "$project_dir/server/browser-source-revision.txt")"
build_dir="$project_dir/.browser-build"
source_dir="$build_dir/selkies-$revision"
mkdir -p "$build_dir/wheels"
if [[ ! -d "$source_dir/.git" ]]; then
  git init -q "$source_dir"
  git -C "$source_dir" fetch --depth=1 https://github.com/selkies-project/selkies.git "$revision"
  git -C "$source_dir" checkout --detach FETCH_HEAD
fi
[[ "$(git -C "$source_dir" rev-parse HEAD)" == "$revision" ]]
(cd "$source_dir" && sh scripts/ci/build-web.sh)
python3 -m venv "$build_dir/build-venv"
"$build_dir/build-venv/bin/pip" wheel --no-deps "$source_dir" -w "$build_dir/wheels"
"$build_dir/build-venv/bin/pip" download --only-binary=:all: --dest "$build_dir/wheels" --find-links "$build_dir/wheels" -r "$project_dir/server/browser-requirements.txt"
(cd "$build_dir" && sha256sum wheels/*.whl > SHA256SUMS)
uname -m > "$build_dir/architecture"
printf 'Browser packages built. Install with sudo %s/scripts/install-browser.sh\n' "$project_dir"
