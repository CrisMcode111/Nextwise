"""Offline transport contract tests. Synthetic secrets, no provider connections."""
import copy
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import project_adapters as adapters
import nextwise_app as app


class AdapterTests(unittest.TestCase):
    def setUp(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith(('NEXTWISE_', 'TAVILY_'))}
        p = patch.dict(os.environ, env, clear=True); p.start(); self.addCleanup(p.stop)
        p = patch('socket.socket', side_effect=AssertionError('No external network')); p.start(); self.addCleanup(p.stop)
        self.request = {'messages': [{'role': 'user', 'content': 'Reviewed project evidence'}],
                        'prepared': {'source': {'candidate_id': 'source'}},
                        'context': {'assessment_mode': 'business-brief-v1'}}
        # These are transport-isolation tests, not claim-generation fixtures.
        # The real contract/materialization boundary has its own offline replay.
        for name, kwargs in (
                ('messages', {'side_effect': lambda request: request['messages']}),
                ('contract', {'side_effect': lambda request: adapters.semantic.output_contract(
                    [request['prepared']], request['context'])}),
                ('materialize', {'side_effect': lambda content, request: content})):
            p = patch.object(adapters.output, name, **kwargs)
            p.start(); self.addCleanup(p.stop)
        self.response = {'ok': True, 'http_status': 200, 'data': {'choices': [
            {'finish_reason': 'stop', 'message': {'role': 'assistant', 'content': '{"assessments":[]}'}}]}}

    def test_construction_and_explicit_injection_never_read_credentials(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(adapters.config, 'secret', side_effect=AssertionError('No secret reads')):
            self.assertEqual(adapters.configured_services(), {})
            with patch.dict(os.environ, {'NEXTWISE_PROJECT_PROVIDERS_ENABLED': 'true'}):
                state = app.State(directory)
                self.assertTrue(callable(state.projects.assessor))
                self.assertEqual(state.projects.external_limits, {'discover': 2, 'assess': 4})
                self.assertEqual(state.projects.list(), [])
                self.assertIsNone(app.State(directory, project_services={}).projects.assessor)
            self.assertFalse((Path(directory)/'projects').exists())

    def test_protected_files_loaded_only_for_requested_provider(self):
        with tempfile.TemporaryDirectory() as directory:
            key = Path(directory)/'key'; key.write_text('synthetic-test-only', encoding='utf-8')
            with patch.dict(os.environ, {'TAVILY_API_KEY_FILE': str(key)}), \
                 patch.object(adapters.tavily, 'search', return_value=[]) as search:
                self.assertEqual(adapters.search('reviewed public query'), [])
                search.assert_called_once_with('reviewed public query', 'synthetic-test-only')
            with patch.dict(os.environ, {'NEXTWISE_METERLESS_TOKEN_FILE': str(key),
                                        'NEXTWISE_METERLESS_URL': 'https://gateway.example',
                                        'NEXTWISE_MODEL': 'approved/model'}), \
                 patch.object(adapters.analyzer, 'request_claims', return_value=self.response) as model:
                self.assertEqual(adapters.assess(self.request), '{"assessments":[]}')
                self.assertEqual(model.call_args.kwargs['endpoint'], 'https://gateway.example/v1/chat/completions')
                self.assertEqual(model.call_args.kwargs['model'], 'approved/model')

    def test_plain_http_remote_and_missing_token_fail_before_transport(self):
        with patch.object(adapters.analyzer, 'request_claims') as model:
            with patch.dict(os.environ, {'NEXTWISE_METERLESS_URL': 'http://private.example:8088'}):
                with self.assertRaises(adapters.config.ConfigError): adapters.assess(self.request)
            with self.assertRaises(adapters.config.ConfigError): adapters.assess(self.request)
            model.assert_not_called()

    def test_incomplete_tool_error_and_echo_responses_fail_closed(self):
        cases = [{'ok': False, 'raw_body': 'synthetic-test-only'}, {'ok': True, 'http_status': 200, 'data': []}]
        for update in ({'finish_reason': 'length'}, {'finish_reason': 'tool_calls'},
                       {'message': {'role': 'assistant', 'content': 'synthetic-test-only'}},
                       {'message': {'role': 'assistant', 'content': '{}', 'tool_calls': [{}]}},
                       {'message': {'role': 'user', 'content': '{}'}}):
            value = copy.deepcopy(self.response); value['data']['choices'][0].update(update); cases.append(value)
        for value in cases:
            with self.subTest(case=len(str(value))), \
                 patch.object(adapters.config, 'secret', return_value='synthetic-test-only'), \
                 patch.object(adapters.analyzer, 'request_claims', return_value=value) as model:
                with self.assertRaises(ValueError) as error: adapters.assess(self.request)
                self.assertNotIn('synthetic-test-only', str(error.exception))
                model.assert_called_once()

    def test_existing_meterless_transport_uses_configured_route_and_clears_auth(self):
        response = io.BytesIO(json.dumps(self.response['data']).encode()); response.status = 200
        captured = []
        def open_request(request, timeout):
            captured.append(request)
            self.assertEqual(request.full_url, 'https://gateway.example/v1/chat/completions')
            self.assertEqual(request.get_header('Authorization'), 'Bearer synthetic-test-only')
            payload = json.loads(request.data)
            self.assertEqual(payload['model'], 'approved/model')
            self.assertEqual(payload['response_format']['type'], 'json_schema')
            self.assertFalse(payload['stream'])
            self.assertNotIn('Defer Version 1', json.dumps(payload))
            return response
        with patch.dict(os.environ, {'NEXTWISE_METERLESS_URL': 'https://gateway.example', 'NEXTWISE_MODEL': 'approved/model'}), \
             patch.object(adapters.config, 'secret', return_value='synthetic-test-only'), \
             patch.object(adapters.analyzer.urllib.request, 'build_opener', return_value=SimpleNamespace(open=open_request)) as opener:
            self.assertEqual(adapters.assess(self.request), '{"assessments":[]}')
            opener.assert_called_once()
            self.assertIsNone(captured[0].get_header('Authorization'))


if __name__ == '__main__': unittest.main()
