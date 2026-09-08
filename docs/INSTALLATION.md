# Install Pi-2000Web on Raspberry Pi 5

Ready-to-edit configurations and scripts are indexed in **[Examples](../Examples/README.md)**.

Pi-2000Web has a single configuration file and a unified installer. The installer sets up system packages, Caddy HTTPS, the Python API, a private SQLite database, persistent-session services, local backups and, optionally, the Chromium browser with audio.

**Alpha status:** the configuration, generated Caddy configuration, backend and existing-installation upgrade path are tested. A full end-to-end run on a newly imaged physical Pi remains to be independently verified. Keep a backup and report installation failures with the command and error output, excluding passwords and private keys.

## 1. Prepare the Pi

Use **Raspberry Pi 5 with 64-bit Raspberry Pi OS / Debian 13 (Trixie)**. The installer checks Debian version, ARM64 architecture and systemd. Other versions, 32-bit systems and Docker are not supported by this installer yet.

Allow at least **6 GiB of free installation space** with Browser, or **2 GiB without Browser**, plus room for user files and backups. An 8 GB Pi is recommended for several simultaneous applications/browser sessions. Installation needs internet access for Debian packages, Python wheels and the pinned browser source and npm dependencies.

Set up your normal Pi login and SSH access. Reserve the Pi address in your router/DHCP server, or configure a DNS name that resolves to it. The installer does not change your router, Pi hostname, Wi-Fi, firewall or SSH login.

Pi-2000Web uses ports **80 and 443** for Caddy and loopback port **8765** for its API. Use a dedicated Pi or review [Caddy integration](CADDY.md) if a web server already runs there. The installer refuses to overwrite another Caddy site or take ports occupied by another service.

## 2. Get the source

```sh
sudo apt update
sudo apt install -y git
git clone https://github.com/xhonken/Pi-2000.git
cd Pi-2000
```

While the repository is private, your GitHub account needs access. You can use GitHub CLI instead:

```sh
sudo apt install -y gh
gh auth login
gh repo clone xhonken/Pi-2000
cd Pi-2000
```

When connecting over PuTTY, complete GitHub CLI device login in the web browser on your own computer. Do not put GitHub tokens in the project configuration.

## 3. Set your network details

```sh
cp config/config.example.toml pi2000.toml
nano pi2000.toml
```

Example for a **local network** (replace the example address with your Pi address):

```toml
[network]
public_url = "https://192.168.1.50"
tls = "internal"
bind_address = ""

[features]
browser = true
```

| Setting | Meaning |
| --- | --- |
| `public_url` | The exact HTTPS address users will open. An IP address or DNS name; no path, username, password or custom port. |
| `tls` | `internal` uses Caddy local CA for LAN access. `public` requests an automatically renewed public certificate for a public DNS name. |
| `bind_address` | Optional local IP on which Caddy listens. Empty means all interfaces. This does not configure a firewall. |
| `browser` | `true` installs Chromium, display/audio/streaming and build dependencies. `false` skips Browser installation on a new Pi; it does not uninstall an existing browser. |

For a domain such as `desktop.your-domain.net`, set `public_url = "https://desktop.your-domain.net"` and `tls = "public"`. Configure DNS and certificate-validation reachability first. See [Caddy and HTTPS](CADDY.md) for LAN certificates, public certificates and existing web servers.

TOML is read as data, not sourced as a shell script. Unknown fields and invalid values are rejected. It contains deployment settings only: no initial admin password, SSH passwords or database credentials. The checkout file `pi2000.toml` is excluded from Git.

Preview without changing the system:

```sh
./scripts/install.sh --config pi2000.toml --check
./scripts/install.sh --config pi2000.toml --render-dir .install-plan
```

The render directory contains the generated Caddyfile, runtime environment, normalised TOML and service definitions. Preview validates syntax/settings only; it does not verify DNS, port availability or package installation. The actual installer performs host preflight checks.

## 4. Install everything

```sh
sudo ./scripts/install.sh --config pi2000.toml
```

The installer:

1. Validates the configuration, OS, architecture, DNS, selected bind address, ports and available space.
2. Checks ownership of any existing Caddyfile before making changes.
3. Installs Debian packages, including Caddy and the required Python virtual-environment support.
4. Creates the private service account and state directory.
5. If enabled, builds the pinned Selkies browser client as the unprivileged `pi2000-build` account, installs its wheels and the Chromium/audio/display packages.
6. Writes the shared runtime settings and publishes the API and desktop.
7. Starts the services; the application creates the SQLite schema and first owner automatically.
8. Validates/reloads Caddy, checks HTTPS using certificate verification, compares served assets, verifies private API access and database integrity, and creates a verified backup.

Browser building can take several minutes. npm/build logs appear in the terminal. Keep the session connected until the command finishes. A failure returns a nonzero exit status and is not reported as a completed installation.

The installed configuration is **`/etc/pi2000web/config.toml`**. Services obtain the public origin from generated **`/etc/pi2000web/runtime.env`**. Do not edit the generated environment or service units to set the public URL; edit the TOML and run the updater.

## 5. Trust local HTTPS and log in

For `tls = "internal"`, copy this **public certificate** to your viewing computer and install it in the appropriate trusted root certificate store:

```text
/var/lib/caddy/.local/share/caddy/pki/authorities/local/root.crt
```

Only export `root.crt`; never export `root.key` or the full Caddy state directory. The installer prints the CA location. Each client/browser may need its own trust setup. [CADDY.md](CADDY.md) describes this in more detail.

Retrieve the generated first password on the Pi:

```sh
sudo cat /var/lib/win2k-admin/initial-password.txt
```

