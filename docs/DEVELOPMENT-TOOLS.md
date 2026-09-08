# Development tools

All tools are available under **Start → Programs → Development and Drawing**. They use the shared Windows 2000 menus, keyboard navigation and window manager. MariaDB administration is documented separately in [MariaDB Manager](MARIADB-MANAGER.md).

## Git Projects

**File → New Project** initializes a private repository. **Clone Repository** accepts HTTPS URLs, with optional username and access token supplied for that operation only. Clones initially fetch the latest commit. Configure **Remote → Remote URL** to add or change `origin`.

Select a project to see its status and files. **New File / Edit File** edits UTF-8 files up to 1 MB with version conflict detection. Select files to stage or unstage, inspect working/staged diffs, and commit with an explicit author name, email and message. Committing does not push. Branch commands create/switch branches; Remote contains Fetch, fast-forward-only Pull and explicitly confirmed Push. History displays the latest 30 commits.

Workspaces are independent from My Files and the Pi-2000 installation. Git runs in a bubblewrap namespace exposing only that project and read-only system binaries/certificates. Host home directories, platform state, installation directories and worker sockets are not mounted. Hooks and filesystem monitors are disabled; Git does not use host Git configuration, credential helpers, SSH, local-file or executable transports. Credentials are not saved into Git configuration. TLS verification remains enabled and HTTP redirects are disabled.

Limits: ten projects per account, 64 MB and 20,000 files per project, two concurrent Git operations globally, one per account, 60 seconds per command, 2 MB command output. Large repositories, SSH remotes, submodule workflows, rebasing/merge editors, LFS downloads and a full IDE are outside this version's interface. Use a smaller project or another Git client for those workflows.

Local platform backups include Git workspaces and repository objects. Existing backup policy omits filesystem symlinks and caches; committed symlinks can be reconstructed from Git objects. Never treat an unverified backup as the only copy of important uncommitted work.

## Code Editor diagnostics

**Code → Check Syntax** checks the active `.py`, `.js`, `.cjs`, `.mjs` or `.json` file. Problems appear as editor annotations and clickable line entries. Editing clears stale annotations. Python is compiled without execution; JavaScript uses Node's syntax-check mode. Neither imports nor executes the user's program.

Checks support up to 256 KB, run with a short timeout/resource limits, and do not provide type checking, dependency analysis or runtime correctness. `.mjs` uses JavaScript module syntax; `.js` and `.cjs` use CommonJS syntax.

## API Tester

Enter a URL, method, headers and optional body, then **Send**. Headers use `Name: value`, one per line. **Request → Authentication** prepares Bearer or Basic authentication. Inspect raw body, formatted JSON, response headers, status, elapsed time and size; download raw response bytes through File.

Saved requests, including bodies and headers, are encrypted with the private credential key and belong to the current Pi-2000 account. Up to 100 requests / 8 MB of encrypted collection data can be stored. Saving a request also saves authentication headers; delete or replace them when they are no longer needed.

Requests originate from the Pi, not from the user's browser. TLS certificates are verified. Pi login cookies are never forwarded automatically. Redirects are shown without being followed, and compressed responses remain raw. Responses are capped at 1 MB and requests at 30 seconds. A timeout does not establish whether a remote write succeeded.

API Tester blocks metadata/link-local addresses and Pi-2000 administration endpoints. Local development services may use ports 3000, 3001, 4000, 5000, 5001, 5173, 8000, 8001, 8080, 8081 or 9000. DNS addresses are checked and pinned for each request. External or LAN APIs must be reachable from the Pi.

## Verification

`python -m unittest discover -s tests -p test_development_tools.py` verifies syntax diagnostics without execution, encrypted/private request storage, HTTP behavior, protected endpoints, Git commits/branches, path isolation and disabled hooks using disposable data. No production database or remote repository is modified.

`python tests/run_classic_suite.py development_ui.cjs` covers the actual desktop flows for API collections, Git project/file/staging/commit/history and editor diagnostics. Use the project's `.venv/bin/python`.
