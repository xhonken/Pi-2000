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
ordinary UI suite listed in `tests/suites.json`, including Pi++, Arduino and all
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
