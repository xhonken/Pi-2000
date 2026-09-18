from contextlib import closing
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
from backup import snapshot
from installation import APPLICATION_ID
from recovery import export_encrypted

@unittest.skipUnless(shutil.which('age') and shutil.which('age-keygen'),'Install age for encrypted backup round-trip checks')
class ExportTests(unittest.IsolatedAsyncioTestCase):
    async def test_encrypted_roundtrip_and_corruption_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);state=root/'state';state.mkdir()
            with closing(sqlite3.connect(state/'admin.sqlite3')) as db:
                db.execute(f'PRAGMA application_id={APPLICATION_ID}')
                db.execute('CREATE TABLE fixture(id INTEGER)');db.commit()
            archive=await snapshot(state,root/'backups','',None)
            key=root/'identity.txt'
            subprocess.run(['age-keygen','-o',str(key)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            recipient=subprocess.check_output(['age-keygen','-y',str(key)],text=True).strip()
            output=root/'backup.tar.age'
            with self.assertRaisesRegex(RuntimeError,'different mounted'):export_encrypted(archive,output,recipient)
            export_encrypted(archive,output,recipient,allow_same_device=True)
            self.assertFalse(output.stat().st_mode & 0o077)
            self.assertTrue(output.with_suffix('.age.sha256').exists())
            decrypted=subprocess.check_output(['age','--decrypt','-i',str(key),str(output)],stderr=subprocess.DEVNULL)
            self.assertEqual(decrypted,archive.read_bytes())
            with self.assertRaises(RuntimeError):export_encrypted(archive,output,recipient,allow_same_device=True)
            data=bytearray(output.read_bytes());data[-1]^=1;output.write_bytes(data)
            bad=subprocess.run(['age','--decrypt','-i',str(key),str(output)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            self.assertNotEqual(bad.returncode,0)
