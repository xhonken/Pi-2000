import os
from pathlib import Path
import select
import shutil
import subprocess
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'server'))
from browser_session import initial_display


@unittest.skipUnless(shutil.which('Xvfb') and shutil.which('xrandr'), 'X11 tools required')
class BrowserDisplayTests(unittest.TestCase):
    def test_small_initial_desktop_preserves_large_randr_maximum(self):
        read_fd, write_fd = os.pipe()
        process = subprocess.Popen(['Xvfb', '-displayfd', str(write_fd), '-screen', '0',
            '4096x4096x24', '-nolisten', 'tcp', '-ac', '-noreset'], pass_fds=(write_fd,),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.close(write_fd)
        try:
            self.assertTrue(select.select([read_fd], [], [], 10)[0], 'Xvfb did not start')
            display = ':' + os.read(read_fd, 64).decode().strip()
            with patch.dict(os.environ, {'DISPLAY': display}):
                initial_display()
                geometry = subprocess.check_output(['xrandr', '--current'], text=True)
            self.assertIn('current 1280 x 720', geometry)
            self.assertIn('maximum 4096 x 4096', geometry)
        finally:
            os.close(read_fd)
            process.terminate()
            process.wait(timeout=10)
