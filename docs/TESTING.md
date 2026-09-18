# Reproducible checks

Run checks as an ordinary user on Debian 13 with Python 3.13 and Node.js.
Native test dependencies: Chromium, bubblewrap, MariaDB server tools, Git,
OpenSSL, age, iputils-ping, iproute2, PHP CLI, Xvfb, x11-xserver-utils and Caddy. Tests create disposable databases and SSH
servers; they do not use the installed MariaDB database or real web accounts.
Bubblewrap requires working unprivileged user namespaces. A restricted container
must enable those namespaces; do not silently skip isolation tests.

```sh
python3 -m venv .venv
.venv/bin/pip install -r server/requirements.txt
npm ci --ignore-scripts
.venv/bin/python scripts/check.py
```

The one-command default runs all backend tests, both geometry suites and the
ordinary UI suite listed in `tests/suites.json`, including desktop management, Vault, Pi++, Arduino and all
five utility tools. Playwright is an exact development dependency in package.json
and package-lock.json; no production Node dependencies or runtime framework are
introduced. Chromium comes from the test host; `WIN2K_TEST_CHROMIUM` can select an
explicit binary. The distribution browser version is part of the host setup,
not pinned by the npm lockfile.

Use `scripts/check.py backend`, `ui` or `geometry` for a focused check. UI tests
run sequentially, each with an OS-allocated listening socket, temporary state,
private SSH fixture and its own `.test-results/ui-*/TEST/` logs/screenshots.
Independent UI runs do not share a fixed port or SFTP folder. Test artifacts are
ignored by Git and excluded from installation/backup application inventories.

Explicit integration checks:

- `scripts/check.py database`: disposable MariaDB plus graphical database tests.
- `scripts/check.py network`: first-use Arduino catalog/library downloads; needs
  the pinned Arduino CLI and internet access. Never run this by default in CI.
- ESP32 compiler checks can supply `WIN2K_ARDUINO_CLI` and a disposable
  `WIN2K_TEST_ARDUINO_RUNTIME` to `tests/run_classic_suite.py arduino_ui.cjs`.
  Never share a mutable runtime between simultaneous tests.
- Installed PAM, service resource limits and real USB/sensor/display checks remain
  explicit host/hardware acceptance. They are not replaced by mock or PTY tests.

The GitHub workflow runs the default checks in Debian 13 as an unprivileged user,
with read-only repository permissions and no production credentials. It runs
when this workflow is published and on subsequent pushes/PRs; creating its file
locally is not evidence of a successful GitHub run. The container needs nested
user namespaces for sandbox verification. The setup follows the official
[GitHub container-job documentation](https://docs.github.com/en/actions/how-tos/write-workflows/choose-where-workflows-run/run-jobs-in-a-container)
and [Playwright CI guidance](https://playwright.dev/docs/ci).

## Workspace recovery

`workspace_recovery_ui.cjs` owns a disposable persistent fixture. It creates four
accounts, edits application content, kills that server with SIGKILL, starts it
again on the same state directory, and signs in from fresh browser contexts.
It checks private drafts, Arduino source, drawings, calculator/layout, terminal
reconnect, locked Vault, failed reads/writes and stale-tab conflict handling.
This verifies abrupt application-process death and durable state recovery; it
is not a physical power-cut or filesystem-corruption test. No production server
is killed.

## Security regression fixtures

`tests/test_security_hardening.py` checks a sandbox-profile log link, descriptor-based
backup traversal during a directory swap, four-account object isolation including
administrators, revoked phpMyAdmin requests, encoded/deep/mistyped bodies, bounded
login/request admission, slow-account isolation, body timeouts, safe audit fields
and the minimum Browser engine policy. `security_crypto_ui.cjs` uses the actual
Web Crypto/Argon2 implementation to prove password/recovery rotation rejects old
data keys, preserves every entry and fails without replacement on corrupt content.

The browser-engine policy is mocked only in cold-start/filesystem unit fixtures;
it is not bypassed by any production environment variable or web preference.
Ordinary UI tests visit only the disposable local application, even when the test
host's browser package is older than the production Browser security floor.

Separate dependency checks can use a disposable pip-audit/bandit environment,
`npm audit`, the OSV API for `assets/vendor/versions.json`, and Debian's security
tracker. Record skipped/unrecognized packages and distribution backport caveats.
Do not run destructive exploit probes against installed accounts to obtain a
passing test. Installed validation uses newly created disposable accounts only.

After installation, the operator can run
`sudo /opt/win2k-admin/venv/bin/python tests/verify_installed_security.py` from the
checkout. It creates and removes four real PAM test accounts, checks HTTPS headers,
anonymous/compressed requests, cross-account file/Vault boundaries and the installed
Browser version gate. Generated passwords and the temporary operator token stay in
memory. It does not open real users' documents or start an external Browser session.

## IPTV media fixtures

`test_iptv.py` includes per-account/credential boundaries, pinned public-network
checks including redirects, bounded M3U/XMLTV/streaming JSON parsing, catalogue
replacement, HLS rewriting, Xtream series/archive and actual network-isolated
FFmpeg conversion. `iptv_ui.cjs` generates local H.264/AAC media, plays HLS/TS/MP4
through the production gateway, verifies decoded audio/video and tests the UI,
recovery and account-safe URLs. The fake provider is injected only by the test
fixture; production has no private-network bypass. FFmpeg is required for these
tests. Real-provider availability and installed PAM/HTTPS verification are separate.

`iptv_stability_ui.cjs` adds a timed live TS fixture (1.2 Mbit/s, 2.5 seconds of
network interruption), asserting decoded audio/video without stalls or catch-up
seeks and cancellation of buffered startup after Stop. Run both player suites:

```sh
python tests/run_classic_suite.py iptv_stability_ui.cjs iptv_ui.cjs
```

`WIN2K_TEST_BASELINE=1` records stall/seek metrics without their zero assertions
when comparing older playback settings. This switch affects only the test.

The GitHub job uses an Ubuntu 22.04 host with a Debian 13 container. Newer Ubuntu
hosts restrict unprivileged user namespaces through AppArmor and can reject
nested Bubblewrap UID maps even with an unconfined container profile. A dedicated
sandbox preflight must pass before the tests run; isolation tests are never skipped
to hide a host policy failure. This affects the disposable CI host, not Pi settings.
