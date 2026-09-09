"""Disposable packaged PHP runtime; no installed configuration or service writes."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]

class PhpMyAdminFixture:
    def __enter__(self):
        self.temp = tempfile.TemporaryDirectory(prefix='pi2000-pma-fixture-')
        self.root = Path(self.temp.name)
        self.site = self.root/'phpmyadmin'
        shutil.copytree('/usr/share/phpmyadmin', self.site, symlinks=False)
        self.state = self.root/'state'; self.state.mkdir(mode=0o700)
        self.socket = self.root/'php.sock'
        cfg = (ROOT/'server/phpmyadmin/config.inc.php').read_text().replace('/var/lib/pi2000-phpmyadmin/', str(self.state)+'/')
        (self.root/'config.inc.php').write_text(cfg)
        (self.site/'config.header.inc.php').write_bytes((ROOT/'server/phpmyadmin/config.header.inc.php').read_bytes())
        vendor = self.site/'libraries/vendor_config.php'
        vendor.write_text(vendor.read_text().replace('/etc/phpmyadmin/config.inc.php', str(self.root/'config.inc.php')).replace('/var/lib/phpmyadmin/tmp/', str(self.state)+'/'))
        config = (ROOT/'server/phpmyadmin/php-fpm.conf').read_text().replace('/run/pi2000-phpmyadmin/php.sock', str(self.socket)).replace('/var/lib/pi2000-phpmyadmin', str(self.state)).replace('/usr/share/phpmyadmin', str(self.site)).replace('/etc/phpmyadmin/config.inc.php',str(self.root/'config.inc.php')).replace('error_log = syslog','error_log = '+str(self.root/'php.log'))
        (self.root/'php-fpm.conf').write_text(config)
        self.log=(self.root/'startup.log').open('w')
        self.process=subprocess.Popen(['/usr/sbin/php-fpm8.4','--fpm-config',str(self.root/'php-fpm.conf')],stdout=self.log,stderr=self.log)
        for _ in range(100):
            if self.process.poll() is not None:
                raise RuntimeError((self.root/'startup.log').read_text())
            if self.socket.exists():return self
            time.sleep(.05)
        raise RuntimeError('PHP fixture did not start')

    def __exit__(self,*args):
        if getattr(self,'process',None):self.process.terminate();self.process.wait(timeout=15)
        self.log.close();self.temp.cleanup()
