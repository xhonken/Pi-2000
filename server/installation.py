"""Fresh-install boundary for the independent Pi-2000 0.2 data line."""
import argparse
from contextlib import closing
import fcntl
import os
from pathlib import Path
import sqlite3

FORMAT = 'Pi-2000 0.2\n'
APPLICATION_ID = 0x50493230
BACKUP_FORMAT = 3
CONFIG = Path('/etc/pi2000web')
INSTALL_PATHS = tuple(map(Path, ('/opt/pi2000-admin', '/opt/pi2000-browser',
    '/srv/pi2000', '/var/lib/pi2000-admin', '/var/lib/pi2000-accounts',
    '/var/lib/pi2000web')))
MESSAGE = ('Pi-2000 0.2 requires a fresh installation. Earlier releases, including '
           'Alpha 5, 6 and 7, cannot be upgraded or restored into this version. '
           'Keep the previous installation and its backups on a separate system.')


def check_installation(config=CONFIG, paths=INSTALL_PATHS, require=False):
    marker = config / 'installation-format'
    if marker.exists():
        if marker.is_symlink() or marker.read_text() != FORMAT:
            raise RuntimeError(MESSAGE)
        return
    if require or config.exists() or any(path.exists() for path in paths):
        raise RuntimeError(MESSAGE)


def reserve_installation(config=CONFIG):
    """Record a checked fresh installation before its first configuration writes."""
    config.mkdir(parents=True, exist_ok=True)
    marker = config / 'installation-format'
    if marker.exists():
        check_installation(config, paths=())
        return
    with marker.open('x') as handle:
        handle.write(FORMAT)
        handle.flush()
        os.fsync(handle.fileno())
    marker.chmod(0o644)


def check_database(path):
    # Read-only: rejection must not modify an older database or create an empty one.
    with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)) as db:
        if db.execute('PRAGMA application_id').fetchone()[0] != APPLICATION_ID:
            raise RuntimeError(MESSAGE)


def prepare_state(state):
    """Serialize first creation across API/worker startup; never adopt an old DB."""
    state.mkdir(parents=True, exist_ok=True)
    with (state / 'initialize.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        database = state / 'admin.sqlite3'
        if database.exists():
            check_database(database)
        else:
            with closing(sqlite3.connect(database)) as db:
                db.execute(f'PRAGMA application_id={APPLICATION_ID}')
                db.commit()


def check_backup(manifest):
    if manifest.get('format') != BACKUP_FORMAT:
        raise RuntimeError(MESSAGE)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--require', action='store_true')
    args = parser.parse_args()
    try:
        check_installation(require=args.require)
    except (OSError, RuntimeError) as exc:
        parser.exit(1, str(exc) + '\n')
