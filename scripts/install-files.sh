#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ $EUID -ne 0 ]]; then
  printf 'Run: sudo %s\n' "$0" >&2
  exit 1
fi
# Make a verified data backup before installing the additive database migration.
systemctl start win2k-backup.service
backup_dir="/var/backups/win2k-files-$(date +%Y%m%d-%H%M%S)"
install -d -m 700 "$backup_dir/code" "$backup_dir/site"
cp -a /opt/win2k-admin/*.py /opt/win2k-admin/requirements.txt "$backup_dir/code/"
cp -a /srv/win2k/. "$backup_dir/site/"
rollback() {
  result=$?
  if [[ $result -ne 0 ]]; then
    # Keep the backward-compatible file reader after an additive content-key
    # migration: an old reader could otherwise discard newly edited blobs.
    if [[ -f /opt/win2k-admin/file_store.py ]]; then
      cp -a /opt/win2k-admin/file_store.py "$backup_dir/file_store-forward.py"
    fi
    cp -a "$backup_dir/code/." /opt/win2k-admin/
    if [[ -f "$backup_dir/file_store-forward.py" ]]; then
      cp -a "$backup_dir/file_store-forward.py" /opt/win2k-admin/file_store.py
    fi
    cp -a "$backup_dir/site/." /srv/win2k/
    systemctl restart win2k-admin
    printf 'Publishing failed. Previous application files were restored. Backup: %s\n' "$backup_dir" >&2
  fi
}
trap rollback EXIT
# The root-owned backup service and the API coordinate through this shared lock.
touch /var/lib/win2k-admin/files.lock
chown win2k-admin:win2k-admin /var/lib/win2k-admin/files.lock
chmod 600 /var/lib/win2k-admin/files.lock
bash "$project_dir/scripts/publish-server.sh"
bash "$project_dir/scripts/publish-local.sh"
for attempt in {1..30}; do
  if /opt/win2k-admin/venv/bin/python - <<'PY'
import sqlite3
with sqlite3.connect('file:/var/lib/win2k-admin/admin.sqlite3?mode=ro',uri=True) as db:
    assert 'storage_quota' in {r[1] for r in db.execute('PRAGMA table_info(users)')}
    assert db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='files'").fetchone()
    assert 'content_key' in {r[1] for r in db.execute('PRAGMA table_info(files)')}
    for table in ('preferences','personal_docs'):
        assert db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone()
PY
  then break; fi
  if [[ $attempt -eq 30 ]]; then exit 1; fi
  sleep 0.2
done
systemctl is-active --quiet win2k-admin win2k-sessions caddy
# Verify what Caddy actually serves, including the new browser assets.
python3 - "$project_dir" <<'PYTHON'
import ssl
import sys
from pathlib import Path
from urllib.request import urlopen
root = Path(sys.argv[1])
context = ssl._create_unverified_context()  # Caddy uses a local CA on this LAN.
def fetch(path):
    with urlopen('https://192.168.1.250/' + path, context=context, timeout=15) as response:
        return response.read()
page = fetch('')
if page != Path('/srv/win2k/index.html').read_bytes():
    raise RuntimeError('HTTPS is not serving the installed entry page.')
if b'data-action="files"' not in page or b'assets/files.js?v=' not in page:
    raise RuntimeError('My Files is missing from the page served over HTTPS.')
if b'data-action="editor"' not in page or b'assets/icon-layout.js?v=' not in page:
    raise RuntimeError('The code editor or icon dragging is missing from the HTTPS page.')
for asset in ('assets/files.js', 'assets/classic-icons.css', 'assets/classic-ui.css', 'assets/classic-ui.js', 'assets/taskmanager.js', 'assets/taskmanager.css', 'assets/devices.js', 'assets/editor.js', 'assets/editor-sftp.js', 'assets/icon-layout.js', 'assets/vendor/ace/ace.js', 'assets/tools.js', 'assets/cad.js', 'assets/sketch-geometry.js', 'assets/calculator.js', 'assets/vendor/pdf/pdf.mjs', 'assets/vendor/pdf/pdf.worker.mjs'):
    if fetch(asset) != (root / asset).read_bytes():
        raise RuntimeError('HTTPS is serving the wrong version of ' + asset)
if Path('/opt/win2k-admin/file_store.py').read_bytes() != (root / 'server/file_store.py').read_bytes():
    raise RuntimeError('Wrong version of the file management server code.')
if b'data-action="calculator"' not in page or b'data-action="cad"' not in page or b'assets/tools.js?v=' not in page:
    raise RuntimeError('Personal tools are missing from the HTTPS page.')
print('Verified over HTTPS: file management, personal tools, code editor and dimension drawing are published.')
PYTHON
systemctl start win2k-backup.service
printf 'Pi-2000Web is installed. Reload the page. Existing terminal and browser sessions have been preserved.\n'
