# MariaDB Manager

The default manager now integrates upstream phpMyAdmin with the Pi-2000 theme and existing saved connections. See [phpMyAdmin integration](PHPMYADMIN.md) for current behavior, installation and limits. The native SQL workspace described below remains available through **File → Saved SQL Workspace** to preserve existing drafts and tools.

MariaDB Manager is available under **Start → Programs → Development and Drawing**. It manages databases through MariaDB TCP connections from the Pi running Pi-2000Web. It does not expose the Pi-2000Web source tree, internal SQLite database, shell, or service configuration.

## Connections and saved work

Select **File → New Connection**, enter a name, server, port (normally 3306), database username and optional default database. Save the connection, then select it and choose **Connect**, or double-click it. **Properties**, **Test Connection** and **Delete Connection** manage the selected profile. Deleting a profile does not delete any remote databases; it disconnects that profile's active sessions.

`127.0.0.1` means the Pi running Pi-2000Web, not the computer displaying the desktop. A local MariaDB server must accept TCP authentication; Unix-socket root authentication is not used. An external server must be reachable from the Pi and allow that database account to connect from the Pi's address.

TLS certificate and hostname verification is the default. A custom PEM CA certificate can be pasted into Properties. Unencrypted mode is an explicit option for trusted local connections. TLS failure never silently falls back to an unencrypted login.

Passwords are requested at connection time unless **Save password encrypted for my account** is selected. Saved secrets are encrypted on the server, never returned by the connection-list API. Changing host, port, username or TLS trust settings clears the old saved secret unless a new password is supplied. Profiles are private even from other Pi-2000Web administrators.

**Save Workspace** (`Ctrl+S`) saves query tabs for the current account. Edits also save after a short pause. Save status is shown at the bottom; concurrent edits from another page produce a conflict rather than silently replacing that page's work. SQL workspaces count towards the account's file quota. SQL text can contain sensitive data, so avoid saving password-bearing administration statements unnecessarily.

Saved profiles and SQL tabs survive page reloads and service restarts. Live database connections are separate: reconnect after reloading. Transactions are not resumed automatically. Closing Manager disconnects its session; idle sessions expire after 30 minutes, and revoked logins are cleaned up within 15 seconds.

## SQL workspace

**Table Data** and **SQL Queries** are separate views. Selecting a table opens its row grid with direct row commands; **SQL Queries** returns to your SQL editor. Each SQL tab displays its own recent result; runtime results are cached for the four most recently executed tabs and are not saved across reloads.

SQL tabs stay on one horizontally scrolling line. Each has a visible **×** close button; the **Open queries** list selects tabs when space is limited. Arrow keys, Home/End and Delete work on the focused tab. **Queries…** opens a separate management dialog; the Query menu also provides Close Other Queries and Close All Queries. Closing nonempty queries asks before removing their text from the saved workspace. Download SQL first to keep a separate copy. These commands never delete database rows.

**New Query** reuses an empty numbered query before opening another. At 32 tabs, Manager opens the query management dialog so you can make room. Existing saved workspaces are preserved even when they contain more tabs or repeated names. Duplicate labels receive display numbers without changing the saved SQL. Closing tabs saves the workspace; closing the last tab leaves one empty editor.

## Working with a database

The left Object Explorer lists databases and their tables/views. Selecting a database changes the active SQL database. Selecting a table shows 100 rows at a time; Previous/Next Rows changes the offset. Without an explicit `ORDER BY`, MariaDB does not promise a stable row order; use **Data → Filter / Sort** or an ordered SQL query for repeatable paging. Contains filters treat percent signs and underscores literally.

**Data → Structure** shows `SHOW CREATE TABLE`/view output. **Query → SQL Templates** prepares editable SQL in a new tab. The Administration menu opens focused dialogs:

- **Database Administration**: list databases, collations, storage engines and table sizes; create/alter/drop databases; create tables; rename/copy tables; change engine, comment, collation or AUTO_INCREMENT; truncate/drop tables.
- **Users and Privileges**: create users with explicit user/host identity, optionally create a database and grant that account access; change passwords, rename/drop accounts, control account locking, password expiry, required TLS and resource limits. Grant/revoke global, database, table, column or routine privileges; create/drop/assign roles and set default roles. Account lists and grants omit authentication hashes.
- **Table Designer**: inspect columns, indexes and relations; add/modify/rename/drop columns; create/drop ordinary, unique, primary, full-text or spatial indexes; create/drop composite foreign keys with update/delete actions.
- **Programmable Objects**: inspect views, procedures, functions, triggers and events; open definitions or creation templates in the SQL workspace; drop objects or change event enabled state.
- **Search Database / Relationship Diagram**: search bounded text-column previews using server collation; inspect declared foreign-key connections and rules in a diagram and detailed table.
- **Server Administration**: filtered status, variables and process lists, query cancellation by process ID, check/analyze/optimize/repair operations.

