#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
sudo -n install -d -m 755 /srv/win2k/assets/vendor /srv/win2k/dist
sudo -n install -m 644 "$project_dir/assets/system-icons.css" "$project_dir/assets/classic-icons.css" "$project_dir/assets/classic-ui.css" "$project_dir/assets/classic-ui.js" "$project_dir/assets/database.js" "$project_dir/assets/database-admin.js" "$project_dir/assets/database.css" "$project_dir/assets/development.js" "$project_dir/assets/git.js" "$project_dir/assets/development.css" "$project_dir/assets/taskmanager.js" "$project_dir/assets/taskmanager.css" "$project_dir/assets/desktop.css" "$project_dir/assets/files.js" "$project_dir/assets/editor.js" "$project_dir/assets/editor-sftp.js" "$project_dir/assets/tools.js" "$project_dir/assets/cad.js" "$project_dir/assets/sketch-geometry.js" "$project_dir/assets/calculator.js" "$project_dir/assets/icon-layout.js" "$project_dir/assets/apps.js" "$project_dir/assets/desktop.js" "$project_dir/assets/devices.js" "$project_dir/assets/devices.css" /srv/win2k/assets/
sudo -n install -m 644 "$project_dir/dist/win2k-ui.css" /srv/win2k/dist/

sudo -n install -m 644 "$project_dir"/assets/vendor/*.* "$project_dir"/assets/vendor/*-LICENSE /srv/win2k/assets/vendor/
sudo -n install -d -m 755 /srv/win2k/assets/vendor/ace
sudo -n install -m 644 "$project_dir"/assets/vendor/ace/* /srv/win2k/assets/vendor/ace/

sudo -n install -d -m 755 /srv/win2k/assets/vendor/pdf/standard_fonts
sudo -n install -m 644 "$project_dir"/assets/vendor/pdf/*.mjs "$project_dir/assets/vendor/pdf/LICENSE" /srv/win2k/assets/vendor/pdf/
sudo -n install -m 644 "$project_dir"/assets/vendor/pdf/standard_fonts/* /srv/win2k/assets/vendor/pdf/standard_fonts/

# Publish the entry page last. A content hash prevents old cached scripts from
# being combined with a newly installed desktop after an ordinary page reload.
page_file="$(mktemp)"
trap 'rm -f "$page_file"' EXIT
python3 - "$project_dir" "$page_file" <<'PYTHON'
import hashlib
from pathlib import Path
import re
import sys
root = Path(sys.argv[1])
def version(match):
    path = match.group(2).split('?')[0]
    asset = root / path
    digest = hashlib.sha256(asset.read_bytes()).hexdigest()[:16]
    return f'{match.group(1)}="{path}?v={digest}"'
page = re.sub(r'(src|href)="((?:assets|dist)/[^"#]+)"', version,
              (root / 'index.html').read_text())
Path(sys.argv[2]).write_text(page)
PYTHON
sudo -n install -m 644 "$page_file" /srv/win2k/index.html
