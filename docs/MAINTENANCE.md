# Build activation and deployment

This describes development changes after Alpha 5. About Pi-2000Web and System
Status show the installed build separately from the builds captured at startup by
the API, session worker and Arduino worker. A pending update means files have
changed while the process still runs its previous build. An older worker that
cannot report this protocol is shown as unknown, never assumed up to date.

Source and package updates preserve the session and Arduino workers. New worker
code becomes active when the worker is restarted during suitable maintenance.
Existing SSH/Browser work and Arduino jobs must not be terminated for convenience.
A web administrator cannot restart host services.

An OS administrator can inspect or activate one idle worker:

```sh
sudo pi2000web workers status
sudo pi2000web workers restart-idle sessions
sudo pi2000web workers restart-idle arduino --wait 60
```

For source installations use `./scripts/workers.sh` instead of
`pi2000web workers`. The helper takes a leased drain lock on the private Unix
socket, rejects new work, checks current work and restarts only an idle worker.
Existing sessions/jobs can continue while draining. A busy refusal resumes new
work admission. If the helper disappears, admission resumes after the 120-second
lease expires. The wait option renews the lease while waiting. Post-restart checks
verify that the worker reports the installed build. Idle activation still closes
idle worker processes; it is not migration of processes or compiling jobs.

Workers predating this protocol require a planned manual maintenance window to
activate it for the first time. The helper refuses to infer their idle state.
Do not use the source updater's explicit `--restart-sessions` option while users
have jobs: that existing option deliberately terminates sessions.

## Module-aware deployment

`deployment.json` is the source file inventory shared by source publishing and
Debian packaging. Installed `deployment-server.json` and `deployment-web.json`
contain SHA-256 hashes. Backup consumes those installed inventories, so nested
Python packages survive packaging and backup. Legacy installations use a bounded
compatibility inventory until updated.

Deployment stages and verifies a complete component before modifying installed
files. Activation preflights destination paths, replaces files individually and
publishes the web entry page after assets. It is not a whole-directory atomic
switch: an I/O failure during activation needs installer diagnostics and repair.
Only stale files tracked by the preceding inventory are removed; unrelated files
and user data are preserved. `build-info.json` is retained separately because
frontend-only publication updates global build metadata without restarting workers.

Private notes, credentials, databases, hidden files, development dependencies,
bytecode, logs and symlinks are excluded. Add application modules under `server/`
or explicitly extend the manifest for new supported runtime file types; do not
add broad globs for private directories. Doctor verifies installed inventories.

See [recovery](RECOVERY.md) and [reproducible tests](TESTING.md). Fresh installation,
real account recovery and hardware checks on the test Pi remain separate acceptance
steps; local fixture checks and a package build cannot substitute for them.
