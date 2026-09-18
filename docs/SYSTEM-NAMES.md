# Pi-2000 names and the 0.2 installation boundary

Alpha 8 (`0.2.0-alpha.8`) starts an independent data line. **It requires a fresh
installation. Alpha 5, 6 and 7 cannot be upgraded, even if their Linux services
already have Pi-2000 names.** Keep the earlier installation and its backups on a
separate system. Published releases and Git history are unchanged.

There is no automatic conversion of old accounts, settings, sessions or system
backups. Export ordinary documents through the earlier version and copy only the
files you need into your new account. Do not copy application SQLite files,
private state directories, browser profiles, environment files or system accounts.
Keep the old installation available to read material that needs the old software.

## Consistent identifiers

- Services and service account: `pi2000-admin`, `pi2000-sessions`, `pi2000-backup`,
  `pi2000-accounts`, `pi2000-arduino`, `pi2000-terminal`, `pi2000-phpmyadmin`.
- Linux task names: `pi2000-api`, `pi2000-sessions`, `pi2000-accounts`, `pi2000-arduino`.
- Environment variables: `PI2000_*`; session cookie: `__Host-pi2000`.
- JavaScript globals: `Pi2000*`; CSS, custom events and browser keys: `pi2000-*`.
- Main stylesheet: `dist/pi2000-ui.css`.
- Code: `/opt/pi2000-admin`, `/opt/pi2000-browser`; web files: `/srv/pi2000`.
- State: `/var/lib/pi2000-admin`; backups: `/var/backups/pi2000`.
- Worker socket: `/run/pi2000-sessions/worker.sock`.

Third-party processes such as Chromium, MariaDB, Caddy and SSH retain their own
names. The Debian package and management command are `pi2000web`.

## Enforced boundary

The Debian pre-install script rejects earlier package versions before unpacking
and refuses existing unmarked installations, including retained data after removal.
The source installer and publish scripts enforce the same data-line marker,
`/etc/pi2000web/installation-format`. It is retained on purge with user data so
compatible reinstallation remains possible. Do not create it manually to bypass
checks: it is an installation identity, not a migration mechanism.

The API and worker require the 0.2 SQLite application identity before initializing
schema or credentials. An earlier database is rejected without modifying it.
System backups use format 3; earlier formats are rejected before extracting their
contents. The [recovery guide](RECOVERY.md) applies only within this data line.

Later compatible 0.2 updates still require verified backups and normal maintenance
procedures. Preserved workers need a planned restart after live jobs finish.
The removed source migrator and historical provenance remain in the Alpha 7 Git
snapshot for operators who still maintain that release; they are not Alpha 8 tools.
