# Pi-2000 system names

New installations use `pi2000-admin.service`, `pi2000-sessions.service`,
`pi2000-backup.service` and `pi2000-backup.timer`. The shared service account and
group are `pi2000-admin`. The accounts, Arduino, phpMyAdmin and private terminal
units already use `pi2000-*` names.

The API, session worker, account broker and Arduino worker set their Linux task
names to `pi2000-api`, `pi2000-sessions`, `pi2000-accounts` and `pi2000-arduino`.
Third-party processes such as Chromium, MariaDB, Caddy and SSH retain their names.

Canonical installation paths are `/opt/pi2000-admin`, `/opt/pi2000-browser`,
`/var/lib/pi2000-admin`, `/srv/pi2000`, `/var/backups/pi2000` and
`/var/lib/caddy/pi2000-admin`. The session socket is
`/run/pi2000-sessions/worker.sock`.

## Existing source installations

**This is a maintenance operation, not a live unit alias.** Renaming the service
account and session unit requires stopping their processes. Live SSH terminals,
browser sessions and Arduino operations cannot be transferred to another unit.
Save work first. Workspace checkpoints can restore supported windows/drafts,
but cannot preserve running OS processes through this migration.

From the reviewed source checkout:

```sh
sudo bash scripts/migrate-system.sh --plan
sudo bash scripts/migrate-system.sh --apply
```

The plan is read-only and reports paths, numeric service identity and worker
counts. Apply obtains worker admission leases and refuses busy workers before
stopping services. It checks them again after staging and backup. Only after the
operator explicitly accepts interruption of current jobs may they use:

```sh
sudo bash scripts/migrate-system.sh --apply --allow-session-stop
```

The migrator:

- rejects conflicting accounts/directories, modified deployment inventories,
  custom legacy unit overrides and unrecognised Caddy configurations;
- creates a verified data backup using the currently installed backup service;
- snapshots code, web files and affected configuration in a private directory
  under `/var/backups/pi2000-namespace`;
- moves directories and renames the service account/group while retaining their
  numeric UID/GID, data, ownership and permissions;
- installs the reviewed source and new units, restores prior enablement/start
  state and runs the full installation doctor;
- automatically restores old code, paths, account names and unit configuration
  if a caught activation/start/verification error occurs. Rollback also requires
  restarting services; it cannot resurrect terminated OS jobs.

Root-owned links from the old directories to their canonical replacements remain
for existing virtualenv shebangs and operator references. They do not create a
second data store or a second service identity. Do not delete these compatibility
links without rebuilding the dependent environments. Protocol keys, cookies,
`WIN2K_*` configuration and UI namespaces also remain compatible.

The migration record and recovery snapshot are root-only. A power failure cannot
be caught by the rollback handler: retain the snapshot and verified data archive,
inspect `migration.json`, and repair the recorded moves/configuration before
restarting services. Do not run a fresh installation over a partially migrated
data directory. The [recovery guide](RECOVERY.md) covers verified data restoration.

After a successful migration:

```sh
sudo bash scripts/doctor.sh
sudo bash scripts/workers.sh status
systemctl status pi2000-admin pi2000-sessions pi2000-backup.timer
```

A repeat plan detects the canonical installation. Source installers refuse to
create a second installation beside an unmigrated legacy state directory.

## Debian package boundary

The new namespace is used for future fresh package builds. The published Alpha 6
package is unchanged. This source migration refuses installations marked as
managed by dpkg; an old-package upgrade needs a separately validated package
migration. The new pre-install guard rejects an unmigrated legacy installation
instead of creating a second account/state directory.
