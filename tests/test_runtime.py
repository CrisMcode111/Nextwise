"""Runtime configuration, startup and health checks. No external services or inference."""
import contextlib
from dataclasses import replace
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import runtime_config as config
import runtime_health as health
import nextwise_app as app
import start_runtime


def dispatch(state, path, *, host='127.0.0.1:8765', origin=None, method='GET'):
    class Connection:
        def __init__(self): self.output = bytearray()
        def makefile(self, *_):
            headers = [f'{method} {path} HTTP/1.1', 'Host: ' + host,
                       f'Cookie: nextwise={state.cookie}', 'Connection: close']
            if origin: headers.append('Origin: ' + origin)
            return io.BytesIO(('\r\n'.join(headers) + '\r\n\r\n').encode())
        def sendall(self, data): self.output.extend(data)
    connection = Connection()
    app.make_handler(state, lambda _: {'fixture': True})(connection, ('127.0.0.1', 0), SimpleNamespace(server_port=8765))
    headers, body = bytes(connection.output).split(b'\r\n\r\n', 1)
    return int(headers.split()[1]), json.loads(body), headers.decode()


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith('NEXTWISE_') and not k.startswith('TAVILY_API_KEY')}
        self.environment = patch.dict(os.environ, env, clear=True)
        self.environment.start(); self.addCleanup(self.environment.stop)
        self.socket_guard = patch('socket.socket', side_effect=AssertionError('External network forbidden'))
        self.socket_guard.start(); self.addCleanup(self.socket_guard.stop)

    def test_defaults_preserve_local_paths_and_routes(self):
        c = config.settings()
        self.assertEqual(c.artifact_root, ROOT)
        self.assertEqual(c.memory_root, ROOT / 'data/memory/hmem')
        self.assertEqual(c.completions_url, 'http://127.0.0.1:8088/v1/chat/completions')
        self.assertEqual(c.port, 8765)
        self.assertFalse(c.require_meterless)

    def test_invalid_config_redacts_values(self):
        cases = {'NEXTWISE_ZETARIS_URL': 'https://SECRET:SECRET@example.invalid/',
                 'NEXTWISE_METERLESS_URL': 'http://host/?SECRET', 'NEXTWISE_PORT': 'SECRET',
                 'NEXTWISE_ZETARIS_ORG_ID': 'SECRET\nBAD', 'NEXTWISE_PUBLIC_ORIGIN': 'https://host/path',
                 'NEXTWISE_REQUIRE_METERLESS': 'SECRET', 'NEXTWISE_DEPENDENCY_TIMEOUT': '0'}
        for key, value in cases.items():
            with self.subTest(key=key), patch.dict(os.environ, {key: value}):
                with self.assertRaises(config.ConfigError) as error: config.settings()
                self.assertNotIn('SECRET', str(error.exception))

    def test_secret_files_conflicts_missing_and_invalid_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'key'; p.write_text('  FIXTURE_SECRET\n', encoding='utf-8')
            with patch.dict(os.environ, {'NEXTWISE_ZETARIS_API_KEY_FILE': str(p)}):
                self.assertEqual(config.secret('NEXTWISE_ZETARIS_API_KEY'), 'FIXTURE_SECRET')
                with patch.dict(os.environ, {'NEXTWISE_ZETARIS_API_KEY': 'DIRECT_SECRET'}):
                    with self.assertRaises(config.ConfigError): config.secret('NEXTWISE_ZETARIS_API_KEY')
                for raw in (b'x' * 16385, b'INVALID\nSECRET', b'\xff'):
                    p.write_bytes(raw)
                    with self.assertRaises(config.ConfigError) as error: config.secret('NEXTWISE_ZETARIS_API_KEY')
                    self.assertNotIn('SECRET', str(error.exception))
            with self.assertRaises(config.ConfigError): config.secret('NEXTWISE_ZETARIS_API_KEY', required=True)

    def test_relocated_configuration_reaches_all_backend_adapters(self):
        # Fresh imports verify constants, not just configuration parsing. No bridge/network calls.
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ, NEXTWISE_ARTIFACT_ROOT=tmp, NEXTWISE_MEMORY_ROOT=str(Path(tmp) / 'private'),
                       NEXTWISE_ZETARIS_URL='http://sql.internal:9999/prefix', NEXTWISE_ZETARIS_ORG_ID='org-2',
                       NEXTWISE_METERLESS_URL='https://gateway.internal', NEXTWISE_PORT='9876', NEXTWISE_MODEL='fixture/model')
            code = '''import sys,json;sys.path.insert(0,'scripts')
import nextwise_app as a,analyze_sources as m,collect_sources as c,validate_zetaris_profile as v
print(json.dumps([str(a.ROOT),str(a.memory.DEFAULT_MEMORY_ROOT),str(a.integration.SNAPSHOT),str(c.ROOT),m.ENDPOINT,m.MODEL,a.PORT,v.ENDPOINT,a.integration.Client('fixture').config.zetaris_org]))'''
            p = subprocess.run([sys.executable, '-B', '-c', code], env=env, cwd=ROOT, capture_output=True, text=True, check=True)
            actual = json.loads(p.stdout)
            self.assertEqual(actual, [str(Path(tmp).resolve()), str(Path(tmp) / 'private'),
                str(Path(tmp) / 'data/zetaris_exports/20261024T151413Z-fdf0c15b-csv-5fa0db458643'),
                str(Path(tmp).resolve()), 'https://gateway.internal/v1/chat/completions', 'fixture/model', 9876,
                'http://sql.internal:9999/prefix/api/v1.0/sql-editor/sqls/run', 'org-2'])

    def fixture_memory(self, directory):
        for name in (health.INVESTIGATION, 'update-discovery'):
            folder = Path(directory) / name; folder.mkdir()
            (folder / 'state.json').write_text(json.dumps({'seq': 1, 'records': [{'fixture': True}]}))
            (folder / 'ledger.jsonl').write_text('{"fixture":true}\n')

    def test_offline_health_never_invokes_bridge_or_network_and_suppresses_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.fixture_memory(tmp)
            c = replace(config.settings(), memory_root=Path(tmp))
            with patch('subprocess.run', return_value=SimpleNamespace(stdout=b'v24.22.2\n')), \
                 patch.object(app.memory, 'call_bridge', side_effect=AssertionError('Production bridge forbidden')):
                report = health.check_dependencies(c, key='FIXTURE_SECRET')
            self.assertTrue(report['ready'], report)
            self.assertEqual(report['model_requests'], 0)
            self.assertNotIn('FIXTURE_SECRET', json.dumps(report))
            self.assertEqual(report['checks'][-1]['status'], 'not_checked')

    def test_missing_corrupt_and_readonly_memory_fail_without_initializing_or_repair(self):
        for problem in ('missing', 'corrupt', 'readonly'):
            with self.subTest(problem=problem), tempfile.TemporaryDirectory() as tmp:
                if problem != 'missing': self.fixture_memory(tmp)
                if problem == 'corrupt': (Path(tmp) / health.INVESTIGATION / 'ledger.jsonl').write_text('broken')
                before = {str(p): p.read_bytes() for p in Path(tmp).rglob('*') if p.is_file()}
                c = replace(config.settings(), memory_root=Path(tmp))
                with patch('subprocess.run', return_value=SimpleNamespace(stdout=b'v24.22.2\n')), \
                     patch.object(health.os, 'access', return_value=problem != 'readonly'):
                    report = health.check_dependencies(c, key='FIXTURE')
                self.assertFalse(report['ready'])
                self.assertEqual(before, {str(p): p.read_bytes() for p in Path(tmp).rglob('*') if p.is_file()})

    def test_network_health_only_selects_one_and_tcp_probes_gateway(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.fixture_memory(tmp)
            c = replace(config.settings(), memory_root=Path(tmp))
            with patch('subprocess.run', return_value=SimpleNamespace(stdout=b'v24.22.2\n')), \
                 patch.object(app.integration, 'Client') as client, \
                 patch.object(config.Settings, 'meterless_probe', side_effect=OSError('FIXTURE_SECRET')):
                client.return_value.sql.return_value = (['nextwise_health'], [['1']])
                report = health.check_dependencies(c, network=True, key='FIXTURE_SECRET')
                self.assertTrue(report['ready'])  # Model gateway optional for saved investigation.
                client.return_value.sql.assert_called_once_with('SELECT 1 AS nextwise_health')
                required = health.check_dependencies(replace(c, require_meterless=True), network=True, key='FIXTURE_SECRET')
                self.assertFalse(required['ready'])
                client.side_effect = ValueError('FIXTURE_SECRET')
                self.assertFalse(health.check_dependencies(c, network=True, key='FIXTURE_SECRET')['ready'])
                self.assertNotIn('FIXTURE_SECRET', json.dumps(required))

    def test_missing_node_and_credentials_are_actionable(self):
        with patch('subprocess.run', side_effect=FileNotFoundError('PRIVATE_PATH')):
            report = health.check_dependencies()
        failures = {c['name']: c for c in report['checks'] if c['status'] == 'error'}
        self.assertIn('node_hmem_runtime', failures)
        self.assertIn('zetaris_credentials', failures)
        self.assertNotIn('PRIVATE_PATH', json.dumps(report))

    def test_configured_sql_url_org_and_health_timeout_reach_transport(self):
        with patch.dict(os.environ, {'NEXTWISE_ZETARIS_URL': 'http://fixture.internal:9999/proxy',
                                    'NEXTWISE_ZETARIS_ORG_ID': 'fixture-org'}):
            client = app.integration.Client('FIXTURE_SECRET', timeout=2)
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b'{"data":{"columns":["n"],"rows":[[1]]}}'
        client.opener.open = MagicMock(return_value=response)
        client.sql('SELECT 1')
        request = client.opener.open.call_args.args[0]
        self.assertEqual(request.full_url, 'http://fixture.internal:9999/proxy/api/v1.0/sql-editor/sqls/run')
        self.assertEqual(request.get_header('X-org-id'), 'fixture-org')
        self.assertEqual(client.opener.open.call_args.kwargs['timeout'], 2)
        self.assertIsNone(request.get_header('Authorization'))

    def test_liveness_readiness_and_host_origin_checks_in_real_handler(self):
        state = app.State(api_key='FIXTURE_SECRET')
        self.assertEqual(dispatch(state, '/health/live')[1], {'status': 'alive'})
        state.key = None
        status, body, _ = dispatch(state, '/api/load', origin='http://127.0.0.1:8765', method='POST')
        self.assertEqual(status, 401)
        self.assertIn('restart the backend', body['message'])
        state.key = 'FIXTURE_SECRET'
        with patch.object(health, 'check_dependencies', return_value={'ready': False}) as probe:
            self.assertEqual(dispatch(state, '/health/ready')[0], 503)
            probe.assert_called_once_with(state.config, network=True, key='FIXTURE_SECRET')
        self.assertEqual(dispatch(state, '/health/live', host='evil.invalid')[0], 403)
        with patch.dict(os.environ, {'NEXTWISE_PUBLIC_ORIGIN': 'https://nextwise.example'}):
            state = app.State(api_key='FIXTURE_SECRET')
            self.assertEqual(dispatch(state, '/health/live', host='nextwise.example')[0], 200)
            self.assertEqual(dispatch(state, '/api/load', host='nextwise.example', origin='https://nextwise.example', method='POST')[0], 200)
            self.assertEqual(dispatch(state, '/api/load', host='nextwise.example', origin='https://evil.invalid', method='POST')[0], 403)

    def test_unattended_missing_dependency_never_binds_or_prompts(self):
        with patch.object(health, 'check_dependencies', return_value={'ready': False}), \
             patch.object(app, 'LocalHTTPServer') as server, patch.object(app.getpass, 'getpass') as prompt, \
             contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(app.main(['--unattended']), 1)
            server.assert_not_called(); prompt.assert_not_called()

    def test_unattended_starts_without_console_and_closes_on_interrupt(self):
        output = io.StringIO()
        with patch.dict(os.environ, {'NEXTWISE_ZETARIS_API_KEY': 'FIXTURE_SECRET'}), \
             patch.object(health, 'check_dependencies', return_value={'ready': True}), \
             patch.object(app, 'LocalHTTPServer') as server, patch.object(app.getpass, 'getpass') as prompt, \
             contextlib.redirect_stdout(output):
            server.return_value.serve_forever.side_effect = KeyboardInterrupt
            self.assertEqual(app.main(['--unattended']), 0)
            server.return_value.server_close.assert_called_once()
            prompt.assert_not_called()
        self.assertNotIn('FIXTURE_SECRET', output.getvalue())

    def test_service_launcher_only_uses_supplied_existing_stacks_and_never_resets_volumes(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Path(tmp) / 'runtime.env'; env.write_text('FIXTURE=1')
            external = Path(tmp) / 'existing.yaml'; external.write_text('services: {}')
            steps = start_runtime.commands(env, [external])
            self.assertEqual(steps[0][0], external.parent)
            self.assertEqual(steps[0][1][-1], 'start')
            self.assertNotIn('up', steps[0][1])
            self.assertIn('--wait', steps[-1][1])
            for _, command in steps:
                self.assertTrue(set(command).isdisjoint({'down', '-v', 'rm', '--force-recreate'}))
            with self.assertRaises(ValueError): start_runtime.commands(env, [Path(tmp) / 'absent'])

    def test_wrapper_reports_invalid_configuration_without_traceback(self):
        p = subprocess.run([sys.executable, '-B', 'scripts/serve_runtime.py'], cwd=ROOT,
            env=dict(os.environ, NEXTWISE_ZETARIS_URL='https://SECRET:SECRET@invalid'), capture_output=True, text=True)
        self.assertEqual(p.returncode, 1)
        self.assertIn('NEXTWISE_ZETARIS_URL', p.stderr)
        self.assertNotIn('SECRET', p.stderr)
        self.assertNotIn('Traceback', p.stderr)

    def test_external_start_failure_stops_before_backend_and_redacts_docker_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Path(tmp) / 'runtime.env'; env.write_text('FIXTURE=1')
            external = Path(tmp) / 'existing.yaml'; external.write_text('services: {}')
            error = io.StringIO()
            with patch.object(start_runtime.subprocess, 'run', return_value=SimpleNamespace(returncode=1, stderr=b'SECRET')) as run, \
                 contextlib.redirect_stderr(error):
                self.assertEqual(start_runtime.main(['--env-file', str(env), '--external-compose', str(external)]), 1)
            self.assertEqual(run.call_count, 1)
            self.assertIn('Existing service container startup failed', error.getvalue())
            self.assertNotIn('SECRET', error.getvalue())


if __name__ == '__main__':
    unittest.main()
