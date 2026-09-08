# Caddy and HTTPS for Pi-2000Web

The unified installer installs the Debian `caddy` package, uses the normal `caddy.service` and generates its dedicated configuration from `server/Caddyfile.template`. Network details come from `/etc/pi2000web/config.toml`. No project network address is embedded in the checked-in service files.

The installer currently targets a dedicated Pi/website. It accepts the Debian welcome Caddyfile or its own generated configuration and refuses unrelated existing sites. `--render-dir` creates reviewable files without changing the system.

## Local network: internal certificates

Use `tls = "internal"` with a reserved Pi IP address or a local DNS name. Caddy issues the HTTPS certificate from its local certificate authority. The site name must resolve on both the Pi and the client computer; editing the TOML does not create DNS records or change the Pi hostname.

Caddy automatically manages the local certificate. Clients need to trust its CA. Export **only**:

```text
/var/lib/caddy/.local/share/caddy/pki/authorities/local/root.crt
```

For example, create a readable copy on the Pi:

```sh
sudo install -m 644 /var/lib/caddy/.local/share/caddy/pki/authorities/local/root.crt /tmp/pi2000web-root.crt
```

Copy `/tmp/pi2000web-root.crt` to your viewing computer using an SFTP client such as WinSCP. Inspect the certificate fingerprint on the Pi and compare it with the copied file before trusting it:

```sh
openssl x509 -in /tmp/pi2000web-root.crt -noout -subject -fingerprint -sha256
```

On Windows, import the public certificate into the **Trusted Root Certification Authorities** store for the intended user/computer. Some browsers use their own trust store. On other systems, use their certificate-management tools. You do not need to install a desktop browser on the Pi just to complete this step.

Never copy the private `root.key`, the whole Caddy directory or user browser profiles to a client. If you reinstall and replace Caddy CA state, clients must trust the new CA. Reusing the same existing CA avoids that during ordinary updates.

See Caddy documentation on [automatic HTTPS](https://caddyserver.com/docs/automatic-https) and [running with systemd](https://caddyserver.com/docs/running).

## Domain name: public certificates

Use `tls = "public"` and a public DNS hostname in `public_url`. Caddy automatically requests and renews the certificate. The installer deliberately supports public certificates for DNS names only; use internal mode for IP-based LAN installs.

Configure DNS to reach your server. For standard HTTP/TLS certificate validation, inbound port 80 and/or 443 must be reachable as required by the selected challenge; this installer uses Caddy defaults. NAT forwarding, firewall configuration and DNS are outside the installer. DNS-based certificate challenges require additional Caddy DNS modules and credentials and are not implemented by this installer.

The Pi must be able to resolve and reach its own public URL for the post-install HTTPS check. Networks without NAT loopback may need split DNS pointing that name to the Pi LAN address. Set this up before installation.

Having a valid public certificate is not a security assessment of the application. Review the Alpha limits before enabling internet access. See [Caddy automatic HTTPS requirements](https://caddyserver.com/docs/automatic-https).

## Generated configuration

The site serves `/srv/win2k` and proxies `/api/*` to `127.0.0.1:8765`. Caddy handles HTTP-to-HTTPS redirects automatically. The application uses the exact HTTPS origin from the same configuration to validate requests.

Caddy administration uses `unix//var/lib/caddy/win2k-admin/control.sock`, in a private mode-0700 directory owned by `caddy`. Do not expose TCP port 2019. Browser sandboxes share the host network namespace, so a loopback-only TCP admin port is not a suitable isolation boundary. See [Caddy administration](https://caddyserver.com/docs/api).

The configured `bind_address` limits listening to a local IP. Leaving it empty allows all interfaces and does not restrict who can connect. No firewall rules are created automatically.

## Existing Caddy sites or another reverse proxy

Do not run the automatic installer over a Caddyfile serving other applications. It will stop before replacing an unrecognised file. A generated marker does not permit appending unrelated sites and then allowing the updater to overwrite them; such extra content is also rejected.

To review a candidate:

```sh
./scripts/install.sh --config pi2000.toml --render-dir .install-plan
caddy adapt --config .install-plan/Caddyfile --adapter caddyfile --pretty
```

Manual integration must preserve all existing sites, the private administration boundary, same-origin embedding and the exact application origin. The unified updater manages a complete dedicated Caddyfile; it is not a shared-site merger. A separate Pi is the supported automatic path. A shared reverse-proxy installation requires a separately maintained deployment process rather than bypassing the ownership check.

For an original Pi-2000Web installation with its known single-site Caddyfile, `--adopt-existing` enables a narrow compatibility migration. It checks the whole expected configuration, not just the occurrence of the application directory name.

## Troubleshooting

- **Unknown CA in the client browser:** trust the public root certificate from this Pi. Do not disable TLS verification as the normal setup.
- **Hostname does not resolve:** use the reserved LAN IP or configure local/public DNS before installation.
- **Address already in use:** inspect `sudo ss -ltnp`; resolve the other service or use a separate host.
- **ACME/certificate error:** inspect `sudo journalctl -u caddy`; verify DNS and validation reachability.
- **Origin error after changing address:** update the installed TOML and rerun `update.sh --restart-sessions`, then open the exact configured URL and log in again.
- **Different assets in doctor:** make sure the checkout matches the deployed version and run `update.sh`; check any external cache or reverse proxy.

The installer uses the distribution package to keep Caddy updates under apt. Caddy also documents its own upstream package repository in [the installation guide](https://caddyserver.com/docs/install); changing package sources is an administrator choice, not a hidden step in this installer.
