# Development workboard

Current scope: Browser memory verification, MariaDB Manager, private Git projects, editor diagnostics and API Tester. MariaDB has priority. Interfaces preserve classic Windows 2000 menus, compact toolbars and separate administration dialogs.

## Implemented coverage

| Area | Current implementation | Deliberate limits / further depth |
|---|---|---|
| Browser | Live cgroup high/max/swap limits, isolated OOM reason, reconnect and profile preservation verified after reboot | See Browser memory documentation |
| MariaDB connections | Private profiles, TLS/custom CA, encrypted credentials, connection errors, SQL workspace restoration | One active connection per Manager window; no SSH tunnel |
| Databases | Create/alter/drop, character sets/collations, metadata, create database as part of new user workflow | Alters defaults rather than rewriting existing text columns |
| Accounts | User/host identities, passwords, rename/drop, lock/unlock, expiration, TLS requirements, limits, scoped grants/revocation, role assignment/default role | Connected database grants determine authority; specialized authentication plugins use SQL |
| Tables | Create table/columns, modify/rename/drop columns, indexes, composite foreign keys, table rename/copy, engine/collation/comment/AUTO_INCREMENT | Generated-column expressions and specialized engine options use SQL; copy uses CREATE TABLE LIKE |
| Rows | Browse, filter, sort, paging, insert/edit/delete SQL forms, optimistic matching by primary key/original values | Binary editing uses SQL; no arbitrary-result row mutation |
| Programmable objects | List/definition/templates/drop for views, routines, triggers, events; enable/disable events | Definitions edited as SQL; execution depends on server version and grants |
| SQL | Multiple tabs/results, private saved drafts, selection execution, EXPLAIN, cancellation, transaction status | Text SQL editor; no graphical plan or visual query builder |
| Transfers | All-row SQL export, optional routines/triggers/events, generated-column/binary handling; DELIMITER restore, progress/cancel | 64 MB export, 16 MB restore, five minutes; consistent InnoDB snapshot only; preserve definers/database references |
| Maintenance | Status/variables/process inspection, kill query, check/analyze/optimize/repair | Variable changes and replication administration use SQL |
| Discovery | Database text search, foreign-key diagram and details | Search caps 50 tables / 250 matching previews; diagram caps 80 related tables |
| Git | Private sandboxed projects, HTTPS clone, file editing, status/diff, staging/commit, branches/history, fetch/pull/push interface | 64 MB projects; no SSH/LFS/merge editor; external remote round trips not part of automated verification |
| Diagnostics | Python, JavaScript/CommonJS/modules, JSON syntax checks with annotations/line navigation | Syntax only, 256 KB; no full language-server/type analysis |
| API Tester | Private encrypted saved requests, headers/auth/body, HTTP response/timing, JSON/header views and downloads | 1 MB response, verified TLS, redirects explicit; protects platform endpoints |

## Remaining beyond this implementation

This is not a claim that every phpMyAdmin feature exists. Spreadsheet/document formats, visual query building, graphical query plans, schema comparison/tracking, richer SQL editor tooling, advanced authentication-plugin forms, SSH tunneling and very large database transfers remain potential follow-up work. Native SQL remains available for MariaDB operations without a dedicated form.

Database users and Pi-2000 users are separate. New-user database access is an exact database grant without GRANT OPTION. Pi-2000 web administrator status cannot bypass MariaDB grants or filesystem isolation.

References: [phpMyAdmin features](https://docs.phpmyadmin.net/en/latest/intro.html), [user administration](https://docs.phpmyadmin.net/en/latest/privileges.html), [MariaDB privileges](https://mariadb.com/docs/server/reference/sql-statements/account-management-sql-statements/grant), [CREATE USER](https://mariadb.com/docs/server/reference/sql-statements/account-management-sql-statements/create-user).

See [MariaDB Manager](MARIADB-MANAGER.md) and [Development Tools](DEVELOPMENT-TOOLS.md) for behavior, security boundaries, limits and verification commands. Installation state must be verified separately from repository test results.
