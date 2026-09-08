"""A disposable MariaDB server. Never connects to the installed server."""
import socket
import datetime
import ipaddress
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import subprocess
import tempfile
import time
from pathlib import Path


class MariaDBFixture:
    def __enter__(self):
        self.temp = tempfile.TemporaryDirectory(prefix='pi2000-mariadb-test-')
        self.root = Path(self.temp.name)
        self.log = (self.root/'server.log').open('w')
        key = rsa.generate_private_key(public_exponent=65537,key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'Disposable MariaDB')])
        now = datetime.datetime.now(datetime.timezone.utc)
        cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-datetime.timedelta(minutes=1)).not_valid_after(now+datetime.timedelta(days=1)).add_extension(x509.BasicConstraints(ca=True,path_length=None),critical=True).add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]),critical=False).sign(key,hashes.SHA256()))
        self.ca = cert.public_bytes(serialization.Encoding.PEM).decode()
        (self.root/'cert.pem').write_text(self.ca)
        (self.root/'key.pem').write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
        (self.root/'key.pem').chmod(0o600)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            self.port = sock.getsockname()[1]
        try:
            subprocess.run(['mariadb-install-db', '--no-defaults', '--datadir='+str(self.root/'data'), '--auth-root-authentication-method=normal', '--skip-test-db'], stdout=self.log, stderr=self.log, check=True)
            self.process = subprocess.Popen(['mariadbd', '--no-defaults', '--datadir='+str(self.root/'data'), '--socket='+str(self.root/'db.sock'), '--pid-file='+str(self.root/'db.pid'), '--bind-address=127.0.0.1', '--port='+str(self.port), '--innodb-buffer-pool-size=32M', '--key-buffer-size=8M', '--max-connections=20', '--local-infile=0', '--skip-log-bin', '--ssl-cert='+str(self.root/'cert.pem'), '--ssl-key='+str(self.root/'key.pem')], stdout=self.log, stderr=self.log)
            for _ in range(100):
                if self.process.poll() is not None:
                    raise RuntimeError('Disposable MariaDB failed: '+(self.root/'server.log').read_text()[-2000:])
                if (self.root/'db.sock').exists():
                    result=subprocess.run(['mariadb', '--no-defaults', '--socket='+str(self.root/'db.sock'), '-u', 'root', '-e', 'SELECT 1'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    if result.returncode == 0:
                        return self
                time.sleep(.1)
            raise RuntimeError('Timed out waiting for disposable MariaDB')
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, *args):
        if getattr(self, 'process', None):
            self.process.terminate()
            self.process.wait(timeout=15)
        self.log.close()
        self.temp.cleanup()
