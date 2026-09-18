# Changelog

User-visible changes are recorded here for each numbered release. Development between releases is listed under Unreleased. See [versioning and releases](docs/VERSIONING.md) for installation and maintainer instructions.

## Unreleased

- Fix Log Off getting blocked by workspace save conflicts or failed recovery.
  Offer an explicit choice to keep the last saved workspace and sign out,
  retain application cancellation guards, and avoid duplicate logout attempts.
- Make the isolated FFmpeg, Git and Arduino launchers usable on x86 test hosts by including their
  optional `/lib64` loader directory. Allow 768 MiB of virtual address space for
  x86 FFmpeg initialization while keeping the Pi limit at 512 MiB. The released
  Debian package remains arm64-only.
- Correct nested sandbox support in the disposable GitHub CI container and check
  it before running the application tests.

## 0.1.0-alpha.6 — 2026-09-18

- Stabilize IPTV live playback with a startup buffer and less aggressive live
  catch-up, buffered HLS quality changes and window-aware automatic quality.
  Avoid periodic position writes for live TV; retain on-demand resume saving.
  Add a real browser playback regression with a simulated network outage.

- Add a private IPTV Player with M3U/Xtream import, live/movie/series views,
  country/group/search filters, favorites, viewing positions, XMLTV and provider
  catchup. Stream HLS, TS and media files through login-bound opaque URLs; add
  isolated FFmpeg AAC/H.264 compatibility modes and bounded streaming imports.
  See [IPTV Player](docs/IPTV.md) for format, provider and security boundaries.

- Harden Browser supervisor log handling and root backup traversal against planted
  or raced filesystem links; rotate Vault data keys as well as passwords/recovery
  protection. Bound active requests and login sessions, reject encoded/malformed
  request bodies, revalidate phpMyAdmin operations and add security event logging.
- Add desktop HTTP security headers and a minimum reviewed Chromium security
  version; Browser pauses if the installed engine is known to predate fixes.
  See [security boundaries and verification](docs/SECURITY.md).

- Continuously checkpoint each account's workspace with save status, conditional
  writes and recovery that survives failed reads, individual app errors and a
  missing terminal service. Restore window order/layout and supported Pi++,
  Arduino, drawing and calculator state; show reconnectable terminal windows
  after reboot while keeping Vault locked and excluding credential forms.

- Bind Browser sessions to their account version before waiting for startup, so
  account housekeeping does not stop a valid session during a slow cold start.

- Add account-owned desktop application icons, personal labels, restore defaults,
  Start-menu Send to Desktop, icon/background context menus, selection rectangles,
  multiple selection/dragging and keyboard commands. Double-click opens by default;
  single-click remains configurable. Add sorting, auto arrangement, grid alignment,
  show/hide icons, file clipboard commands and ETag conflict protection between tabs.
- Preserve file extensions when creating a renamed copy in the same folder.

- Add a personal Vault application with client-encrypted titles/content, separate
  A/B passphrases, fresh B unlock per entry, automatic locking, password generation,
  encrypted export/import and a user-held recovery key. Account-bound APIs include
  no administrator read override; Vault ciphertext participates in quotas/backups.

- Add guarded OS-administrator recovery planning and application for managed identities,
  account data and homes; preserve UID/GID and file modes in new backups, retain
  rollback data and an operation journal, and support age-encrypted external exports.
- Show installed and running component builds in About and System Status; add
  leased draining and idle-only activation for session and Arduino workers.
- Share a module-aware deployment inventory between source installation, Debian
  packages and backups; verify staged/installed hashes and exclude private notes.
- Pin the development test dependencies, isolate UI test sockets/artifacts, include
  all ordinary applications in one test entrypoint and add a GitHub CI workflow.

These changes are included in Alpha 6. Fresh-machine recovery and clean Pi 4
installation remain acceptance checks. See the [release notes](docs/releases/0.1.0-alpha.6.md),
[maintenance](docs/MAINTENANCE.md) and [recovery](docs/RECOVERY.md).

## 0.1.0-alpha.5 — 2026-09-16

