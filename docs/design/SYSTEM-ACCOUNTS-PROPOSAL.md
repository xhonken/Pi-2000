# System accounts and authentication proposal

Status: approved design, implementation added 2026-09-11. The investigation below records the original baseline and intended design. See [current behavior and recovery](../SYSTEM-ACCOUNTS.md) for implementation details, differences and verification.

## Recommendation

Use one dedicated Linux identity per Pi-2000 user and Linux-PAM as the authority for web/Linux passwords. Keep application identity, roles, creator protection, quotas, preferences and resource ownership in SQLite. Do not retain a second application password verifier after a user migrates to PAM. SQL connection credentials remain a separate concern.

## Original baseline before implementation

- `server/app.py`: creation adds only a SQLite user. Web passwords use salted scrypt; password changes update that verifier and revoke sessions.
- Creator/owner checks and SQLite protection triggers currently depend on the literal username `admin`.
- `server/local_terminal.py`: every web administrator receives the same OS-managed Linux username. Terminal objects have separate web owners, but their Linux processes share the configured UID.
- `packaging/provision.py`: initial provisioning can create a Linux account, but it does not provision one for each subsequent web user.
- `server/win2k-admin.service`: the API runs as `win2k-admin` with `NoNewPrivileges` and filesystem restrictions. Preserve this boundary.

## Authentication alternatives

| Alternative | Benefit | Cost / failure mode |
| --- | --- | --- |
| Separate web and Linux hashes, same chosen password | Smallest initial change to web login | SQLite and the system account database are not one transaction. Password changes, resets, external `passwd` calls and partial failures can leave different passwords. Both copies must be protected. |
| PAM-backed web authentication | One password authority for web login, local terminal and Linux tools | Requires a carefully scoped privileged service, explicit account eligibility, PAM account checks, password-change support and session invalidation. PAM availability becomes a login dependency. |

