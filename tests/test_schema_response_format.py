"""In-memory HTTP mocks only. No runtime, credentials, memory or network access."""
import copy
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import analyze_sources as analyzer
import semantic_discovery as semantic
from semantic_fixture import assessment, context


class SchemaResponseFormatTests(unittest.TestCase):
    def setUp(self):
        self.source = {'candidate_id': 'ISOLATED-CANDIDATE', 'source_id': 'ISOLATED-SOURCE',
            'existing_investigation': True, 'passages': [{'passage_id': 'p1',
            'text': 'An isolated fixture model supports structured user requirements through a compatible API.'}]}
        self.prepared = {'source': self.source}
        self.schema = semantic.output_contract([self.prepared])
        self.messages = semantic.messages([self.prepared], context())
        self.value = assessment(self.source, True)
        self.content = json.dumps({'assessments': [self.value]})
        self.response = MagicMock()
        self.response.status = 200
        self.response.read.return_value = json.dumps({'model': 'nvidia/ISOLATED-FIXTURE',
            'choices': [{'message': {'content': self.content}}]}).encode()
        self.response.__enter__.return_value = self.response
        self.opener = MagicMock(); self.opener.open.return_value = self.response
        build_patch = patch.object(analyzer.urllib.request, 'build_opener', return_value=self.opener)
        open_patch = patch.object(analyzer.urllib.request, 'urlopen', return_value=self.response)
        self.build = build_patch.start(); self.addCleanup(build_patch.stop)
        self.open = open_patch.start(); self.addCleanup(open_patch.stop)

    def request(self, **kwargs):
        return analyzer.request_claims('FIXTURE_ONLY_NOT_A_CREDENTIAL', self.messages,
            max_tokens=4000, max_response_bytes=100_000, **kwargs)

    def body(self):
        return json.loads(self.opener.open.call_args.args[0].data)

    def test_default_json_object_and_plain_mode_are_unchanged(self):
        self.request()
        default = self.body()
        self.assertEqual(default, {'model': analyzer.MODEL, 'stream': False, 'max_tokens': 4000,
            'messages': self.messages, 'chat_template_kwargs': {'enable_thinking': False},
            'response_format': {'type': 'json_object'}})
        self.request(json_output=False)
        self.assertNotIn('response_format', self.body())
        self.assertNotIn('chat_template_kwargs', self.body())

    def test_exact_existing_discovery_schema_forwarded_without_mutation(self):
        before = copy.deepcopy(self.schema)
        result = self.request(response_schema=self.schema)
        body = self.body()
        self.assertTrue(result['ok'])
        self.assertEqual(body['response_format'], {'type': 'json_schema', 'json_schema': {
            'name': 'nextwise_discovery', 'strict': True, 'schema': semantic.output_contract([self.prepared])}})
        self.assertEqual(self.schema, before)
        self.assertEqual(body['messages'], self.messages)
        self.assertEqual(body['chat_template_kwargs'], {'enable_thinking': False})
        self.assertEqual(self.opener.open.call_args.kwargs['timeout'], analyzer.TIMEOUT_SECONDS)
        self.response.read.assert_called_once_with(100_001)
        request = self.opener.open.call_args.args[0]
        self.assertEqual(request.get_header('Meterless-tier-split'), 'off')
        self.assertEqual(request.full_url, analyzer.ENDPOINT)
        redirect = self.build.call_args.args[1]
        self.assertIsNone(redirect.redirect_request(None, None, 302, '', {}, 'https://unapproved.invalid'))
        self.open.assert_not_called()

    def test_valid_response_uses_unchanged_batch_and_evidence_validator(self):
        result = self.request(response_schema=self.schema)
        parsed = semantic.parse_batch(analyzer.message_content(result['data']), [self.prepared])
        self.assertEqual(semantic.validate(parsed[self.source['candidate_id']], self.prepared), self.value)

    def test_provider_rejection_is_visible_one_attempt_no_format_downgrade(self):
        for status in (400, 422, 503):
            with self.subTest(status=status):
                self.opener.open.reset_mock()
                error = {'error': {'message': 'Schema request rejected', 'code': 'unsupported_response_format'}}
                self.opener.open.side_effect = HTTPError(analyzer.ENDPOINT, status, 'Rejected', {},
                                                        io.BytesIO(json.dumps(error).encode()))
                result = self.request(response_schema=self.schema)
                self.assertFalse(result['ok'])
                self.assertEqual(result['http_status'], status)
                self.assertEqual(result['server_error']['code'], 'unsupported_response_format')
                self.opener.open.assert_called_once()
                self.assertEqual(self.body()['response_format']['type'], 'json_schema')
                self.open.assert_not_called()

    def test_transport_failure_and_oversize_do_not_retry_or_downgrade(self):
        self.opener.open.side_effect = URLError('ISOLATED connection failure')
        result = self.request(response_schema=self.schema)
        self.assertFalse(result['ok']); self.opener.open.assert_called_once()
        self.opener.open.reset_mock(); self.opener.open.side_effect = None
        self.response.read.return_value = b'x' * 100_001
        result = self.request(response_schema=self.schema)
        self.assertFalse(result['ok']); self.opener.open.assert_called_once()
        self.assertEqual(self.body()['response_format']['type'], 'json_schema')
        self.open.assert_not_called()

    def test_invalid_options_fail_before_transport(self):
        for bad in ({}, [], 'schema', {'type': 'array'}, False):
            with self.subTest(value_type=type(bad).__name__):
                with self.assertRaises(ValueError): self.request(response_schema=bad)
        with self.assertRaises(ValueError): self.request(response_schema=self.schema, json_output=False)
        self.build.assert_not_called(); self.open.assert_not_called()

    def test_http_success_does_not_attest_schema_enforcement_or_accept_invalid_evidence(self):
        duplicate = copy.deepcopy(self.value)
        content = json.dumps({'assessments': [self.value, duplicate]})
        self.response.read.return_value = json.dumps({'choices': [{'message': {'content': content}}]}).encode()
        result = self.request(response_schema=self.schema)
        self.assertTrue(result['ok'])  # Transport success only.
        with self.assertRaises(semantic.AssessmentError):
            semantic.parse_batch(analyzer.message_content(result['data']), [self.prepared])
        for field, bad in [('source_id', 'wrong'), ('passage_id', 'absent'),
                           ('exact_quote', 'An invented quotation absent from the supplied material.')]:
            invalid = copy.deepcopy(self.value); invalid['evidence'][0][field] = bad
            with self.assertRaises(semantic.AssessmentError): semantic.validate(invalid, self.prepared)
        self.assertEqual(self.body()['response_format']['type'], 'json_schema')


if __name__ == '__main__': unittest.main()