Administration forms produce a separate **Review Database Changes** dialog. Only **Apply Changes** executes the reviewed statements. Plans expire after five minutes, are single-use and belong to the current database login session. Passwords are redacted in previews and never inserted into saved query tabs. Earlier statements can remain applied if a later step fails; the error reports how many steps completed.

All commands use the connected MariaDB account's grants. A Pi-2000 administrator cannot bypass database permissions. MariaDB has database privileges rather than PostgreSQL-style ownership; database grants escape `%` and `_` to target the exact named database. New-user database grants do not include GRANT OPTION. Advanced or version-specific SQL remains available in the editor.
**Execute** (`Ctrl+Enter`) runs selected SQL or the entire tab. Multiple statements and multiple result sets are supported, including routine results. Each result has its own selector. The header reports the active database and transaction/autocommit state after executing SQL. Use the transaction templates or SQL for `START TRANSACTION`, `COMMIT`, and `ROLLBACK`. MariaDB DDL can implicitly commit; a SQL script is not automatically an atomic operation.

**Data → Insert Row / Edit Row / Delete Row** opens a focused form. **OK executes the change directly**, then refreshes the table; it does not create a query tab. Delete presents its own confirmation form. Each field has an explicit Value, Database default or NULL mode; edits default to Keep existing value. Typing selects Value automatically. Empty auto-increment IDs are omitted on insert and preserved on edit. Blank TIMESTAMP/DATETIME values use `CURRENT_TIMESTAMP`, evaluated with the connected database server's time/time zone. Choose NULL explicitly when intended. Defaults are resolved by MariaDB, not guessed in the browser.

Edits/deletes require a primary key and match the original displayed values with `LIMIT 1`. Zero affected rows can mean unchanged values or a concurrent change. Binary values are preserved unless NULL/default is explicitly selected; replace binary data through SQL. With an open transaction, the message explains that the change awaits COMMIT. A failed refresh after a successful write is reported separately to prevent accidental repeat inserts.

**Query → Query Builder** opens a tabbed SELECT builder: Tables and Joins, Columns and Filters, SQL Preview. Choose a base table, add up to eight LEFT/RIGHT/INNER/CROSS joins, select output columns, an optional WHERE filter, sorting and a row limit. Declared foreign keys suggest join conditions, including composite keys; manual column matching is available. Aliases distinguish repeated tables. Short explanations describe each join's behavior and the effect of WHERE on outer joins. **Open SQL Query** creates an editable query tab for execution or saving in the SQL workspace. It does not change data automatically. Aggregation, nested queries, UNION and multiple manual ON/WHERE conditions remain editable SQL tasks.

**Explain** runs MariaDB `EXPLAIN` for the current query. **Cancel Query** terminates this session's database connection through a separate authenticated connection, then discards the session. Reconnect and inspect writes before retrying an interrupted command. Network failures cannot prove whether a write committed.

## Import and export

- **Import SQL / CSV** reads a UTF-8 file chosen in the user's browser into a query tab for review. It never reads an arbitrary server-side file path.
- SQL imports support up to 1 MB. `DELIMITER` is a command-line client directive and must be removed; execute routine definitions separately. Use Restore SQL File for larger files and DELIMITER support.
- CSV imports require a header containing unique column names and up to 1,000 data rows. Commas, quoted fields, escaped quotes and embedded newlines are supported. Empty CSV fields become empty strings; adjust the prepared SQL if NULL is intended. Expanded SQL must fit the 1 MB SQL limit.
- **Export CSV** exports the selected displayed result; NULL becomes an empty CSV field.
- **Export Result SQL** creates INSERT statements targeting the selected table, preserving NULL and binary values. Review the destination and columns. This exports the displayed result only.
- **Download SQL** saves the current query text.

