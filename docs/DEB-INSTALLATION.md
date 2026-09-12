# Debian package installation

Target: Raspberry Pi OS 64-bit based on Debian 13 (Trixie), arm64, Python 3.13.
The package includes pinned Python runtimes for the desktop and Browser. APT
installs native dependencies; no pip download or compilation occurs on the Pi.
32-bit Raspberry Pi OS and Debian 12 are not supported by this build.

```sh
sudo apt install ./pi2000web_0.1.0~alpha.4-12_arm64.deb
sudo pi2000web doctor
```

The first installation selects the Pi's default-route LAN address for HTTPS.
To change it, finish live jobs and run
`sudo pi2000web configure --url https://YOUR-HOST --restart-sessions`.
The default uses Caddy's local CA: install the public root certificate from
`/var/lib/caddy/.local/share/caddy/pki/authorities/local/root.crt` on your client.
Do not copy Caddy's private keys. The Debian terminal dialogs ask you to choose
and confirm the protected creator username and password. Each web user gets an
individual managed Linux identity and a private home. Administrators receive Local
Terminal without automatic sudo; ordinary users have no local login shell.
Password fields are cleared from debconf after use and passed through stdin.

MariaDB setup creates the `pi2000_admin` database and matching SQL account with
privileges only on that database, using the initial creator password. Its encrypted
connection appears only for the creator. Existing SQL accounts/databases are never
overwritten. Later Linux/web password changes leave SQL credentials independent.

The private Local Terminal SSH listener binds only to loopback port 2222 and uses
pinned local host keys. Managed users cannot log in through the host SSH listener.
An existing Linux identity is linked only by an explicit OS administrator command;
its password and permissions are preserved. See [system accounts](SYSTEM-ACCOUNTS.md).

Upgrades preserve users and the creator. Legacy users migrate at their next login.
Fresh setup requires local MariaDB OS-root socket authentication; it never changes
MariaDB's root authentication. Unattended fresh installs preseed both admin-password
fields and `pi2000web/creator-username` through a protected input stream.

On systems without the memory controller:

```sh
sudo pi2000web enable-memory-controller
sudo reboot
```

Reboot only after saving work. A backup of the original boot command line is kept
privately. A 2 GB Pi uses a 1024 MiB Browser hard limit, an 896 MiB high threshold,
up to 128 MiB swap and a 128 MiB start reserve;
several simultaneous Browser sessions or large web applications may not fit.
Larger machines retain the existing 1536 MiB Browser budget.

The package uses its own HTTPS service and configuration. An unchanged Caddy
sample service is disabled, while its configuration file is retained. A custom
existing Caddy service is not overwritten. phpMyAdmin sees the gateway config
through a read-only service mount; the distribution's configuration is retained.

Upgrade with `sudo apt install ./NEW-PACKAGE.deb`. A verified local backup is
required by the upgrade script before files are replaced. Finish database operations
first: the API and PHP runtime restart. SSH/Browser worker sessions are preserved;
use `sudo pi2000web restart-sessions` after finishing jobs to activate new worker
code. A legacy script-managed installation is rejected rather than overwritten.

Remove with `sudo apt remove pi2000web`. Account data and backups remain; purge
removes generated platform configuration but deliberately retains user data and
credential keys. Managed Linux accounts, their access restrictions and MariaDB databases/accounts also remain after purge; remove them explicitly only when no longer needed. Reinstallation preserves accounts and saved files. Do not use the source updater
on a package-managed host: install the next `.deb` through APT instead.

Build on the matching arm64 Python 3.13 host:

```sh
./scripts/build-browser.sh
python3 scripts/build-deb.py
```

The output `.deb` and SHA-256 file are under `build/packages/`. Local project notes,
credentials, runtime databases and machine configuration are never package inputs.

## Final Alpha 4 package status

The release package `0.1.0~alpha.4-12` includes PAM authentication and per-user Linux identities. It is built from the Alpha 4 source release and inspected with package metadata and checksum checks. **Fresh installation of this package on a reimaged Pi 4 is still pending.** PAM/terminal behavior was tested on the existing Pi 5 installation; the earlier physical Pi 4 results below predate that account migration.

## Earlier package validation on physical hardware

The local Alpha 4 candidate was tested on a Raspberry Pi 4 Model B with 2 GB RAM,
64-bit Raspberry Pi OS / Debian 13.6 and Python 3.13. Tests covered a first APT
installation on a host without Pi-2000, service startup after reboot, trusted HTTPS
and served-asset checks, generated administrator login, package upgrade with an
unchanged session-worker PID, and removal/purge with retained accounts, files and
credential keys, followed by successful reinstallation and reading the original
file with the original account. Distribution Caddy and phpMyAdmin configuration checksums remained
unchanged. The upgrade backup completed successfully.

Functional checks used a disposable web account and a disposable MariaDB database:
Browser startup and its stream client, live kernel memory limits, Git init/edit/
stage/commit, syntax diagnostics, native upload pickers from the desktop and Files,
and phpMyAdmin SQL, direct insert, import/export, protected paths and session
revocation. This is functional coverage, not a long-duration load test on a 2 GB Pi.
Cold SD-card startup exposed short wall-clock deadlines and reclaim pressure
from overly low 512/640 MiB high thresholds. The 2 GB profile now uses 896 MiB high
and a 1024 MiB hard cap, with 1152 MiB available RAM required before starting. Browser now allows up to
180 seconds to initialize and syntax checks allow 15 seconds for startup and disk
reads while retaining their three-second CPU budget.

`tests/run_deb_remote_ui.py` repeats functional checks against an explicitly
selected test Pi. It requires a pre-created disposable ordinary web account, a
trusted copy of its public CA certificate, an SSH control connection and the local
Playwright/MariaDB test dependencies. It reads the test password interactively.
`--inspect-browser` pauses while Browser runs so a root operator can verify
`memory.max`, `memory.high` and `memory.swap.max` in its private cgroup. The test
retains `upgrade-preserved.txt` as a lifecycle fixture and resets only the disposable
account's saved window layout before UI checks. Remove the disposable account after
validation.

Earlier local candidate `0.1.0~alpha.4-5` passed the complete functional suite after
APT installation and session-worker restart, starting with the Pi's disk cache
cleared. Its live 1024/896/128 MiB limits were read directly from cgroup files; no
OOM kill occurred. The generated administrator login and account-removal path were
also checked, then the disposable account was removed. Final package checksum,
services, trusted HTTPS assets and SQLite checks passed. The matching backend
suite passed 88 tests. The package is a local candidate, not a GitHub release.

The terminal installer was additionally tested through actual Debian dialogs on
physical hardware: chosen admin password, a separate Linux account with password-required
sudo, private automatic MariaDB login through phpMyAdmin, and role-based terminal access. Ordinary users are denied, while additional web
administrators can open Local Terminal with Linux authentication. The installer clears its debconf password
answers and does not create a plaintext initial-password file for a chosen password.

With local MariaDB enabled, the 2 GB profile uses a 128 MiB admission reserve
(1152 MiB available RAM before starting), while retaining the 1024/896/128 MiB
hard/high/swap limits. A physical cold-cache test with Raspberry OS desktop and
MariaDB running passed without a cgroup OOM or hard-limit event. The complete
backend suite passes 97 tests. These results describe the earlier pre-PAM candidate.

Browser begins at 1280 × 720 while retaining its 4096 × 4096 resize maximum.
This avoids rendering a large empty desktop before a client connects. Cold SD-card
startup with MariaDB can exceed 90 seconds, so initialization allows up to three
minutes without increasing the hard memory limit.
