import sys,os,subprocess
sys.path.insert(0,'tests')
from mariadb_fixture import MariaDBFixture
with MariaDBFixture() as fixture:
 subprocess.run([sys.executable,'tests/run_classic_suite.py','phpmyadmin_ui.cjs'],env={**os.environ,'WIN2K_TEST_DB_PORT':str(fixture.port)},check=True)