Neither design stores plaintext passwords. In the recommended local `pam_unix` configuration the system stores the verifier in `/etc/shadow`; Pi-2000 does not copy or read that verifier. Password input is necessarily transient during authentication or change, and must not enter logs, argv, queues or persistent retry records. PAM can use other backends; this proposal initially supports local managed accounts only. [Debian authentication reference](https://www.debian.org/doc/manuals/debian-reference/ch04.en.html), [pam_unix](https://man7.org/linux/man-pages/man8/pam_unix.8.html).

PAM authentication must include account validity checks, not just password matching. Handle expired/disabled accounts and password-change-required responses explicitly. Use PAM's password-change operation for ordinary self-service changes. Test the deployed module's length/encoding limits against the existing web limit of 1024 characters; do not silently truncate passwords. [pam_acct_mgmt](https://man7.org/linux/man-pages/man3/pam_acct_mgmt.3.html), [pam_chauthtok](https://man7.org/linux/man-pages/man3/pam_chauthtok.3.html).

A password change through Pi-2000 revokes existing sessions according to an explicit policy. A change through Linux `passwd` affects subsequent authentication automatically, but does not by itself invalidate an existing Pi-2000 cookie. Add bounded periodic validity checks and a credential-generation mechanism for external changes. Its implementation must be validated in the prototype; PAM is not automatic web-session revocation.

## Identity and creator protection

Bind stable web user IDs to unique Linux UIDs and names. Keep a root-owned registry of which accounts Pi-2000 created, their UIDs, managed home paths and creator identity. Names alone never authorize account modification; recheck the UID to detect deletion/recreation outside Pi-2000.

For newly created accounts, use reserved generated Linux names such as `pi2k_1042`, while retaining a human-friendly web username. This avoids existing service account collisions and the different web/Linux username limits. Display the local username in account details and the terminal dialog. Home directories are private (0700) by default. A shell does not constitute a sandbox: ordinary shared/public OS resources remain accessible according to Linux permissions, and full sudo overrides file isolation.

The installer chooses the initial web login name/password, creates its Linux identity and records one immutable creator ID. Show `Creator` separately from the admin role. The creator cannot be deleted, disabled, demoted or replaced through web APIs, including by itself. Enforce this in API validation, database constraints and the privileged registry, not only hidden buttons. Recovery/ownership transfer must be an explicit OS-admin procedure. Creator status is independent of whether passwords use PAM.

On upgrade, preserve the existing protected owner as creator. Do not silently transfer ownership to another administrator or infer ownership from the current Linux login. Existing Linux accounts require an explicit link and remain externally managed/protected unless separately adopted through a reviewed OS-admin operation. In particular, web deletion must never remove a pre-existing host administration account.

## Account lifecycle and access

| Action | Proposed behavior |
| --- | --- |
| Create web user | Reserve web identity as pending; create its managed Linux account and private home; set the password through protected IPC; record the binding; activate only after all steps succeed. |
| Ordinary user | Web access enabled. Local Terminal, host SSH/console shell access and sudo denied by default. The Linux password must still work for the dedicated web PAM service. |
| Promote to admin | Enable Local Terminal against that user's own UID. Preserve private per-web-user sessions. No automatic sudo grant. |
| Demote admin | Revoke web sessions and end local shells; remove managed shell access without disabling web password authentication. |
| Disable | Deny new web and managed system logins, revoke cookies, close terminals and stop owned jobs; preserve identity and data for reactivation. |
| Permanently delete | Disable first; present exact affected managed resources; require explicit confirmation; remove managed account/home and active application data; retain a minimal audit record. |

Web access, Local Terminal, external SSH/console access and sudo are distinct permissions. For the first version, recommend ordinary users have web access only and admins additionally have Local Terminal. Prototype a dedicated loopback-only SSH endpoint/PAM policy for Local Terminal and narrowly scoped rules for managed accounts on host SSH and console services. Preserve existing host access. Merely hiding the app, using a general `nologin` shell everywhere, or locking the password is insufficient: the web PAM service must still authenticate eligible web-only users. OpenSSH supports group-based login policy, but changes must be tested against the actual Raspberry OS configuration. [OpenSSH sshd_config](https://man.openbsd.org/sshd_config).

Full sudo remains a separately granted OS privilege. The web account service must not offer arbitrary group membership or unrestricted sudoers editing. A web admin capable of resetting an OS-privileged user's password could take over that OS privilege; password-reset rules must therefore protect creator, peer administrators and externally privileged accounts. Prefer owner-controlled elevation through an OS-admin operation for the initial implementation.

`Disable` should be the default removal choice. Add `Delete permanently…` with the account name, data scope and typed-name confirmation. Administrators may manage ordinary users; only the creator manages other administrators. Preserve the creator in every path.

A password lock is not a complete account disable. The system account policy and live sessions must also be handled. Linux `userdel -r` does not remove every user-owned file from every filesystem; backups and external databases need separate retention/ownership policies. Do not promise secure erasure or delete external resources just because a saved connection belongs to the account. [usermod](https://www.man7.org/linux/man-pages/man8/usermod.8.html), [userdel](https://www.man7.org/linux/man-pages/man8/userdel.8@@shadow-utils.html).

For externally linked accounts, disabling/removing the web account affects Pi-2000 access only by default; the existing OS account is protected. The UI must label this exception explicitly.

## Privileged service and failure handling

Implement a small root-owned account service over a permission-restricted Unix socket. The web API stays unprivileged and does not join the shadow group. Give the service a fixed operation vocabulary, bounded requests, peer credential checks and independent target validation. It must reject root, service identities, foreign UIDs, arbitrary paths/commands/groups and attempts to change the creator. A compromised API remains a threat even with a helper: do not claim peer-UID checks authenticate individual web actors or grant the helper unlimited host administration.

Use a Pi-2000-specific PAM service; do not rewrite system-wide common PAM stacks. Account provisioning and SQLite writes are a recoverable workflow, not one atomic transaction. Record operation IDs and pending/error states without passwords; serialize conflicting operations, make retries idempotent and require password re-entry where needed. Never expose a half-provisioned account as active or reuse an unverified pre-existing identity.

Deletion must stop processes before removing managed resources, validate UID/path ownership again and avoid symlink traversal. Account names/UID reuse and files outside the managed home need explicit safeguards. Backup/restore must preserve or deliberately remap UIDs, creator identity and registry data before enabling logins.

## Migration and MariaDB

Existing web scrypt hashes cannot be converted back into passwords. Keep an explicit legacy authentication mode only during migration. For a new managed Linux identity, successful legacy login can supply the entered password for one-time provisioning; alternatively use an owner-guided reset. Activate PAM and remove the legacy verifier only after provisioning succeeds. Never fall back to the old web password after a PAM failure for a migrated account.

Linking an existing Linux identity requires verification and acceptance of its current system credential. Do not overwrite it with the old web password. Keep an independent OS recovery route until creator migration and restore tests pass.

MariaDB login credentials are currently stored separately as encrypted connection secrets. PAM-backed web login does not automatically change MariaDB authentication. Preserve existing SQL credentials in this migration. A future per-user database provisioning design should preferably use separate generated SQL credentials; do not add implicit password synchronization to a third system.

## Implementation and verification sequence

1. Prototype dedicated PAM authentication, account checks, password changes and managed-user lifecycle on the test Pi. Confirm ordinary users can log into the web while shell access stays denied.
2. Introduce creator ID and root-owned account registry with tests for forged requests, name collisions, UID replacement, partial failures and recovery.
3. Connect create/promote/demote/disable/delete UI and APIs; bind Local Terminal to individual accounts. Test five administrators with distinct UIDs/homes and no cross-session or cross-home access without sudo.
4. Test password changes both through web and `passwd`, expired accounts, old-cookie revocation, SSH keys after disable, active-job shutdown and backup/restore.
5. Validate new `.deb` setup, upgrades, removal/reinstallation and account/data retention. Migrate an existing installation without changing unrelated host accounts.
6. Take a verified backup and migrate the user-facing Pi only after the test-host gates pass. Creator recovery must be tested before discarding legacy verifiers.

Decision still needed before implementation: accept PAM as the final authority; generated managed Linux names; and the default policy of local terminal for admins with separately controlled sudo. These are recommendations, not changes already applied.
