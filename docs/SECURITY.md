# Security boundaries and review

Pi-2000 is a development desktop for a trusted operator and separately authenticated
users. It is not certified for financial systems or unrestricted hostile hosting.
A review and passing tests reduce specific risks; they do not establish that no
exploitable vulnerability exists. OWASP ASVS is a useful verification reference,
not a certification this project has obtained.

## Account and operator boundaries

Every private object lookup uses the authenticated account ID. Web administrator
status does not grant an API for reading another account's files, drafts, Pi-Vault,
SSH profiles, API collections, Git projects or database connections. The creator
controls roles. The root account broker separately protects the creator binding
and permits fixed operations on managed Linux identities; it does not accept shell
commands or arbitrary account paths. A web role does not grant sudo.

Administrators who can reset another account's login password can impersonate that
account after resetting it. OS administrators can read ordinary server data and
replace the delivered application. Those are administrative trust boundaries,
not protections provided by the object API. Pi-Vault passphrases remain separate
from login resets, but an actively malicious server can change the JavaScript
used to unlock Pi-Vault. See [Pi-Vault](VAULT.md).

Cookies are Secure, HttpOnly and SameSite=Strict, with a twelve-hour absolute
expiry. Mutations and terminal WebSockets require the configured Origin. Account
changes invalidate sessions; pending writes recheck authorization after reading
their body. Login/password work is rate/concurrency limited. Up to twelve login
sessions per account are retained; a new login expires the oldest excess logins
without terminating their detached SSH jobs. There is currently no MFA/passkey or
idle-session reauthentication policy.

## Hardening reviewed on 2026-09-18

The review covered the authentication/account broker, object ownership routes,
file and archive handling, Browser/Git/Arduino isolation, SSH/SFTP, database and
phpMyAdmin bridges, request limits, Pi-Vault cryptography, client HTML sinks,
installation/recovery code and dependency inventories. Focused adversarial tests
use disposable local state. They never attack another person's service or read
production user data.

| Finding or control | Change and evidence |
| --- | --- |
| Browser supervisor wrote a log inside a sandbox-writable profile | Reproduced a planted symlink truncating a temporary host-side marker. Logs now use an atomically replaced file in a separate directory which is not mounted into Browser. |
| Pi-Vault password/recovery changes reused data keys | Demonstrated old data keys decrypting later content. Both data keys, salts and Pi-Vault ID now rotate; all entries are authenticated and re-encrypted before a single conditional save. Tests cover preservation, old-key rejection and corrupt-entry failure. |
| Mutable backup paths could change between metadata checks and root reads | User-controlled trees now use descriptor-relative traversal with `O_NOFOLLOW`, inspect the opened inode and archive that same file descriptor. A deterministic directory-swap test cannot include an outside marker. |
| phpMyAdmin retained a session object across a slow POST | Disconnect and connection changes are rechecked after the body and before returning results. A revoked/replaced session cannot submit that pending request to PHP. Connection admission and timeouts are bounded. |
| Unbounded live login sessions and request admission | Twelve logins per account; sixteen active HTTP/WS handlers per account, eight unauthenticated login handlers, sixty-four total per process. Excess handlers receive 429. A slow-account test confirms another account remains usable. |
| Encoded or malformed input and stalled body streams | Automatic request decompression is disabled. Encoded requests receive 415; deep/mistyped JSON receives 400; streamed bodies have a thirty-second idle timeout. Existing per-route size/quota limits remain enforced. |
| Browser engine lagged current published security fixes | New Browser starts require Chromium 153.0.8010.52 or newer. The API checks before forwarding to a retained older worker. Failure or unknown version blocks start; there is no web override. This minimum is a dated known-fix floor, not ongoing vulnerability detection. |
| Response and operational visibility | Caddy adds HSTS, a header CSP for the desktop and a Permissions Policy. API errors/streams receive no-store and nosniff. Selected login/password/account operations produce fixed event names, numeric IDs and status in the service journal, without credentials or document content. |

The four-account matrix includes the creator, another administrator and two regular
users. It probes foreign file reads/writes, SSH profiles, API collections, database
profiles, Arduino projects and Pi-Vault owner substitution. Both administrator roles
must obey the same object boundaries. Existing tests also exercise Git sandboxing,
SSH host-key pinning, rejected platform/metadata URLs, safe inert file previews,
ZIP traversal, SQL parameter handling, quotas and session revocation.

Run the checks described in [TESTING.md](TESTING.md), including
`test_security_hardening.py` and `security_crypto_ui.cjs`. Deployment and installed
validation are separate from passing source tests. Browser supervisor changes need
worker activation; the API engine floor protects new Browser access during a
rolling update which retains SSH sessions.

## Dependency and host checks

The dated review queried Python advisories with pip-audit and checked npm plus all
five vendored JavaScript package versions through OSV. No advisories were returned
for the 37 recognized pinned Python packages or those JavaScript versions. The
source-pinned Selkies development build cannot be evaluated as a published PyPI
release and requires separate source/upstream review. Static analysis findings
were inspected; heuristics alone do not demonstrate an exploit or prove absence.

Distribution security results must be reconciled with the actual Debian/Raspberry
Pi source and patch history. Raspberry Pi version epochs and backports can make a
numerically newer security build lose normal APT candidate selection or produce
misleading generic scanner matches. Do not blindly downgrade OpenSSL, replace the
kernel, or treat an empty `apt upgrade` as proof of current browser security.
The operator must maintain OS, Chromium, PHP, MariaDB, SSH and third-party runtime
updates in addition to the application. Browser remains paused if the available
trusted package has not reached the reviewed floor; saved profiles are retained.

References: [OWASP ASVS](https://owasp.org/projects/asvs),
[session management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html),
[key rotation](https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html),
[Chromium September 17 security update](https://chromereleases.googleblog.com/2026/09/stable-channel-update-for-desktop_0194356994.html),
[Debian Chromium tracker](https://security-tracker.debian.org/tracker/source-package/chromium).

## Remaining boundaries and requirements for higher assurance

- Browser and Git network access, SSH/SFTP and SQL tools intentionally reach
  operator-selected networks/services. Filesystem sandboxes do not isolate the
  host network. Untrusted tenants need separate hosts/VMs or enforced network
  namespaces/egress policy, not just this desktop's account roles.
- Requests have bounded application resources, but this is not a volumetric-DDoS
  defense. Use a private network/VPN and an appropriate network boundary. Ordinary
  host SSH and unrelated OS services are separate from Pi-2000's HTTPS listener.
- Ordinary files, drafts and saved connection secrets are accessible to the server
  service identity. Saved database/API credentials use a server-held key; this
  does not protect against host compromise or disk theft. Consider encrypted disks,
  separated key management and a stronger tenant execution boundary.
- Higher assurance requires MFA, privileged-action reauthentication, durable remote
  audit collection/alerting, an incident response process, and tested off-device
  encrypted backups. A local journal is not tamper-proof; local snapshots are not
  protection against losing the whole Pi/storage device.
- An independent penetration test and cryptographic review, sustained dependency
  monitoring and regular restore exercises remain necessary. This review did not
  prove kernel/browser-engine exploit resistance, perform a physical power-cut
  test, certify a fresh Pi4 installation or establish regulatory compliance.

Report suspected issues privately to the operator first. Do not include credentials,
real user documents or unlocked Pi-Vault contents in issue reports or public logs.
