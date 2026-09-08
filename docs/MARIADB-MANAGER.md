# MariaDB Manager

MariaDB Manager is available under **Start → Programs → Development and Drawing**. It manages databases through MariaDB TCP connections from the Pi running Pi-2000Web. It does not expose the Pi-2000Web source tree, internal SQLite database, shell, or service configuration.

## Connections and saved work

Select **New Connection**, enter a name, server, port (normally 3306), database username and optional default database. Save the connection, then select it and choose **Connect**, or double-click it. **Properties**, **Test Connection** and **Delete Connection** manage the selected profile. Deleting a profile does not delete any remote databases; it disconnects that profile's active sessions.

`127.0.0.1` means the Pi running Pi-2000Web, not the computer displaying the desktop. A local MariaDB server must accept TCP authentication; Unix-socket root authentication is not used. An external server must be reachable from the Pi and allow that database account to connect from the Pi's address.

TLS certificate and hostname verification is the default. A custom PEM CA certificate can be pasted into Properties. Unencrypted mode is an explicit option for trusted local connections. TLS failure never silently falls back to an unencrypted login.

Passwords are requested at connection time unless **Save password encrypted for my account** is selected. Saved secrets are encrypted on the server, never returned by the connection-list API. Changing host, port, username or TLS trust settings clears the old saved secret unless a new password is supplied. Profiles are private even from other Pi-2000Web administrators.

**Save Workspace** (`Ctrl+S`) saves query tabs for the current account. Edits also save after a short pause. Save status is shown at the bottom; concurrent edits from another page produce a conflict rather than silently replacing that page's work. SQL workspaces count towards the account's file quota. SQL text can contain sensitive data, so avoid saving password-bearing administration statements unnecessarily.

Saved profiles and SQL tabs survive page reloads and service restarts. Live database connections are separate: reconnect after reloading. Transactions are not resumed automatically. Closing Manager disconnects its session; idle sessions expire after 30 minutes, and revoked logins are cleaned up within 15 seconds.

## Working with a database

The left Object Explorer lists databases and their tables/views. Selecting a database changes the active SQL database. Selecting a table shows 100 rows at a time; Previous/Next Rows changes the offset. Without an explicit `ORDER BY`, MariaDB does not promise a stable row order; use an ordered SQL query for repeatable paging during concurrent changes.

**Structure** shows `SHOW CREATE TABLE`/view output. Administration templates provide editable SQL for columns, indexes, foreign keys, databases, tables, views, stored procedures, triggers, events, database users/grants, process lists, variables, status and table maintenance. Templates are prepared in a new query tab and are never executed automatically. Database grants determine which operations succeed.

**Execute** (`Ctrl+Enter`) runs selected SQL or the entire tab. Multiple statements and multiple result sets are supported, including routine results. Each result has its own selector. The header reports the active database and transaction/autocommit state after executing SQL. Use the transaction templates or SQL for `START TRANSACTION`, `COMMIT`, and `ROLLBACK`. MariaDB DDL can implicitly commit; a SQL script is not automatically an atomic operation.

**Insert Row**, **Edit Row** and **Delete Row** prepare SQL from a form or selected row. Review it and select Execute. Update/delete preparation requires a primary key and includes the displayed original values in the WHERE condition, with `LIMIT 1`; zero affected rows can mean someone changed the row. For tables without a primary key or binary-column edits, use explicit SQL. Do not apply arbitrary query results to a different selected table.

**Explain** runs MariaDB `EXPLAIN` for the current query. **Cancel Query** terminates this session's database connection through a separate authenticated connection, then discards the session. Reconnect and inspect writes before retrying an interrupted command. Network failures cannot prove whether a write committed.

## Import and export

- **Import SQL / CSV** reads a UTF-8 file chosen in the user's browser into a query tab for review. It never reads an arbitrary server-side file path.
- SQL imports support up to 1 MB. `DELIMITER` is a command-line client directive and must be removed; execute routine definitions separately. This is not yet a streaming, full-database dump importer.
- CSV imports require a header containing unique column names and up to 1,000 data rows. Commas, quoted fields, escaped quotes and embedded newlines are supported. Empty CSV fields become empty strings; adjust the prepared SQL if NULL is intended. Expanded SQL must fit the 1 MB SQL limit.
- **Export CSV** exports the selected displayed result; NULL becomes an empty CSV field.
- **Export Result SQL** creates INSERT statements targeting the selected table, preserving NULL and binary values. Review the destination and columns. This exports the displayed result only.
- **Download SQL** saves the current query text.

A result export is not a full database backup. External database backups remain the database owner's responsibility.

## Limits and platform boundaries

Each Pi-2000Web account may save 100 profiles and open up to four live sessions; the service allows 12 sessions and two connection handshakes globally. SQL commands have a 60-second client timeout. Results are streamed, with limits of 1,000 rows total, 2 MB serialized row data, 2 MB per protocol packet and 1,000 result sets. Exceeding a result limit closes the session; use LIMIT, narrower queries or smaller batches. A SQL script may have applied earlier statements before an error or limit is reached.

The connector does not use Unix sockets, option files, shell commands or `LOAD DATA LOCAL INFILE`. Even a database server requesting a local file cannot use this connector to read Pi-2000Web files. There is no automatic use of the platform owner's credentials. The database server's OS account must also remain unable to modify Pi-2000Web code or private state; SQL administration grants do not replace filesystem isolation.

The private `database-credentials.key` in the state directory is required to decrypt saved passwords. Pi-2000Web backups include it alongside encrypted profiles. Protect backups as credentials and restore the key and database together. The source repository must never contain that key.

## Feature coverage and references

The design draws on [phpMyAdmin's supported feature list](https://docs.phpmyadmin.net/en/latest/intro.html) and [SSMS Object Explorer](https://learn.microsoft.com/en-us/ssms/object/manage-objects-by-using-object-explorer). MariaDB-specific SQL and permission behavior follow [MariaDB's SQL reference](https://mariadb.com/docs/server/reference/sql-statements) and [GRANT documentation](https://mariadb.com/docs/server/reference/sql-statements/account-management-sql-statements/grant). Client file loading is deliberately disabled as described in [MariaDB LOAD DATA INFILE](https://mariadb.com/docs/server/reference/sql-statements/data-manipulation/inserting-loading-data/load-data-into-tables-or-index/load-data-infile).

This version is a working SQL administration client, not full graphical parity with phpMyAdmin or SSMS. Schema and privilege changes beyond the row forms use editable SQL/templates. Visual table designers, relationship diagrams, graphical privilege editors, execution-plan diagrams, global data search, server-copy/backup workflows, SSH tunneling and large streaming imports/exports remain future work. SSMS-specific SQL Server features are not MariaDB features.

## Verification

With `mariadbd` and `mariadb-install-db` installed, `python -m unittest discover -s tests -p test_database_tools.py -v` starts a disposable loopback MariaDB instance on a random port. It tests private profiles, encrypted credentials, endpoint changes, verified custom-CA TLS, SQL batches, transactions, large integer precision, cancellation, limits and disabled file loading. It never connects to the installed MariaDB server.

`python tests/run_database_ui.py` runs the desktop browser test with a separate MariaDB instance. It covers connection create/edit/delete, real query results, table browsing, row editing, CSV import and saved SQL workspace restoration. Existing backup tests verify credential-key preservation. Use the project `.venv/bin/python` for these commands.
