"""Local subprocess smoke test with loopback-only fake SQL; not a clean-host deployment test."""
import http.server
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener

ROOT = Path(__file__).resolve().parents[1]


class RuntimeProcessTests(unittest.TestCase):
    def test_unattended_process_with_local_node_and_fake_sql(self):
        queries = []
        class SQL(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_): pass
            def do_POST(self):
                if self.path != '/api/v1.0/sql-editor/sqls/run':
                    self.send_error(404); return
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                queries.append(body['sql'])
                raw = b'{"data":{"columns":["nextwise_health"],"rows":[[1]]}}'
                self.send_response(200); self.send_header('Content-Length', str(len(raw)))
                self.end_headers(); self.wfile.write(raw)
        sql = http.server.ThreadingHTTPServer(('127.0.0.1', 0), SQL)
        self.addCleanup(sql.server_close)
        thread = threading.Thread(target=sql.serve_forever, daemon=True); thread.start()
        self.addCleanup(sql.shutdown)
        with socket.socket() as reservation:
            reservation.bind(('127.0.0.1', 0)); port = reservation.getsockname()[1]
        with tempfile.TemporaryDirectory(prefix='nextwise-native-runtime-') as tmp:
            for name in ('nemotron-lightning-requirements-extraction', 'update-discovery'):
                folder = Path(tmp) / name; folder.mkdir()
                (folder / 'state.json').write_text('{"seq":1,"records":[{"fixture":true}]}')
                (folder / 'ledger.jsonl').write_text('{"fixture":true}\n')
            before = {str(p): p.read_bytes() for p in Path(tmp).rglob('*') if p.is_file()}
            env = {k: v for k, v in os.environ.items() if not k.startswith('NEXTWISE_') and not k.startswith('TAVILY_API_KEY')}
            dependency_url = f'http://127.0.0.1:{sql.server_port}'
            env.update(NEXTWISE_MEMORY_ROOT=tmp, NEXTWISE_PORT=str(port), NEXTWISE_HOST='127.0.0.1',
                       NEXTWISE_ZETARIS_API_KEY='SYNTHETIC_LOCAL_TEST_SECRET', NEXTWISE_ZETARIS_URL=dependency_url,
                       NEXTWISE_METERLESS_URL=dependency_url, NEXTWISE_REQUIRE_METERLESS='true')
            process = subprocess.Popen([sys.executable, '-B', 'scripts/serve_runtime.py'], cwd=ROOT, env=env,
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                opener = build_opener(ProxyHandler({}))
                deadline = time.monotonic() + 20
                while True:
                    if process.poll() is not None:
                        stdout, stderr = process.communicate()
                        self.fail('Unattended startup exited: ' + stdout + stderr)
                    try:
                        with opener.open(f'http://127.0.0.1:{port}/health/live', timeout=1) as result:
                            self.assertEqual(json.load(result), {'status': 'alive'})
                        break
                    except (URLError, TimeoutError):
                        if time.monotonic() >= deadline: self.fail('Local runtime did not become live.')
                        time.sleep(.05)
                self.assertEqual(queries, [])
                with opener.open(f'http://127.0.0.1:{port}/health/ready', timeout=15) as result:
                    body = json.load(result)
                self.assertTrue(body['ready'], body)
                self.assertEqual(queries, ['SELECT 1 AS nextwise_health'])
                self.assertNotIn('SYNTHETIC_LOCAL_TEST_SECRET', json.dumps(body))
                self.assertEqual(before, {str(p): p.read_bytes() for p in Path(tmp).rglob('*') if p.is_file()})
            finally:
                process.terminate()
                stdout, stderr = process.communicate(timeout=10)
            self.assertNotIn('SYNTHETIC_LOCAL_TEST_SECRET', stdout + stderr)
            self.assertIn('unattended listener started', stdout)
            if os.name != 'nt': self.assertEqual(process.returncode, 0)


if __name__ == '__main__':
    unittest.main()
