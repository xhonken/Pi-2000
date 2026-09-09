# Alpha 3 stabilization

## Local verification

The current stabilization changes have passed:

- 87 backend tests, including two ordinary accounts, owner access denial,
  encrypted request restoration, Git files and SQL drafts from an isolated
  restored state, SQLite integrity and invalidated old login tokens.
- Real smart-Git HTTPS clone/fetch/pull/push and diverged-push rejection against
  a disposable TLS server. Anonymous public GitHub clone/fetch/pull also passed
  through the sandboxed API. No hosted repository was modified by these tests.
- Packaged phpMyAdmin running in disposable PHP/MariaDB state: SQL, browse,
  insert, import/export, protected paths and revocation, with no dependency
  notices rendered on the exercised full pages and AJAX views. Actionable
  PHP warnings are explicitly verified to reach the previous error handler.
- Native MariaDB suites; unsaved API/Git regressions; editor, SFTP, files,
  drafts/notes, menus, large fonts, accessibility and English UI suites.

These are checkout tests, not proof that the new code is installed.

## Installed verification

Finish database operations before an update. From the development checkout:

```sh
sudo /opt/win2k-admin/venv/bin/python tests/verify_installed_stabilization.py --update
```

This runs the normal updater and doctor, then uses a disposable ordinary account
for trusted HTTPS health/build checks and a temporary Browser session to inspect
actual cgroup memory limits. It then uses an unprivileged, disposable MariaDB
server for the installed phpMyAdmin UI regression. The account is removed in
cleanup. Existing user tables are not used. The persistent SSH/Browser worker is
not restarted. Dependencies: the developer virtual environment, Node, Chromium
and Playwright at the location used by the existing UI suite.

Omit `--update` to run verification against the already installed matching checkout.
Do not put passwords or tokens in command lines or this document.

## Remaining physical recovery checks

A staged restore and an application started from restored data are covered above.
A complete recovery after losing the host remains unverified until an independent
backup device and spare Pi are available.

1. Identify the intended external mount and verify that it is a different device
   from the system disk. Use a private directory; do not format a disk as part of
   this procedure.
2. Create a verified local snapshot, copy it and its checksum to that device, and
   verify the copied checksum. Platform snapshots do not back up every MariaDB
   server reachable through saved profiles: back up those databases separately.
3. Extract into a new empty private staging directory, validate SQLite and
   ownership, and exercise restored files, credentials and profiles in isolation.
4. On the identified spare Pi/test card, verify the supported OS/architecture and
   follow the normal installation guide. Exercise first login, HTTPS trust,
   phpMyAdmin, file operations, Git, Browser limits and backup/restore.
5. Record device/OS details and observed results in private project notes. Do not
   mark physical Pi 4 support or full disaster recovery as verified from the
   development Pi's tests.

Optional phpMyAdmin metadata storage must be scoped to the connected database
account; consult [phpMyAdmin integration](PHPMYADMIN.md). The updated
[development roadmap](DEVELOPMENT-ROADMAP.md) distinguishes the embedded upstream
application from the retained native SQL workspace.