**File → Export Database** exports table structure and optionally every row, views, routines, triggers and events into a downloadable SQL file. Export uses its own connection and streams rows into a private temporary file; it is independent of the editor's open transaction. The export is capped at 64 MB, with a five-minute runtime and 2 MB protocol packet limit. InnoDB data uses a consistent snapshot; non-transactional tables and concurrent schema changes do not. Generated columns are excluded from INSERT assignments. Account grants are not part of the dump.

**File → Restore SQL File** accepts UTF-8 SQL up to 16 MB / 100,000 statements, supports DELIMITER and reports progress. The file is parsed before any statements execute. It uses a separate connection, stops at the first SQL error and commits any transaction left open at successful completion. Completed writes or DDL may remain after failure or cancellation. Scripts relying on unusual delimiter syntax or changing string-escape parsing modes mid-file may need normalization first.

Transfer dialogs show progress and offer cancellation. Only completed exports can be downloaded. Temporary output belongs to the originating login, expires after ten minutes of inactivity and is removed when the dialog closes or the login ends. One transfer per account and four globally are allowed.

Definitions retain definers and qualified database references. Restore to the original database name, or review/adapt the SQL before moving it. Existing destination objects are not dropped automatically. A result export remains different from a database export; neither replaces a tested database-server backup strategy.

## Limits and platform boundaries

Each Pi-2000Web account may save 100 profiles and open up to four live sessions; the service allows 12 sessions and two connection handshakes globally. SQL commands have a 60-second client timeout. Results are streamed, with limits of 1,000 rows total, 2 MB serialized row data, 2 MB per protocol packet and 1,000 result sets. Exceeding a result limit closes the session; use LIMIT, narrower queries or smaller batches. A SQL script may have applied earlier statements before an error or limit is reached.

The connector does not use Unix sockets, option files, shell commands or `LOAD DATA LOCAL INFILE`. Even a database server requesting a local file cannot use this connector to read Pi-2000Web files. There is no automatic use of the platform owner's credentials. The database server's OS account must also remain unable to modify Pi-2000Web code or private state; SQL administration grants do not replace filesystem isolation.

The private `database-credentials.key` in the state directory is required to decrypt saved passwords. Pi-2000Web backups include it alongside encrypted profiles. Protect backups as credentials and restore the key and database together. The source repository must never contain that key.

## Feature coverage and references

The design draws on [phpMyAdmin's supported feature list](https://docs.phpmyadmin.net/en/latest/intro.html) and [SSMS Object Explorer](https://learn.microsoft.com/en-us/ssms/object/manage-objects-by-using-object-explorer). MariaDB-specific SQL and permission behavior follow [MariaDB's SQL reference](https://mariadb.com/docs/server/reference/sql-statements) and [GRANT documentation](https://mariadb.com/docs/server/reference/sql-statements/account-management-sql-statements/grant). Client file loading is deliberately disabled as described in [MariaDB LOAD DATA INFILE](https://mariadb.com/docs/server/reference/sql-statements/data-manipulation/inserting-loading-data/load-data-into-tables-or-index/load-data-infile).

This version provides substantial graphical administration, but does not claim complete phpMyAdmin/SSMS parity. Additional spreadsheet/document import-export formats, graphical execution plans, schema comparison/change tracking, SSH tunnels, advanced query construction and unbounded data searches remain outside the current interface. Large production dumps and specialized MariaDB features may require native tools. The [development workboard](DEVELOPMENT-ROADMAP.md) records coverage. SSMS-specific SQL Server features are not MariaDB features.

## Verification

With `mariadbd` and `mariadb-install-db` installed, `python -m unittest discover -s tests -p test_database_tools.py -v` starts a disposable loopback MariaDB instance on a random port. It tests private profiles, encrypted credentials, endpoint changes, verified custom-CA TLS, SQL batches, transactions, large integer precision, cancellation, limits and disabled file loading. It never connects to the installed MariaDB server.

`python tests/run_database_ui.py` runs the desktop browser test with a separate MariaDB instance. It covers connection create/edit/delete, real query results, table browsing, row editing, CSV import and saved SQL workspace restoration. It also verifies account/database creation with redacted review and full export download. Backend tests cover exact database grants, roles/schema operations, partial failure, single-use plans and a 1,200-row export/restore with generated columns, binary data, procedure and trigger. Existing backup tests verify credential-key preservation. Use the project `.venv/bin/python` for these commands.
