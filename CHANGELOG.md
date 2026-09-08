# Changelog

User-visible changes are recorded here for each numbered release. Development between releases is listed under Unreleased. See [versioning and releases](docs/VERSIONING.md) for installation and maintainer instructions.

## Unreleased

No changes recorded yet.

## 0.1.0-alpha.2 — 2026-09-08

### Fixed

- URL shortcuts and Run open web addresses in the account's private Browser instead of a client browser tab.
- Shortcuts support a context menu, Delete key, drag to Recycle Bin, restoration and persistent deletion state.
- Browser URL requests accept only bounded HTTP/HTTPS URLs and are queued separately for each account without shell execution.

### Update note

This release changes the persistent session worker and browser supervisor. Schedule `sudo ./scripts/update.sh --restart-sessions` after finishing live jobs. This ends running SSH/browser sessions; saved browser profiles remain. Reload the desktop and reopen Browser afterward. Ordinary updates without a worker restart will not activate URL navigation in an already running worker.

## 0.1.0-alpha.1 — 2026-09-08

First numbered Alpha release. This captures the existing application and its installation tooling; earlier development remains available in Git history.

### Included

- English Windows 2000 styled web desktop, grouped Start menu, movable icons and application windows.
- Private accounts, owner/admin roles, per-user storage quotas, file uploads, folders and Recycle Bin.
- Persistent SSH terminals, per-account Chromium profiles with audio and ad blocking, code editor and SFTP editing.
- Dimension Drawing, Calculator, Notes and Tasks, search, favourites and Task Manager with resource graphs.
- Configurable Raspberry Pi 5 installer, updater, health checks, Caddy HTTPS setup and SQLite initialization.
- Verified local backups, recovery documentation and organized configuration, Caddy and maintenance examples.
- A version file, version-reporting command, release documentation and this changelog.

### Alpha limitations

- The complete installation on a newly imaged physical Pi still needs independent verification. Configuration, backend tests and upgrades on the existing installation have been checked.
- Session persistence requires the Pi and remote devices to keep running. Worker restarts can end jobs.
- Database and configuration compatibility may change during Alpha. Downgrading code does not undo database migrations; use compatible backups for recovery.
- See the [security review](docs/security/review-2026-09-08.md) for remaining isolation and resource-limit constraints.

[0.1.0-alpha.1]: https://github.com/xhonken/Pi-2000/releases/tag/v0.1.0-alpha.1
