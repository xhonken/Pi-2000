# phpMyAdmin in Pi-2000

MariaDB Manager embeds the distribution-packaged phpMyAdmin inside a Pi-2000 window. The upstream application provides server/database/table navigation and its SQL, structure, search, insert, accounts/privileges, operations, routines, triggers, events, import/export and administration pages. A local CSS overlay supplies the Windows 2000 appearance without replacing upstream forms or query handling.

Choose a saved connection and Connect. File → New Connection / Properties / Delete Connection uses the existing private connection profiles and encrypted credentials. Both local and external MariaDB servers are supported. Unencrypted transport must be selected explicitly; verified TLS and custom CA certificates retain their meaning. The legacy saved SQL drafts remain accessible through File → Saved SQL Workspace.

Database permissions come from the chosen MariaDB account. Global administration pages can be unavailable for accounts with only database-level grants. phpMyAdmin configuration-storage features, including persistent bookmarks, tracking, central columns and designer metadata, require its optional configuration storage on an authorized database. The integration does not silently grant additional privileges or share a platform control account. Use phpMyAdmin's configuration-storage setup for the connected server; metadata follows that database account's access.

## Isolation and session lifecycle

- Every page, asset and form request passes Pi-2000 authentication. An embedded session belongs to the exact Pi login token, not merely the user name.
- Editing/deleting a connection, logout/revocation, inactivity or API restart invalidates the embedded session. Reconnect explicitly; active SQL transactions are not restored.
- Passwords travel only through a private FastCGI Unix socket. They are not embedded in HTML, URLs or browser configuration.
- A separate unprivileged PHP-FPM service cannot access Pi-2000 state, home directories, Caddy state or the served desktop. It does not belong to the API/worker group. The API receives supplementary access only to the dedicated PHP socket.
- PHP setup/configuration/source paths are not exposed by the gateway. PHP execution is restricted to index.php and js/messages.php. Only packaged static asset/documentation directories are served.
- PHP cannot execute shell commands or fetch arbitrary URL streams. MariaDB itself still enforces database account grants.
- PHP session/cache directories are private and age out through systemd-tmpfiles. Embedded sessions expire after 30 minutes idle. Launches are rate limited.

Imports are capped at 64 MiB; gateway responses at 128 MiB; PHP requests at five minutes. One gateway request is processed at a time to bound API memory. Export large databases in smaller selections or use native tools. These are integration resource limits, not claims of unlimited phpMyAdmin parity.

## Installation and maintenance

The normal installer/updater runs scripts/install-phpmyadmin.sh. Debian 13 PHP 8.4 is the current runtime target. Distribution packages supply phpMyAdmin, PHP-FPM and MySQL/mbstring/XML/ZIP/GD extensions. The installer retains the pre-integration /etc/phpmyadmin/config.inc.php as a root-only backup, then installs the gateway-controlled configuration and theme header. The distro's default control-account configuration is not used by this integration.

pi2000-phpmyadmin.service handles PHP on a Unix socket; there is no new public HTTP listener. The API service has supplementary membership of pi2000-phpmyadmin to connect to that socket. Caddy continues to expose only the existing /api gateway. Upstream package security updates remain available through apt; rerun the Pi-2000 updater after package/runtime changes and verify the embedded application.

## References

[phpMyAdmin user guide](https://docs.phpmyadmin.net/en/latest/user.html), [configuration](https://docs.phpmyadmin.net/en/latest/config.html), [installation and configuration storage](https://docs.phpmyadmin.net/en/latest/setup.html), [custom themes](https://docs.phpmyadmin.net/en/latest/themes.html).

## Verification

Backend tests include session ownership, revocation, profile changes, expiry and running-request protection. tests/run_phpmyadmin_ui.py uses disposable PHP and MariaDB runtimes plus a Pi account fixture, without access to the installed PHP socket. It verifies SQL, direct insert/defaults, browse, SQL download/upload, protected source paths, anonymous rejection and disconnect. Run tests/run_database_ui.py for the retained native workspace. The installed HTTPS application is additionally tested with a temporary Pi account and disposable MariaDB, never production user tables.

## Dependency notices

The gateway configuration filters PHP dependency deprecations before routing and
rendering, including AJAX requests which do not render the custom HTML header.
Warnings and ordinary notices continue to reach phpMyAdmin's original error
handler. The distribution dependencies remain unmodified. This is a compatibility
filter, not an upgrade of Twig's deprecated APIs. See the
[PHP error handler documentation](https://www.php.net/manual/en/function.set-error-handler.php).
`tests/run_phpmyadmin_ui.py` now starts disposable PHP and MariaDB runtimes using
the installed distribution packages; it does not need access to the live PHP socket.
