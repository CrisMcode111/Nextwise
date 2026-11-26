"""Run the offline browser journey, restart and follow-up checks with temporary data.

Requires Chrome at the path used by integrated_workflow_browser.py, websocket-client,
and the Node version required by the existing H-MEM bridge. No providers are called.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='nextwise-integrated-browser-', ignore_cleanup_errors=True) as temp:
    env = dict(os.environ, NEXTWISE_DEMO_MEMORY=str(Path(temp)/'memory'),
               NEXTWISE_DEMO_RESULT=str(Path(temp)/'result.json'), NEXTWISE_DEMO_PORT='8772')
    def start():
        process = subprocess.Popen([sys.executable, 'scripts/demo_integrated_local.py'], cwd=ROOT,
                                   env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            if process.poll() is not None:
                raise RuntimeError('Offline demo server failed to start.')
            try:
                urllib.request.urlopen('http://127.0.0.1:8772/health/live', timeout=1).close()
                return process
            except OSError:
                time.sleep(.2)
        process.terminate()
        raise RuntimeError('Offline demo server did not become ready.')
    def browser(*args):
        subprocess.run([sys.executable, 'tests/integrated_workflow_browser.py', *args],
                       cwd=ROOT, env=env, check=True, timeout=300)
    server = start()
    try:
        browser()
        server.terminate(); server.wait(timeout=15)
        server = start()
        browser('--reopen')
        browser('--second')
        browser('--clarify')
        browser('--rejected')
    finally:
        server.terminate(); server.wait(timeout=15)
