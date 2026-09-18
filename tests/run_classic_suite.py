"""Run each UI regression with its own socket, state, SSH fixture and artifacts."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

root = Path(__file__).resolve().parents[1]
tests = sys.argv[1:] or json.loads((root/'tests/suites.json').read_text())['ui']
if not (root/'node_modules/playwright/package.json').exists():
    raise SystemExit('Run npm ci in the project first (see docs/TESTING.md).')
results = root/'.test-results'
results.mkdir(exist_ok=True)
run_dir = Path(tempfile.mkdtemp(prefix='ui-', dir=results))
print('UI artifacts:', run_dir, flush=True)
for test in tests:
    if Path(test).name != test or not (root/'tests'/test).is_file():
        raise SystemExit('Unknown UI test: '+test)
    artifacts = run_dir/Path(test).stem
    artifacts.mkdir()
    with tempfile.TemporaryDirectory(prefix='pi2000-ui-') as work, socket.socket() as listener:
        listener.bind(('127.0.0.1',0));listener.listen(128)
        origin='http://127.0.0.1:'+str(listener.getsockname()[1])
        env={**os.environ,'NODE_PATH':str(root/'node_modules'),
             'WIN2K_TEST_URL':origin,'WIN2K_TEST_LISTEN_FD':str(listener.fileno()),
             'WIN2K_TEST_ARTIFACTS':str(artifacts)}
        if test in ('iptv_ui.cjs','iptv_stability_ui.cjs'):
            from iptv_fixture import make_media
            make_media(Path(work)/'media')
            if test=='iptv_stability_ui.cjs':
                from iptv_fixture import make_jitter_media
                make_jitter_media(Path(work)/'media')
            env['WIN2K_TEST_IPTV_MEDIA']=str(Path(work)/'media')
        if test in ('editor_sftp_ui.cjs','utilities_ui.cjs'):
            env['WIN2K_TEST_SFTP_DIR']=str(Path(work)/'sftp')
        if test=='utilities_ui.cjs':env['WIN2K_TEST_SERIAL_PTY']='1'
        with (artifacts/'server.log').open('w') as log:
            server=subprocess.Popen([sys.executable,'tests/ui_server.py'],cwd=root,env=env,
                                    pass_fds=(listener.fileno(),),stdout=log,stderr=log)
            try:
                for attempt in range(150):
                    if server.poll() is not None:raise RuntimeError('Fixture exited; see '+str(artifacts/'server.log'))
                    try:
                        urllib.request.urlopen(origin,timeout=1).close()
                        break
                    except OSError:time.sleep(.1)
                else:raise RuntimeError('Fixture startup timed out')
                subprocess.run(['node','tests/'+test],cwd=root,env=env,check=True,timeout=300)
            finally:
                server.terminate()
                try:server.wait(timeout=15)
                except subprocess.TimeoutExpired:server.kill();server.wait()