- Keep large application windows and their title-bar controls within the desktop when opened, restored or resized.

- Keep CAD-specific Object commands out of Display Studio, and reconcile missing system packages during source updates as well as fresh installation.

- Add Network Tools with private targets, Pi-originated DNS/ping/TCP checks and graphical monitoring; Display Studio with layers, images, round-screen previews and PNG/RGB565/Arduino exports; Archive Manager with safe ZIP extraction and creation; Log Viewer with bounded local/SSH tails, filtering and follow mode.
- Add Serial Plotter to Arduino Workshop with incremental samples, up to eight curves, scale controls, pause and CSV export. Preserve USB permissions and exclusive-port access.

- Replace the Code Editor presentation with Pi++: an original icon, compact toolbar, document panel, accessible tabs, expanded menus, Save All, graphical open/import, search across open documents, bookmarks, language selection, LF/CR LF conversion and private editor preferences. Preserve existing private files, SFTP connections, conflict checks and recovery drafts.

- Prepare missing Arduino catalogs automatically when opening package managers or searching libraries, and allow catalog downloads inside their sandbox. Show search progress and readable failures.

- Add an Arduino Workshop desktop icon as well as its Start menu entry.

- Add Arduino Workshop with private multi-file sketches, classic application menus, board options, graphical board/library version managers, header insertion, import/export, Verify, Pi-connected USB Upload and Serial Monitor.
- Run Arduino CLI in a separate memory-limited service and filesystem sandbox, restrict USB access to administrators and preserve the latest job log across service restarts. Include the tools and service in source and Debian installation paths.
- Verify real ESP32 compilation with ArduinoJson; physical USB flashing remains a hardware acceptance check.

### Test installation and remaining checks

Includes a new arm64 test package for Raspberry Pi OS 64-bit / Debian 13 (Trixie).
Back up and finish live work before upgrading; use the installation method already
in use on that host. Physical ESP32 flashing, sensor/display hardware and fresh
installation of this release on a reimaged Pi 4 remain pending. See the
[Alpha 5 release notes](docs/releases/0.1.0-alpha.5.md).

## 0.1.0-alpha.4 — 2026-09-12

- Create one Linux identity and private home per web account; authenticate through PAM and remove the legacy application verifier after migration.
- Protect the installation creator by stable identity, including database and privileged-service guards; ask for the creator username during Debian setup.
- Give administrators their own Local Terminal via a private loopback SSH listener. Ordinary managed users have no login shell; managed identities are excluded from the host SSH listener. Sudo is an independent OS decision.
- Add deactivation, exact-name deletion confirmation, protected links to existing Linux identities, recoverable account provisioning and session revocation following external password changes.
- Include managed account recovery metadata and homes in root-only local backups; preserve linked OS accounts and their homes.

- Show a dedicated Local Terminal desktop icon for all administrators.

- Start Browser with a modest display size while preserving large-window resizing, and allow up to three minutes for cold SD-card initialization.

- Wait for HTTPS readiness during package setup and adjust the 2 GB Browser admission reserve for coexistence with local MariaDB, retaining its hard memory limit.

- Add Debian terminal setup dialogs for the initial administrator password, a private local MariaDB database/connection and an optional Linux account for Local Terminal. Existing passwords and accounts are preserved on upgrades.
- Add Local Terminal for all web administrators under System Tools, with loopback SSH, OS-managed account mapping, pinned local host keys and separate Linux authentication.

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

### Upgrade and known limitations

Back up before upgrading, finish live jobs and restart the session worker to activate the new account policy. Legacy accounts migrate at successful login; explicitly linked OS accounts retain their Linux password and permissions. MariaDB passwords remain independent. See [system accounts](docs/SYSTEM-ACCOUNTS.md) and the [Alpha 4 release notes](docs/releases/0.1.0-alpha.4.md).

The final PAM-enabled Debian package has not yet passed fresh installation on a reimaged Pi 4. Earlier package candidates passed physical installation/lifecycle tests; PAM and per-user terminals were verified on the existing Pi 5. Full OS-account restore still requires manual UID/home reconciliation.

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
