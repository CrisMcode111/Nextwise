"""Synthetic transport only; real official H-MEM in temporary isolated storage."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import reassess_opportunity_once as once
import semantic_discovery as semantic
import update_discovery as discovery
from semantic_fixture import assessment, context, Transport
from test_update_discovery import Fixture, NOW


class OpportunityOnceTests(unittest.TestCase):
    def initialize(self, tmp):
        store = discovery.Store(tmp)
        fixture = Fixture()
        fixture.page = 'A model supports structured outputs for preserving explicit requirements in a compatible API. ' * 8
        with patch.object(semantic, 'project_context', return_value=context()):
            store.run(fixture, now=NOW)
            # Existing old failed outcomes/allowance must survive separately.
            old = semantic.run(store, 'FIXTURE_ONLY', context(), lambda *a: {'ok': False, 'http_status': 503}, lambda m: None)
        fixture_id = next(i['id'] for i in old['items'].values() if i['source'] == discovery.config()['pages'][0])
        scope = patch.object(once, 'CANDIDATE', fixture_id)
        scope.start()
        self.addCleanup(scope.stop)
        return store, copy.deepcopy(old)

    def transport(self, invalid=False, route=False, cache=False, echo=False):
        calls = []
        def request(token, messages):
            calls.append(messages)
            sources = json.loads(messages[1]['content'])['untrusted_sources']
            self.assertEqual(len(sources), 1)
            self.assertEqual(sources[0]['candidate_id'], once.CANDIDATE)
            value = assessment(sources[0], True)
            if invalid: value.pop('source_observation')
            data = {'model': once.EXPECTED_MODEL, 'usage': {'prompt_tokens': 100, 'completion_tokens': 200, 'total_tokens': 300},
                'meterless': {'winning_route': {'provider': 'other' if route else 'nvidia', 'model': once.EXPECTED_MODEL},
                    'from_cache': cache, 'receipt_id': 'ISOLATED_FIXTURE_RECEIPT'},
                'choices': [{'message': {'content': json.dumps({'assessments': [value]})}, 'finish_reason': 'stop'}]}
            if echo: data['echo'] = token
            return {'ok': True, 'http_status': 200, 'duration_seconds': .01, 'data': data}
        return request, calls

    def test_one_candidate_acceptance_briefing_replay_restart_prior_history_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(semantic, 'project_context', return_value=context()):
            store, old = self.initialize(tmp)
            request, calls = self.transport()
            report = once.run_once(store, 'FIXTURE_PRIVATE_TOKEN', context(), request)
            self.assertEqual(len(calls), 1)
            self.assertTrue(report['assessment_persisted']); self.assertTrue(report['briefing_persisted'])
            self.assertFalse(report['human_decision_written'])
            state = discovery.Store(tmp).read()
            self.assertEqual(state.get('opportunity_decisions', []), [])
            self.assertEqual(state['opportunity_recommendations'][0]['recommended_choice'], 'Defer')
            self.assertEqual(state['runs'], old['runs']); self.assertEqual(state['baselines'], old['baselines'])
            for key, value in old['semantic_cache'].items(): self.assertEqual(state['semantic_cache'][key], value)
            self.assertEqual(state['semantic_requests'][:-1], old['semantic_requests'])
            for cid, item in old['items'].items():
                self.assertEqual(state['items'][cid]['revisions'], item['revisions'])
                if cid != once.CANDIDATE: self.assertEqual(state['items'][cid], item)
            self.assertEqual(once.replay(once.directory(store))['status'], 'validated')
            self.assertEqual(once.run_once(store, '', context(), request)['new_requests_sent'], 0)
            self.assertEqual(len(calls), 1)
            self.assertNotIn('FIXTURE_PRIVATE_TOKEN', ''.join(p.read_text(encoding='utf-8') for p in once.directory(store).glob('*.json')))

    def test_schema_route_cache_failure_and_credential_echo_preserve_old_assessments(self):
        for options in ({'invalid': True}, {'route': True}, {'cache': True}, {'echo': True}):
            with self.subTest(options=options), tempfile.TemporaryDirectory() as tmp, patch.object(semantic, 'project_context', return_value=context()):
                store, old = self.initialize(tmp)
                request, calls = self.transport(**options)
                report = once.run_once(store, 'FIXTURE_PRIVATE_TOKEN', context(), request)
                self.assertEqual(report['validation_status'], 'failed')
                self.assertFalse(report['assessment_persisted']); self.assertFalse(report['briefing_persisted'])
                state = store.read()
                for field in ('items', 'semantic_cache', 'proposals', 'runs', 'baselines'):
                    self.assertEqual(state[field], old[field])
                self.assertNotIn('opportunity_recommendations', state)
                self.assertEqual(once.replay(once.directory(store))['status'], 'failed')
                self.assertEqual(once.run_once(store, '', context(), request)['new_requests_sent'], 0)
                self.assertEqual(len(calls), 1)

    def test_interruption_and_transport_failure_cannot_retry(self):
        for interrupted in (False, True):
            with self.subTest(interrupted=interrupted), tempfile.TemporaryDirectory() as tmp:
                store, old = self.initialize(tmp)
                calls = []
                def fail(*args):
                    calls.append(1)
                    if interrupted: raise KeyboardInterrupt()
                    return {'ok': False, 'http_status': 503}
                if interrupted:
                    with self.assertRaises(KeyboardInterrupt): once.run_once(store, 'FIXTURE', context(), fail)
                else:
                    result = once.run_once(store, 'FIXTURE', context(), fail)
                    self.assertEqual(result['validation_failure']['code'], 'transport')
                self.assertEqual(once.run_once(store, '', context(), fail)['new_requests_sent'], 0)
                self.assertEqual(len(calls), 1)
                self.assertEqual(store.read()['semantic_cache'], old['semantic_cache'])

    def test_post_request_context_change_blocks_assessment_and_briefing(self):
        with tempfile.TemporaryDirectory() as tmp:
            store, old = self.initialize(tmp)
            request, calls = self.transport()
            changed = context(); changed['human_decision']['rationale'] = 'ISOLATED context has changed'
            with patch.object(semantic, 'project_context', return_value=changed):
                report = once.run_once(store, 'FIXTURE_PRIVATE_TOKEN', context(), request)
            self.assertEqual(report['validation_status'], 'validated')
            self.assertEqual(report['error_category'], 'post_request_evidence_check')
            self.assertFalse(report['assessment_persisted'])
            self.assertEqual(store.read()['semantic_cache'], old['semantic_cache'])

    def test_malformed_response_is_retained_without_echo_and_without_promotion(self):
        for echo in (False, True):
            with self.subTest(echo=echo), tempfile.TemporaryDirectory() as tmp:
                store, old = self.initialize(tmp)
                data = {'model': once.EXPECTED_MODEL, 'choices': ['FIXTURE_PRIVATE_TOKEN' if echo else 'malformed fixture choice']}
                report = once.run_once(store, 'FIXTURE_PRIVATE_TOKEN', context(), lambda *a: {'ok': True, 'http_status': 200, 'data': data})
                raw = (once.directory(store) / 'response.json').read_text(encoding='utf-8')
                artifact = json.loads(raw)
                self.assertEqual(artifact['data'], None if echo else data)
                self.assertNotIn('FIXTURE_PRIVATE_TOKEN', raw)
                self.assertEqual(report['validation_status'], 'failed')
                self.assertEqual(store.read()['semantic_cache'], old['semantic_cache'])


if __name__ == '__main__': unittest.main()
