import os
import subprocess
import sys
from mariadb_fixture import MariaDBFixture
with MariaDBFixture() as fixture:
    subprocess.run([sys.executable,'tests/run_classic_suite.py','database_ui.cjs','database_workspace_ui.cjs'],env={**os.environ,'WIN2K_TEST_DB_PORT':str(fixture.port)},check=True)
