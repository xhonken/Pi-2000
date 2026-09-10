# Debian package installation

Target: Raspberry Pi OS 64-bit based on Debian 13 (Trixie), arm64, Python 3.13.
The package includes pinned Python runtimes for the desktop and Browser. APT
installs native dependencies; no pip download or compilation occurs on the Pi.
32-bit Raspberry Pi OS and Debian 12 are not supported by this build.

```sh
sudo apt install ./pi2000web_0.1.0~alpha.4-3_arm64.deb
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
credential keys. Reinstallation must preserve accounts and saved files. Physical
installation/upgrade/remove tests are recorded separately from build success.

Build on the matching arm64 Python 3.13 host:

```sh
./scripts/build-browser.sh
python3 scripts/build-deb.py
```

The output `.deb` and SHA-256 file are under `build/packages/`. Local project notes,
credentials, runtime databases and machine configuration are never package inputs.
