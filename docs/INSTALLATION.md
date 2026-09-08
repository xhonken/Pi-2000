# Pi-2000Web Deployment and Database

## Installation status

The current deployment runs on Raspberry Pi 5, using 64-bit Debian 13 / Raspberry Pi OS, Python 3, systemd and Caddy. The scripts in this checkout primarily update that existing installation. They assume the service account, directories and API virtual environment already exist.

A generic, clean-machine installer and an independently tested fresh-install walkthrough are still required before the public Alpha release. Do not treat the maintenance commands below as a complete fresh installation recipe. In particular, the checked-in Caddyfile and systemd unit currently contain the existing deployment address `192.168.1.250`; another installation must configure its own HTTPS origin consistently.

## Installed layout

| Path / service | Purpose |
| --- | --- |
| `/srv/win2k` | Published static desktop files |
| `/opt/win2k-admin` | Installed Python application |
| `/opt/win2k-admin/venv` | API Python virtual environment |
| `/opt/win2k-browser/venv` | Browser streaming Python environment |
| `/var/lib/win2k-admin` | Private application state, owned by `win2k-admin` |
| `/var/lib/win2k-admin/admin.sqlite3` | SQLite database |
| `/var/lib/win2k-admin/initial-password.txt` | Initial owner password until changed |
| `/var/backups/win2k` | Verified local backup archives |
| `win2k-admin.service` | HTTP API on loopback port 8765 |
| `win2k-sessions.service` | Persistent SSH and browser worker |
| `/run/win2k-sessions/worker.sock` | Private API-to-worker transport |
| `win2k-backup.timer` | Scheduled backups |
| `/etc/caddy/Caddyfile` | HTTPS reverse proxy and static hosting |
| `/var/lib/caddy/win2k-admin/control.sock` | Private Caddy administration socket |

These legacy names remain intentional compatibility identifiers after the product rename to **Pi-2000Web**. Do not rename installed directories or database tables to match the branding. The source checkout may have a different directory name; scripts determine its root relative to their own path.

## Database initialisation

No MySQL/PostgreSQL instance, database password or manual SQL import is required. The application creates the SQLite schema and the initial owner at startup. `server/app.py:initialize`, `FileStore.initialize`, `PersonalStore.initialize` and `SessionStore` define the schema and supported legacy migrations.

| Table | Contents |
| --- | --- |
| `users` | Accounts, salted password hashes, roles, activation/session version and storage quotas |
| `items` | Per-account SSH profiles and connection folders |
| `hostkeys` | SSH host keys, scoped by account, host and port |
| `workspaces` | Per-account window layout and restoration metadata |
| `desktops` | Per-account shortcuts, icon positions and background |
| `files` | File/folder metadata, ownership, parent location, state, size and content key |
| `preferences` | Per-account text size, favourites, recent items and default viewer |
| `personal_docs` | Notes, dimension drawings and editor recovery drafts with versions and sizes |
| `login_sessions` | Digests of session tokens and expiring session data |

The database uses foreign-key checks for account-owned records. Protected-owner triggers prevent deleting or disabling/demoting the initial owner. File bytes live in private blob storage alongside the database, not as a public static directory. Back up the database **and** its related file storage together. Browser profiles are separate private directories and must also be included when preserving browser state.

Use a new empty private state directory for a fresh deployment. Never distribute the real `admin.sqlite3`, initial password, browser cookies, profiles or backups with source code. Do not manually create account rows or edit password hashes; use the application.

## Existing-installation updates

Run from the source checkout after reviewing and testing changes:

```sh
sudo ./scripts/install-files.sh
```

This creates a verified backup and previous-code snapshot, publishes the API and static assets, validates the database/services and checks the actual HTTPS page. The entry page is published last with content hashes so an ordinary reload fetches the new scripts. The frontend service restarts; the persistent session worker is started if needed, not restarted.

For a static-only update:

```sh
sudo ./scripts/publish-local.sh
```

Backend changes to worker-owned behaviour take effect when the worker next restarts. Restarting `win2k-sessions` ends running terminal and browser sessions; schedule that separately when no jobs need to continue.

Browser build/install scripts are separate:

```sh
./scripts/build-browser.sh
sudo ./scripts/install-browser.sh
```

The build step runs as a regular user. Browser installation changes system components and can restart session services; read its output and plan around running jobs. The older `install-foundation.sh` is a migration for installations predating the separate worker, not a fresh installer.

## Configuration

`WIN2K_STATE` selects private state, `WIN2K_ORIGIN` is the exact public HTTPS origin, `WIN2K_PORT` defaults to 8765, and `WIN2K_WORKER_SOCKET` connects the frontend to the worker. The worker uses `WIN2K_SESSION_WORKER=1` and a private Unix listening socket. See the checked-in systemd units for the complete environment and hardening settings.

Caddy serves only `/srv/win2k` and proxies `/api/*` to loopback. The current local deployment uses Caddy internal TLS. Client devices must trust that installation certificate authority for a normal trusted HTTPS connection. Keep the Caddy administration socket private to the `caddy` account; do not revert it to an unrestricted local TCP administration endpoint.

## Health checks and recovery

```sh
systemctl status win2k-admin win2k-sessions caddy
systemctl status win2k-backup.timer
sudo journalctl -u win2k-admin -n 100 --no-pager
sudo journalctl -u win2k-sessions -n 100 --no-pager
```

The application System Status window shows service health and, for the owner, backup status. Task Manager displays current server usage.

To restore an existing backup, inspect the archive name and run:

```sh
sudo ./scripts/restore-backup.sh /var/backups/win2k/ARCHIVE.tar
```

Restore validates a staged copy, stops services, replaces state and starts services again. Existing jobs end and users must log in again. Keep off-device backups as well: local backups on the same disk cannot protect against loss of that disk.
