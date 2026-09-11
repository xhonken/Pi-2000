# System accounts

Pi-2000 uses Linux-PAM for migrated web accounts. SQLite stores web identity, role, creator status and private application resources. A separate root service owns `/var/lib/pi2000-accounts/accounts.sqlite3`, binds web IDs to Linux names/UIDs/homes, and permits only fixed account operations over a restricted Unix socket. The web API and session worker remain unprivileged. PAM performs authentication and account validity checks. Password changes use PAM; initial provisioning uses `chpasswd` with standard input, never command-line passwords.

## Accounts and permissions

| Account | Web | Local Terminal | Host SSH / console | Sudo |
| --- | --- | --- | --- | --- |
| Managed ordinary user | Enabled | Denied | Denied by host SSH group policy and nologin shell | None |
| Managed administrator | Enabled | Own Linux identity | Host SSH denied; Linux console login possible | None by default |
| Creator | Enabled, protected role | Own Linux identity | Same policy as administrator | None by default |
| Explicitly linked existing Linux user | According to web status | Admin role only, existing local SSH | Existing OS permissions preserved | Existing OS permissions preserved |

Managed usernames are generated from the stable web ID (`pi2k_ID`). Homes have mode 0700. The private SSH listener uses `127.0.0.1:2222`, password authentication, pinned local host keys and the `pi2000-terminal` group. Forwarding and user SSH startup scripts are disabled. The host listener excludes `pi2000-users`. Do not remove that exclusion when modifying host SSH policy.

The creator flag is independent of the username. The creator cannot be renamed, deleted, disabled or demoted through the web API. Only the creator can change roles or administer another administrator. Web password resets cannot change the creator's password or any linked Linux account's password. Linked users change passwords locally with `passwd`.

New passwords require at least 12 characters and at most 512 UTF-8 bytes. No plaintext passwords are retained. After migration the web salt/hash fields are empty; retained older backups can still contain old verifiers. MariaDB credentials remain independent encrypted connection secrets after initial setup.

## Installation and migration

The Debian dialog asks for the creator username and confirmed password. It creates the creator's Linux identity and initial private MariaDB connection. It does not grant sudo. A package upgrade preserves the creator and existing resources.

Legacy web users migrate on their next successful login, using the password they entered. A migrated account never falls back to the old web verifier if PAM rejects authentication or the broker is unavailable. An old password outside the new password policy requires an administrator reset before migration. The account list shows pending migration and the Linux identity after migration.

To explicitly link an existing Linux identity, run as the OS administrator **before that web account is migrated**:

```sh
sudo /opt/win2k-admin/venv/bin/python /opt/win2k-admin/account_service.py link --web-id WEB_ID --linux-user EXISTING_USER
```

This changes web login to the existing Linux password and revokes previous web sessions. It preserves the OS password, home and permissions. It will not infer a link from matching usernames, replace an existing binding, or link a system UID. Linked local terminals currently use the existing SSH listener on loopback port 22.

## Disable, delete and recovery

Disable preserves data and prevents web access. For managed identities it expires the Linux account, removes terminal membership and stops that UID's processes. Demotion similarly removes terminal membership and ends local processes. Linked identities lose Pi-2000 access only; their unrelated OS sessions remain intact.

Permanent deletion requires typing the exact web username. Managed Linux identities and their specific home are removed; private application data is removed separately. Existing linked Linux identities/homes are preserved. External databases, backups and files created elsewhere on the machine are not deleted. Review ownership outside the managed home before reusing deleted UIDs.

Creation is recorded as pending and inactive until OS provisioning completes. Retry New User with the same username to finish a pending account, or delete the pending account. No arbitrary existing Linux account is adopted. A crash precisely after `useradd` but before its UID is recorded requires root to inspect and explicitly recover that reserved identity:

```sh
sudo /opt/win2k-admin/venv/bin/python /opt/win2k-admin/account_service.py recover --web-id WEB_ID --linux-user pi2k_WEB_ID
```

Then retry account creation or the legacy login. If a recorded UID/home changes unexpectedly, authentication is rejected for OS administrator investigation. Do not edit the registry from the web service account.

Password/account record changes outside Pi-2000 are detected every five seconds using a root-only keyed fingerprint, revoking web sessions and asking the worker to stop that user's jobs. Restarting the broker preserves the fingerprint. A temporary worker failure still invalidates cookies; inspect and stop retained jobs before returning the worker to service.

## Backups and validation

Local root-only archives include the binding registry, generation key, managed password recovery records and managed homes. Linked account password records/homes are excluded. Archive staging restore verifies both SQLite databases. Restores do not automatically overwrite OS users or `/etc/shadow`: an OS administrator must reconcile UIDs and homes before enabling a restored account. As with existing file snapshots, running background processes are not checkpointed; stop writers for a consistent home snapshot. Special files and symlinks are excluded by the existing archive safety filter; executable modes and original file ownership are not restored automatically.

Automated unit tests cover creator identity across restart, SQL protections, UTF-8 password limits and UID mismatch rejection. `tests/system_accounts_live.py` is an **explicit root-only** integration test using disposable high-ID accounts: five distinct UIDs/homes, PAM login and password changes, ordinary-user denial, admin SSH terminal, host SSH denial, no sudo, disable/reset/re-enable, creator protections and confirmed deletion. It cleans up only its generated fixture accounts. Fresh installation on a reinstalled test Pi remains a separate acceptance step.

Implementation references: [Linux-PAM application interface](https://github.com/linux-pam/linux-pam/blob/master/libpam/include/security/pam_appl.h) and [OpenSSH server configuration](https://man.openbsd.org/sshd_config).
