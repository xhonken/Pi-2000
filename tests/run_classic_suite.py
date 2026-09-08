"""Run each browser regression against its own disposable loopback database."""
import os,subprocess,time,urllib.request,shutil
from pathlib import Path
root=Path(__file__).resolve().parents[1]
import sys
for test in (sys.argv[1:] or ['file_batch_ui.cjs','tools_ui.cjs','sketch_ui.cjs','editor_sftp_ui.cjs','classic_ui.cjs','classic_accessibility.cjs','taskmanager_ui.cjs','english_ui.cjs']):
    env={**os.environ,'NODE_PATH':'/tmp/win2k-browser-check/node_modules'}
    if test=='editor_sftp_ui.cjs':
        remote=Path('/tmp/win2k-editor-sftp-fixture')
        if remote.exists():shutil.rmtree(remote)
        env['WIN2K_TEST_SFTP_DIR']=str(remote)
    with open('/tmp/win2k-classic-fixture.log','w') as log:
        server=subprocess.Popen([str(root/'.venv/bin/python'),'tests/ui_server.py'],cwd=root,env=env,stdout=log,stderr=log)
        try:
            for attempt in range(100):
                if server.poll() is not None:raise RuntimeError('Fixture exited')
                try:urllib.request.urlopen('http://127.0.0.1:18765',timeout=1);break
                except OSError:time.sleep(.1)
            result=subprocess.run(['node','tests/'+test],cwd=root,env=env)
            if result.returncode:raise SystemExit(result.returncode)
        finally:server.terminate();server.wait(timeout=10)
