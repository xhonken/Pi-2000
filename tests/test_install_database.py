import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import pymysql
from cryptography.fernet import Fernet
from mariadb_fixture import MariaDBFixture
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packaging'))
sys.path.insert(0,str(ROOT/'server'))
import provision
import app

class InstallationDatabaseTests(unittest.TestCase):
    def test_database_credentials_grants_private_profile_and_retry(self):
        with MariaDBFixture() as fixture, tempfile.TemporaryDirectory() as directory, patch.object(app,'STATE',Path(directory)):
            password='installation-fixture-password'
            state={}
            with pymysql.connect(unix_socket=str(fixture.root/'db.sock'),user='root',autocommit=True) as admin:
                provision.provision_database(admin,state,lambda:None,password)
                provision.provision_database(admin,state,lambda:None,'not-applied-to-existing-account')
            with pymysql.connect(host='127.0.0.1',port=fixture.port,user='pi2000_admin',password=password,database='pi2000_admin',autocommit=True) as db:
                with db.cursor() as cur:
                    cur.execute('CREATE TABLE proof (id INT)')
                    cur.execute('SHOW GRANTS')
                    grants=' '.join(row[0] for row in cur.fetchall())
                    self.assertIn('`pi2000_admin`.*',grants)
                    self.assertNotIn('ALL PRIVILEGES ON *.*',grants)
                    with self.assertRaises(pymysql.Error):cur.execute('CREATE DATABASE forbidden_database')
            app.initialize(initial_password=password)
            provision.save_connection(app,password,state,lambda:None)
            provision.save_connection(app,'another-fixture-password',state,lambda:None)
            with app.db() as db:
                rows=db.execute('SELECT * FROM database_connections').fetchall()
                self.assertEqual(len(rows),1)
                self.assertEqual(rows[0]['user_id'],db.execute("SELECT id FROM users WHERE username='admin'").fetchone()['id'])
                self.assertEqual(Fernet((app.STATE/'database-credentials.key').read_bytes()).decrypt(rows[0]['secret'].encode()).decode(),password)
                self.assertNotIn(password,(app.STATE/'admin.sqlite3').read_bytes().decode(errors='ignore'))
            with pymysql.connect(unix_socket=str(fixture.root/'db.sock'),user='root',autocommit=True) as admin:
                with self.assertRaises(ValueError):provision.provision_database(admin,{},lambda:None,password)

if __name__=='__main__':unittest.main()
