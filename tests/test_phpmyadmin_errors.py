"""Dependency notices must not replace real warnings in AJAX or page requests."""
import subprocess
import tempfile
import unittest
from pathlib import Path

class PhpErrorTests(unittest.TestCase):
    def test_early_filter_keeps_actionable_warnings(self):
        with tempfile.TemporaryDirectory() as temp:
            temp=Path(temp)
            config=Path(__file__).resolve().parents[1]/'server/phpmyadmin/config.inc.php'
            (temp/'config.php').write_text(config.read_text().replace('/var/lib/pi2000-phpmyadmin/',str(temp)+'/'))
            script='''<?php
$seen=[];
set_error_handler(static function($number,$text)use(&$seen){$seen[]=$number;return true;});
$_SERVER['PI2000_BRIDGE']=base64_encode(json_encode(['sid'=>str_repeat('a',48),'base'=>'https://localhost/','host'=>'127.0.0.1','port'=>3306,'username'=>'fixture','password'=>'','name'=>'Fixture','tls'=>'disabled']));
require __DIR__.'/config.php';
trigger_error('Dependency deprecation',E_USER_DEPRECATED);
trigger_error('Actionable warning',E_USER_WARNING);
trigger_error('Actionable notice',E_USER_NOTICE);
if($seen!==[E_USER_WARNING,E_USER_NOTICE])exit(1);
echo 'PASS';
'''
            (temp/'test.php').write_text(script)
            self.assertEqual(subprocess.check_output(['php',str(temp/'test.php')]).decode(),'PASS')
