import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'server'))
from browser_runtime import BrowserRuntime, BrowserUnavailable, valid_browser_url

class BrowserURLTests(unittest.IsolatedAsyncioTestCase):
    def test_reject_non_web_urls_and_control_characters(self):
        for value in ['file:///etc/passwd','javascript:alert(1)','--new-window','https://','https://x\n--flag','https://x:bad',None,{},'https://x/'+'a'*4096]:
            self.assertFalse(valid_browser_url(value),repr(value))
        self.assertTrue(valid_browser_url('https://elektrokit.com/'))

    async def test_private_queue_and_capacity(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime=BrowserRuntime(tmp)
            for uid in (1,2):
                folder=Path(tmp)/str(uid);folder.mkdir();(folder/'url-ready').touch()
                runtime.sessions[uid]={'runtime':folder,'process':SimpleNamespace(returncode=None)}
            await runtime.open_url(1,'https://elektrokit.com/')
            self.assertEqual([p.read_text() for p in (Path(tmp)/'1').glob('open-*.url')],['https://elektrokit.com/'])
            self.assertEqual(list((Path(tmp)/'2').glob('open-*.url')),[])
            with self.assertRaises(BrowserUnavailable):await runtime.open_url(2,'file:///etc/passwd')
            for _ in range(31):await runtime.open_url(1,'https://example.com/')
            with self.assertRaises(BrowserUnavailable):await runtime.open_url(1,'https://example.com/')
