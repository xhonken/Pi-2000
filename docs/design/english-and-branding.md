# English interface and Pi-2000Web branding — 2026-09-08

The maintained desktop UI, application dialogs, accessible names, status/error messages, installer output and project documentation now use English. The login page, page title, Start menu and systemd descriptions use Pi-2000Web. Chromium is configured with `--lang=en-GB` for newly started browser sessions. Existing external websites and user-authored content retain their own language.

File and Edit menu mnemonics changed to Alt+F and Alt+E. Menu definitions and their underlying toolbar commands were updated together. Generated ZIP, SVG and CSV download names and CSV headings use English. Locale formatting uses en-GB.

Compatibility identifiers remain unchanged: installed `win2k` paths/services, `WIN2K_*` configuration, browser profiles, cookies, stored account/document keys and JavaScript namespaces. No data migration or user-content translation is performed. The original upstream gallery is retained separately under `reference/gallery/` as an unmodified historical reference and is not installed.

## Verification

- 45 backend integration tests passed.
- Geometry and arithmetic checks passed.
- Browser regressions passed for batch files, personal tools, drawing/calculator, remote SFTP editing, shared classic UI, ordinary-user/desktop accessibility, Task Manager, English labels/dialogs, file management and editor operations.
- The English regression checks branding, application menus, accessible labels, dialogs, English mnemonics and preservation of a Unicode user file across reload.
- JavaScript and shell syntax checks passed. Python AST comparison against the pre-translation snapshot found no structural changes outside string values.
- Production HTTPS entry page, all 26 linked assets and installed Python sources matched the checkout. Anonymous API requests still returned 401 with an English message.
- Services remained active, deployment backup succeeded and the persistent worker start timestamp was unchanged.

The current session worker was deliberately not restarted. Already-running Chromium sessions retain their previous language until ended and relaunched; worker-held older error messages are replaced on the next scheduled worker restart. Such a restart ends its live jobs and must be planned accordingly.

Screenshots: [production login](../screenshots/login.png), [English Start menu](../screenshots/desktop.png).
