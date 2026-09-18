"""Exercise packaged phpMyAdmin using disposable PHP, Pi and MariaDB state."""
import sys, os, subprocess
from mariadb_fixture import MariaDBFixture
from phpmyadmin_fixture import PhpMyAdminFixture
with MariaDBFixture() as db, PhpMyAdminFixture() as php:
    subprocess.run([sys.executable,'tests/run_classic_suite.py','phpmyadmin_ui.cjs'],env={**os.environ,'PI2000_TEST_DB_PORT':str(db.port),'PI2000_TEST_PMA_ROOT':str(php.site),'PI2000_TEST_PMA_SOCKET':str(php.socket)},check=True)
