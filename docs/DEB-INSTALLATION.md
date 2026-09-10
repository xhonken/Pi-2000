# Debian package installation

Target: Raspberry Pi OS 64-bit based on Debian 13 (Trixie), arm64, Python 3.13.
The package includes pinned Python runtimes for the desktop and Browser. APT
installs native dependencies; no pip download or compilation occurs on the Pi.
32-bit Raspberry Pi OS and Debian 12 are not supported by this build.

```sh
sudo apt install ./pi2000web_0.1.0~alpha.4-4_arm64.deb
sudo pi2000web doctor
```

The first installation selects the Pi's default-route LAN address for HTTPS.
To change it, finish live jobs and run
`sudo pi2000web configure --url https://YOUR-HOST --restart-sessions`.
The default uses Caddy's local CA: install the public root certificate from
`/var/lib/caddy/.local/share/caddy/pki/authorities/local/root.crt` on your client.
Do not copy Caddy's private keys. Read the generated initial password locally with
`sudo cat /var/lib/win2k-admin/initial-password.txt`, sign in as admin, and change it.

On systems without the memory controller:

```sh
sudo pi2000web enable-memory-controller
sudo reboot
```

Reboot only after saving work. A backup of the original boot command line is kept
privately. A 2 GB Pi uses a 768 MiB Browser limit and a 256 MiB start reserve;
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
credential keys. Reinstallation preserves accounts and saved files. Do not use the source updater
on a package-managed host: install the next `.deb` through APT instead.

Build on the matching arm64 Python 3.13 host:

```sh
./scripts/build-browser.sh
python3 scripts/build-deb.py
```

The output `.deb` and SHA-256 file are under `build/packages/`. Local project notes,
credentials, runtime databases and machine configuration are never package inputs.

## Validation on physical hardware

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
Cold SD-card startup exposed short wall-clock deadlines. Browser now allows up to
90 seconds to initialize and syntax checks allow 15 seconds for startup and disk
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
