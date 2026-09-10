# Changelog

User-visible changes are recorded here for each numbered release. Development between releases is listed under Unreleased. See [versioning and releases](docs/VERSIONING.md) for installation and maintainer instructions.

## Unreleased

- Wait for HTTPS readiness during package setup and adjust the 2 GB Browser admission reserve for coexistence with local MariaDB, retaining its hard memory limit.

- Add Debian terminal setup dialogs for the initial administrator password, a private local MariaDB database/connection and an optional Linux account for Local Terminal. Existing passwords and accounts are preserved on upgrades.
- Add owner-only Local Terminal under System Tools, with loopback SSH, OS-managed account mapping, pinned local host keys and separate Linux authentication.

- Allow slower cold SD-card startup for Browser and syntax checks while retaining CPU and memory limits.

- Add an arm64 Debian package for Raspberry Pi OS 64-bit / Debian 13, with prebuilt Python runtimes, APT dependencies, separate HTTPS configuration, verified backup before upgrades and retained account data on removal.
- Add a smaller Browser resource profile for 2 GB Raspberry Pi systems and require an available memory controller before starting a new sandboxed Browser session.

- Keep upload file inputs attached to the page and launch pickers directly from user actions; share cleanup and account guards across desktop, Files and folder uploads.

- Add Help → About Pi-2000Web with the installed version, source revision and generated build identity.
- Protect unsaved API requests and Git file dialogs on replacement, close and logoff; warn before reloading unsaved development work and save SQL drafts before logoff.
- Apply phpMyAdmin dependency-deprecation filtering before AJAX/page rendering while preserving actionable warnings.
- Include phpMyAdmin integration and build identity in code backups; verify private restored API requests, Git files and SQL drafts without reviving login tokens.
- Add isolated HTTPS Git clone/fetch/pull/push and rejected-push coverage, and an unprivileged packaged phpMyAdmin test runtime.

- Refresh the README, user guide and GitHub descriptions for Alpha 3, including phpMyAdmin, Git Projects, API Tester, syntax diagnostics and verified Browser memory protection. Documentation only; the published Alpha 3 source tag is unchanged.

## 0.1.0-alpha.3 — 2026-09-09

- Integrate upstream phpMyAdmin in MariaDB Manager with a Windows 2000 theme, private saved connections and an authenticated, isolated PHP-FPM gateway. Preserve the native saved SQL workspace as a separate tool.

- Separate MariaDB table data from SQL editing; use a single scrolling query strip with close buttons, a query selector and bulk management. Preserve legacy drafts, reuse empty tabs, bound new tab growth and isolate recent results by query. Prevent SQL tab names from intercepting application menu commands.

- Row forms now execute inserts/edits/deletes directly on OK and refresh the table; explicit defaults, NULL and current-time modes avoid blank auto-ID/datetime errors. Add a tabbed SELECT builder with guided LEFT/RIGHT/INNER/CROSS joins, foreign-key suggestions, columns, filters, sorting and editable SQL output.

- Expand MariaDB Manager with classic administration dialogs for databases, users/hosts, exact database grants, roles, account security/limits, table design, indexes, foreign keys, routines/events and maintenance. Review single-use SQL plans before applying; passwords stay out of previews and saved SQL drafts.
- Add MariaDB filtering/sorting, bounded database text search and relationship diagrams. Export all table rows and programmable objects through private transfer jobs; restore SQL with DELIMITER support, progress, cancellation and partial-completion reporting. Document size/consistency limits.
- Add Git Projects with sandboxed private workspaces, HTTPS remotes, file editing, status/diffs, staging/commits, branches/history and fetch/pull/push controls. Include project data in local backups.
- Add Code Editor syntax diagnostics for Python, JavaScript and JSON without executing source code.
- Add API Tester with encrypted private saved requests, HTTP methods/headers/auth/body, formatted responses and timing. Protect platform endpoints and avoid forwarding Pi login credentials.

- Show MariaDB connection failures in a prominent alert, report connection progress, and explain login/TLS/network errors, including unexpected proxy responses.

- Add private saved MariaDB TCP/TLS connections and optional encrypted credentials; include the credential key in verified backups. The native workspace remains available alongside phpMyAdmin. See `docs/MARIADB-MANAGER.md` for scope and limits.

- Browser checks available server RAM before starting a new session; reconnecting to a running session remains possible when memory is low.
- Browser reports memory-limit stops, crashes, low disk space and idle timeouts separately, removes a stopped stream and offers explicit reconnect.
- Browser displays a warning as its memory use approaches the limit. Watchdog stop reasons are logged and kept per account.
- Memory cgroup activation and post-reboot verification are documented in docs/BROWSER-MEMORY.md.

- Keep the Start menu Search button wide enough for its label, including larger text sizes.

### Upgrade and known limitations

The updater now installs phpMyAdmin and PHP 8.4 packages and a dedicated isolated PHP-FPM service. Run the updater, then doctor, and reload the desktop. Existing saved connections and native SQL drafts are preserved. Complete active database work before updating because API database sessions are not resumed.

Optional phpMyAdmin metadata features require configuration storage on an authorized database. Twig deprecation notices have still been reported on some pages; the current filter does not cover every path. This release does not claim that warning is fully resolved. See [release notes](docs/releases/0.1.0-alpha.3.md) for validation and resource limits.

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
