# MariaDB Manager rebuild

Requested outcome: phpMyAdmin-style navigation and complete functional coverage, retaining Pi-2000 private saved local/remote connections and platform isolation. This is a new request; the existing manager is not a complete phpMyAdmin implementation.

## Navigation model

- Server: overview, databases, SQL, status/processes, accounts/privileges, export/import, variables, charsets/collations, engines/plugins, binary logs and replication.
- Database: table structure/list, SQL, search, query builder, export/import, operations, privileges, routines, events, triggers, tracking, designer and central columns.
- Table/view: browse, structure, SQL, search, insert, export/import, privileges, operations, tracking and triggers.
- Persistent left navigation: connection selection and searchable database/object tree. Main content follows the selected server/database/table, with breadcrumbs and contextual actions.

Navigation entries must lead to working pages. Unsupported operations must not be represented by dead buttons or silently replaced with an unrelated SQL template.

## Functional coverage to verify

| Area | Existing Pi-2000 coverage | Additional scope |
|---|---|---|
| Connection/session | Private profiles, encrypted passwords, TLS, reconnect | Preserve identity and TLS through any integration; revoke access on Pi logout |
| Server inspection | Status, variables, processes | Engines/plugins, collations, binary logs, replication, richer status displays |
| Database operations | Create/alter/drop; table metadata | Database copy/move, bulk table actions, per-object privilege handling |
| Structure | Columns, indexes, foreign keys | Column order, generated expressions, comments, engine-specific options |
| Browse/edit | Paged rows, direct forms, defaults/NULL, optimistic edits | Multi-row actions, binary input/download, richer cell editing |
| SQL | Saved drafts, multi-results, cancellation, EXPLAIN, JOIN builder | Bookmarks/history, richer editor and result charts |
| Accounts | Users/hosts, roles, grants, security/limits | Copy privileges and complete server-supported privilege discovery |
| Programmable objects | Definitions, templates, drops, event state | Dedicated create/edit/call flows and parameter forms |
| Transfers | SQL/CSV, bounded full SQL exports and restore jobs | phpMyAdmin-supported formats and compression, format-specific options |
| Relations | Foreign-key view/diagram | Designer layout, PDF diagrams and auxiliary relations |
| Metadata | Private Pi drafts | Tracking, central columns, bookmarks, preferences and transformations |
| Permissions | MariaDB grants plus Pi account isolation | Tests across multiple Pi accounts, logout/revocation and inaccessible platform files |

## Implementation routes

An upstream phpMyAdmin integration supplies its actual feature implementation, including optional configuration-storage features when correctly provisioned. It adds a PHP runtime and an authentication/session bridge. It must remain a separately confined database tool and must not gain access to Pi-2000 private files or services. Saved credentials must never appear in URLs, client-visible configuration or logs. Optional metadata must be isolated appropriately; shared database user names alone do not identify Pi accounts.

A native implementation preserves the current Python/plain-JavaScript stack but requires each missing feature to be built and tested individually. Changing appearance alone cannot establish full parity.

The user selected upstream phpMyAdmin integration with the Pi-2000 appearance. Implementation and operational boundaries are documented in [PHPMYADMIN.md](PHPMYADMIN.md).

## Upstream references

- [Feature overview](https://docs.phpmyadmin.net/en/latest/intro.html)
- [User guide](https://docs.phpmyadmin.net/en/latest/user.html)
- [Account and privilege management](https://docs.phpmyadmin.net/en/latest/privileges.html)
- [Installation and configuration storage](https://docs.phpmyadmin.net/en/latest/setup.html)
- [Configuration and signon authentication](https://docs.phpmyadmin.net/en/latest/config.html)
- [Transformations](https://docs.phpmyadmin.net/en/latest/transformations.html)

Reviewed 2026-09-09. Upstream latest documentation includes development-version material; implementation must target the chosen installed release and its supported MariaDB versions.
