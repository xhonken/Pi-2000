# Installation and maintenance examples

Copy these examples and replace the sample addresses with your own settings. Run the commands below from the repository root. The scripts find the checkout relative to their own location, so keep them inside this repository. All scripts support `--help` without making changes.

The supported automatic installation targets a dedicated Raspberry Pi 5 running 64-bit Raspberry Pi OS / Debian 13. Read the [installation guide](../docs/INSTALLATION.md) and [Caddy guide](../docs/CADDY.md) before installing. These examples use the project's existing installer and maintenance services.

## Choose a configuration

| Example | Purpose |
| --- | --- |
| [configuration/lan-ip.toml](configuration/lan-ip.toml) | Reserved LAN IP address, HTTPS with Caddy's local CA, Browser included. |
| [configuration/lan-hostname.toml](configuration/lan-hostname.toml) | Resolvable local hostname, HTTPS with Caddy's local CA, Browser included. |
| [configuration/public-domain.toml](configuration/public-domain.toml) | Your own public DNS name, automatic public HTTPS certificate, Browser included. |
| [configuration/without-browser.toml](configuration/without-browser.toml) | New installation without the streamed Chromium runtime. |

```sh
cp Examples/configuration/lan-ip.toml pi2000.toml
nano pi2000.toml
./scripts/install.sh --config pi2000.toml --check
sudo ./Examples/installation/install-from-config.sh pi2000.toml
```

`192.168.1.50`, `pi2000.local` and `desktop.example.com` are placeholders. Set an address that clients can reach and the Pi can resolve. The installer does not configure router reservations, DNS, mDNS or port forwarding. Leave `bind_address` empty to listen on all interfaces, or set an IP assigned to the Pi; binding is not a firewall. LAN clients must trust the local CA certificate. Public TLS needs your own domain and the DNS/reachability setup in the Caddy guide.

`pi2000.toml` is ignored by Git. Do not put passwords or keys in it. The installer stores the active settings in `/etc/pi2000web/config.toml`. Changing `browser` to `false` does not uninstall Browser or hide its desktop application.

## Caddy and certificates

| Example | Purpose |
| --- | --- |
| [caddy/lan-ip.Caddyfile](caddy/lan-ip.Caddyfile) | Complete dedicated-server configuration for the LAN IP example. |
| [caddy/lan-hostname.Caddyfile](caddy/lan-hostname.Caddyfile) | Complete configuration for the local hostname example. |
| [caddy/public-domain.Caddyfile](caddy/public-domain.Caddyfile) | Complete configuration for the public domain example. |
| [caddy/preview-caddy-config.sh](caddy/preview-caddy-config.sh) | Render Caddy, application environment and service files into a new directory for review. If Caddy is installed, also adapt its configuration to JSON. |
| [caddy/export-local-ca-certificate.sh](caddy/export-local-ca-certificate.sh) | Export the public LAN CA certificate for your client devices. |

The Caddyfiles illustrate what the installer generates. Use TOML and the installer to apply changes so the application origin and Caddy address remain consistent. These are complete configurations for a dedicated server; they are not snippets to append to another Caddy installation. The private Unix administration socket and internal `win2k` paths are intentional. The installer creates the required directories and permissions.

```sh
# Choose a directory that does not already exist.
./Examples/caddy/preview-caddy-config.sh pi2000.toml .install-plan

# Export the public certificate after completing a LAN installation.
sudo ./Examples/caddy/export-local-ca-certificate.sh > pi2000web-root.crt
openssl x509 -in pi2000web-root.crt -noout -subject -fingerprint -sha256
```

Check the certificate fingerprint against the Pi before trusting it on a client. Transfer the `.crt` file using SCP or WinSCP and follow the [certificate trust instructions](../docs/CADDY.md). Keep it outside your checkout or remove the exported copy afterward. Never distribute `root.key`. Public TLS does not require exporting a local CA.

The preview command changes only its output directory. Caddy adaptation checks configuration syntax; it does not prove that DNS, certificate issuance or network connectivity will work.

## Installation and maintenance scripts

| Script | Purpose |
| --- | --- |
| [installation/install-from-config.sh](installation/install-from-config.sh) | Check your configuration, then run the full installer. Installs packages and configures services. |
| [installation/update-and-check.sh](installation/update-and-check.sh) | Apply the current checkout and run the installed application's health checks. Defaults to the installed configuration. |
| [maintenance/create-verified-backup.sh](maintenance/create-verified-backup.sh) | Run the installed backup service, including its verification and retention policy. |
| [maintenance/restore-user-data.sh](maintenance/restore-user-data.sh) | Explicitly restore user data from a compatible archive. Ends running sessions and replaces current data. |

```sh
git pull --ff-only
sudo ./Examples/installation/update-and-check.sh
sudo ./scripts/doctor.sh
sudo ./Examples/maintenance/create-verified-backup.sh

# Inspect recent service logs locally.
sudo journalctl -u win2k-admin -u win2k-sessions -u caddy --since '1 hour ago' --no-pager
```

Normal updates preserve running sessions. For an origin change, legacy installation migration, or a planned session-worker restart, use the options on the canonical [installer](../scripts/install.sh) and [updater](../scripts/update.sh) described in the installation guide.

Backups contain private user information. The installed policy retains seven local archives in `/var/backups/win2k`; running extra backups also applies that retention policy. Store an additional protected copy on another device for disk-failure recovery. Do not commit archives to GitHub or publish service logs without checking their contents.

Restoring is an operation for recovery, not a routine installation step. Read the [recovery instructions](../docs/INSTALLATION.md), select a compatible archive and application version, and then run:

```sh
sudo ./Examples/maintenance/restore-user-data.sh --end-running-sessions /var/backups/win2k/YOUR-BACKUP.tar
```

The underlying restore script validates the archive before replacing state and keeps the previous state on disk. It restores user data; code and system configuration recovery are separate steps in the installation guide.

## Change the nightly backup time

[systemd/backup-at-0200.conf](systemd/backup-at-0200.conf) moves the nightly backup to 02:00 in the Pi's local timezone, plus a random delay of up to 15 minutes. It replaces the original 03:15 schedule.

```sh
sudo install -d -m 755 /etc/systemd/system/win2k-backup.timer.d
sudo install -m 644 Examples/systemd/backup-at-0200.conf /etc/systemd/system/win2k-backup.timer.d/schedule.conf
sudo systemctl daemon-reload
sudo systemctl restart win2k-backup.timer
systemctl list-timers win2k-backup.timer
```

This overwrites `schedule.conf` if it exists; inspect any existing drop-ins first. To return to the packaged schedule, remove that drop-in, reload systemd and restart the timer. Restarting this timer does not restart the session worker.

## Existing templates and UI demo

The canonical [configuration template](../config/config.example.toml), [Caddy template](../server/Caddyfile.template), [frontend service](../server/win2k-admin.service), [session service](../server/win2k-sessions.service), [backup service](../server/win2k-backup.service) and [backup timer](../server/win2k-backup.timer) remain in their installer locations. They define the actual deployed paths and services; examples do not introduce a second deployment implementation.

The older lowercase [examples/standalone](../examples/standalone) directory contains a standalone UI demo. This capital-`Examples` directory contains installation and operations examples.
