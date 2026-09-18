# Code cleanup — 2026-09-18

The review covers first-party Python, JavaScript, installation/package scripts,
the deployment inventory, development dependencies and archived UI assets.
Removal decisions combine static analysis with references from routes, app
registration, examples, deployment scripts and tests. A missing literal reference
alone does not establish that code is unused.

## Removed or reduced

- Removed the 31-file superseded reference gallery, including duplicate framework
  distributions, demo applications and fonts. Its source provenance remains in
  [the Alpha 7 source manifest](https://github.com/xhonken/Pi-2000/blob/v0.1.0-alpha.7/docs/source-manifest.json); Git history retains the original files.
- Removed `assets/system-icons.css`. Its pixel drawings had already been hidden
  by the current SVG icon styles. Essential layout declarations now belong to
  `classic-icons.css`; the icon generator also retains Pi++ and Pi-Vault icons.
- Moved the standalone demo's JavaScript from `dist/` into
  `examples/standalone/ui.js`. The example still works; that script is no longer
  included in the installed desktop's public files.
- Removed unused imports and local state from application, installer and test
  code. Calls whose side effects are required remain in place.
- Removed the unused full file-table query from ZIP export. Selection, ownership,
  archive limits and descendant traversal are unchanged.
- Removed the unused health request from My Activities' three-second refresh.
  The terminal list still refreshes normally; System Status retains health checks.
- Removed the unused npm development copy of `hash-wasm`. Pi-Vault continues to
  use its vendored Argon2 bundle and license; encryption formats are unchanged.

## Required code retained

- HTTP handlers registered by name, lifecycle callbacks and inherited protocol
  methods, including SSH host-key validation and bounded MariaDB result handling.
- URL port validation: reading `urlsplit(...).port` can raise on invalid input,
  even when its returned value is not otherwise needed.
- The account monitor task's strong reference, PAM callback arguments and browser
  version cache key, which static analyzers can mistake for unused state.
- Ace modes/themes/search extension and PDF fonts/workers loaded dynamically;
  IPTV playback and Vault dependencies; upstream browser dependency pins.
- Source/package installation, backup/restore, supported compatibility commands,
  system-name migration and account/workspace data migrations.
- The maintained standalone example and operator examples, regression tests,
  licenses and source provenance.

Static analysis is not a proof that no unused code remains. In particular,
unobserved error paths and hardware workflows are not deletion candidates merely
because they did not run in a browser test. Future cleanup should use the same
reference review and behavioral checks before removing them.
