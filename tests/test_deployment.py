import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
from deployment import selected, stage, activate, verify, backup_files

class DeploymentTests(unittest.TestCase):
    def test_nested_modules_shared_inventory_and_private_exclusion(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'source';root.mkdir()
            (root/'deployment.json').write_text(json.dumps({'format':1,'server':['server/**/*'],'web':['index.html','assets/**/*']}))
            for name,text in {'server/core/nested.py':'answer=42','server/AGENTS.md':'private','server/private.key':'private','server/__pycache__/junk.py':'private','server/venv/not_app.py':'private','index.html':'<script src="assets/core/app.js"></script>','assets/core/app.js':'const answer=42;','assets/PROJECT-HISTORY.local.md':'private'}.items():
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
            for component in ['server','web']:
                staging=Path(temp)/('stage-'+component);dest=Path(temp)/component
                stage(root,staging,component,{'version':'fixture','build':'old'})
                activate(staging,dest,component)
                files=[p.relative_to(dest).as_posix() for p in backup_files(dest,component)]
                self.assertIn('core/nested.py' if component=='server' else 'assets/core/app.js',files)
                self.assertFalse(any('private' in n or 'AGENTS' in n or 'local.md' in n or 'venv' in n for n in files))
                self.assertEqual(verify(dest,component)['component'],component)
            self.assertIn('?v=',(Path(temp)/'web/index.html').read_text())
            # Stale files are removed only if recorded in the previous inventory.
            (root/'server/core/nested.py').unlink();(root/'server/new.py').write_text('answer=43')
            dest=Path(temp)/'server';(dest/'unrelated.txt').write_text('keep')
            stage(root,Path(temp)/'next','server',{'build':'new'})
            activate(Path(temp)/'next',dest,'server')
            self.assertFalse((dest/'core/nested.py').exists());self.assertTrue((dest/'unrelated.txt').exists())
            # Verification fails before activation can damage the old installation.
            (Path(temp)/'next/new.py').write_text('corruption')
            with self.assertRaises(ValueError):activate(Path(temp)/'next',dest,'server')
            self.assertEqual((dest/'new.py').read_text(),'answer=43')

    def test_source_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'server').mkdir();(root/'deployment.json').write_text('{"format":1,"server":["server/**/*.py"]}')
            (root/'server/escape.py').symlink_to('/etc/passwd')
            with self.assertRaises(ValueError): selected(root,'server')
