import asyncio
from pathlib import Path
import sys
import unittest
from unittest.mock import patch, AsyncMock
from aiohttp import web
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
from runtime_health import RuntimeIdentity, compare
from maintenance import restart_idle

class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    def test_loaded_identity_does_not_change_with_installed_files(self):
        info={'build':'old','version':'alpha','revision':'old'}
        process=RuntimeIdentity('sessions',info)
        info['build']='new'
        self.assertEqual(compare(process.report(),info)['state'],'pending')
        self.assertEqual(compare(RuntimeIdentity('sessions',info).report(),info)['state'],'current')
        self.assertEqual(compare(None,info)['state'],'unknown')

    def test_draining_blocks_new_work_and_lease_expires(self):
        process=RuntimeIdentity('arduino',{})
        with process.operation():
            process.control({'action':'drain','lease':'a'*16})
            self.assertTrue(process.report()['busy'])
            with self.assertRaises(web.HTTPServiceUnavailable):process.admit()
        self.assertFalse(process.report()['busy'])
        with self.assertRaises(web.HTTPConflict):process.control({'action':'resume','lease':'b'*16})
        process.deadline=0
        process.admit()
        self.assertFalse(process.draining)

    async def test_restart_refuses_busy_and_resumes_admission(self):
        process=RuntimeIdentity('sessions',{})
        async def control(socket,action,**data):
            process.control({'action':action,**data})
            return {'runtime':process.report({'terminals':1})}
        restart=AsyncMock()
        with patch('maintenance.control',side_effect=control):
            with self.assertRaisesRegex(RuntimeError,'busy'):await restart_idle('fixture',restart)
        restart.assert_not_awaited();self.assertFalse(process.draining)

    async def test_restart_only_after_atomic_drain_and_idle_status(self):
        process=RuntimeIdentity('sessions',{})
        async def control(socket,action,**data):
            process.control({'action':action,**data})
            return {'runtime':process.report()}
        async def restart():
            self.assertTrue(process.draining)
            with self.assertRaises(web.HTTPServiceUnavailable):process.admit()
        with patch('maintenance.control',side_effect=control):await restart_idle('fixture',restart)
        self.assertFalse(process.draining)
