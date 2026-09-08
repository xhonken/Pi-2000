import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, AsyncMock
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'server'))
from browser_runtime import BrowserRuntime, BrowserUnavailable
from resource_limits import available_memory, BROWSER_START_RESERVE

class BrowserMemoryTests(unittest.IsolatedAsyncioTestCase):
    def test_available_memory_uses_reclaimable_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'meminfo'
            p.write_text('MemFree: 100 kB\nMemAvailable: 3000000 kB\n')
            self.assertEqual(available_memory(p),3000000*1024)
            p.write_text('MemAvailable: broken kB\n')
            self.assertIsNone(available_memory(p))

    async def test_low_memory_blocks_start_but_allows_reconnect(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'bin').mkdir();(root/'bin/python').touch()
            runtime=BrowserRuntime(tmp,venv=tmp)
            with patch('browser_runtime.available_memory',return_value=BROWSER_START_RESERVE-1), patch('browser_runtime.asyncio.create_subprocess_exec',new_callable=AsyncMock) as spawn:
                with self.assertRaisesRegex(BrowserUnavailable,'Not enough available'):
                    await runtime.start(1)
                spawn.assert_not_called()
                existing={'process':SimpleNamespace(returncode=None)}
                runtime.sessions[1]=existing
                self.assertIs(await runtime.start(1),existing)
                spawn.assert_not_called()

    async def test_watchdog_preserves_reason_and_account_privacy(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime=BrowserRuntime(tmp)
            runtime.sessions[1]={'process':SimpleNamespace(returncode=None)}
            runtime.sessions[2]={'process':SimpleNamespace(returncode=None)}
            runtime.resources.usage=lambda uid:{'memory_bytes':1600*1024**2 if uid==1 else 100*1024**2}
            async def stop(uid):runtime.sessions.pop(uid)
            runtime._stop=AsyncMock(side_effect=stop)
            await runtime.monitor()
            self.assertEqual(runtime.status(1)['reason'],'memory_limit')
            self.assertEqual(runtime.status(2)['state'],'running')
            self.assertEqual(runtime.status(3)['reason'],'not_started')
            runtime._stop.assert_awaited_once_with(1)

    async def test_oom_crash_and_warning_are_distinct(self):
        runtime=BrowserRuntime('/tmp')
        runtime.sessions[1]={'process':SimpleNamespace(returncode=-9),'oom_baseline':2}
        runtime.resources.usage=lambda uid:{'oom_kills':3,'memory_bytes':1250*1024**2}
        self.assertEqual(runtime.status(1)['reason'],'memory_limit')
        runtime.sessions[1]['oom_baseline']=3
        self.assertEqual(runtime.status(1)['reason'],'crashed')
        runtime.sessions[1]['process'].returncode=None
        self.assertIsNotNone(runtime.status(1)['warning'])