Open your configured `public_url` and log in as **`admin`**. Change the password through Start → Settings → Change Password. This removes the initial-password file. A missing file on an established installation is normal; rerunning the installer does not reset existing passwords.

## Updates and network changes

From the checkout:

```sh
git pull --ff-only
sudo ./scripts/update.sh
sudo ./scripts/doctor.sh
```

Update and doctor use `/etc/pi2000web/config.toml` by default. You can pass `--config another.toml` explicitly. Update makes a verified data backup and a previous-code/configuration snapshot before changing the existing installation. It reuses the installed browser environment. When browser dependencies or the pinned browser revision change, rerun `install.sh --config /etc/pi2000web/config.toml` to rebuild/install them.

For a new address or TLS mode:

```sh
sudo nano /etc/pi2000web/config.toml
sudo ./scripts/update.sh --check
sudo ./scripts/update.sh --restart-sessions
```

**Changing the public URL requires a worker restart.** The installer refuses the change without `--restart-sessions` when the worker is running. That flag explicitly ends running terminals and browser sessions. Finish jobs first. With an unchanged origin, normal updates preserve the worker; worker-owned code changes apply on its next restart.

If the update fails, retain the printed previous-code snapshot and verified data archives. The installer does not silently revert a migrated database. Correct the reported problem, rerun the update and then doctor. Apt/package and Python-environment changes are not transactionally rolled back. Backups do not replace a full system image when testing system changes.

### Original installation migration

The older installation used direct settings in service files and one dedicated Caddyfile. Create a TOML file with **the same existing HTTPS origin** and run:

```sh
sudo ./scripts/update.sh --config pi2000.toml --adopt-existing
```

Adoption accepts only the original known single-site configuration; it does not authorise overwriting arbitrary Caddy sites. The service/database identifiers remain compatible and existing user data is preserved. Later updates use the installed configuration normally.

The former `install-files.sh`, `install-security.sh` and `install-foundation.sh` now forward to `update.sh`. Use the clear `install.sh`, `update.sh` and `doctor.sh` entrypoints for new instructions. Low-level `publish-*.sh` scripts are implementation helpers, not fresh installers.

## Database and installed layout

There is **no separate database server or database password to configure**. SQLite is private to the application. The schema and supported migrations are defined in `server/app.py`, `file_store.py`, `personal_store.py` and `session_store.py`.

| Table | Contents |
| --- | --- |
| `users` | Accounts, salted password hashes, roles, activation/session versions and storage quotas |
| `items`, `hostkeys` | Per-account SSH profiles/folders and verified remote host keys |
| `workspaces`, `desktops` | Window restoration, shortcuts, icon positions and backgrounds |
| `files` | Owned file/folder metadata, hierarchy, state, size and content keys |
| `preferences`, `personal_docs` | Preferences, favourites, notes, drawings and editor drafts |
| `login_sessions` | Token digests and expiring login-session data |

File bytes are stored as private blobs alongside the database. Back up the database and related storage together; copying only `admin.sqlite3` is insufficient. Foreign-key checks and protected-owner triggers are created automatically. New accounts receive 50 MiB by default; administrators adjust quotas through User Management.

| Location | Purpose |
| --- | --- |
| `/etc/pi2000web/config.toml` | Your installed deployment configuration |
| `/etc/pi2000web/runtime.env` | Generated shared service settings |
| `/etc/caddy/Caddyfile` | Generated dedicated Caddy configuration |
| `/srv/win2k` | Published static desktop |
| `/opt/win2k-admin` | Installed Python application and virtual environment |
| `/opt/win2k-browser/venv` | Browser streaming environment |
| `/var/lib/win2k-admin/admin.sqlite3` | Private SQLite database |
| `/var/lib/win2k-admin` | Private user data and browser profiles |
| `/var/cache/pi2000web/build` | Unprivileged browser build cache |
| `/var/backups/win2k` | Verified local data backups |
| `/var/backups/pi2000web-update-*` | Previous code/site/configuration snapshots |
| `/run/win2k-sessions/worker.sock` | Private persistent-worker connection |

The `win2k` service/storage names are stable internal compatibility identifiers, not network-specific settings. The checkout can live anywhere and can be named `Pi-2000`, `Pi-2000Web` or another name. Avoid moving installed storage directories manually.

## Diagnostics and restore

```sh
sudo ./scripts/doctor.sh
systemctl status win2k-admin win2k-sessions caddy
systemctl status win2k-backup.timer
sudo journalctl -u win2k-admin -n 100 --no-pager
sudo journalctl -u win2k-sessions -n 100 --no-pager
sudo journalctl -u caddy -n 100 --no-pager
```

Doctor verifies HTTPS with the correct certificate authority, served assets against your checkout, anonymous API rejection, SQLite integrity, active services and private Caddy administration. Use the checkout corresponding to the installed version when comparing assets. It reports failure instead of ignoring certificate errors.

To restore a data backup:

```sh
sudo ./scripts/restore-backup.sh /var/backups/win2k/ARCHIVE.tar
```

Restore validates a staged copy before replacing data. It stops services, ends running jobs and requires users to log in again. Data archives do not change your installed network TOML. Local backups are on the same disk: arrange off-device copies for disk-failure protection.

## Known Alpha limits

Browser profiles do not yet have hard per-user disk quotas. On kernels without memory cgroups, the browser memory watchdog is a soft limit. Browser/SSH network access is not isolated from the Pi LAN. Read the [security review](security/review-2026-09-08.md) before adding untrusted accounts or exposing the service beyond your trusted network. The installer does not turn this into unrestricted multi-tenant hosting.
