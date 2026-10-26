"""Simulated assessments and sources, real isolated official H-MEM. No remote IO."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
import uuid
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import opportunity_workflow as workflow
import semantic_discovery as semantic
import update_discovery as discovery
from semantic_fixture import context, Transport
from test_update_discovery import Fixture, NOW
from decision_fixture import app, call, initialize


class OpportunityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='nextwise-opportunity-fixture-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.ctx = context()
        self.mock_context = patch.object(semantic, 'project_context', return_value=self.ctx)
        self.mock_context.start()
        self.addCleanup(self.mock_context.stop)
        # Catch accidental real network/model use in the implementation under test.
        self.no_network = patch.object(semantic.analyzer, 'request_claims', side_effect=AssertionError('No live model allowed'))
        self.no_network.start()
        self.addCleanup(self.no_network.stop)
        self.store = discovery.Store(self.root)
        self.fixture = Fixture()
        self.fixture.feed = self.fixture.feed.replace(b'Publisher summary', b'ISOLATED source paragraph about structured task interfaces and explicit constraints.')
        self.fixture.page = 'A language model supports structured outputs for user requirements through a compatible API. ' * 8
        self.before = self.store.run(self.fixture, now=NOW)
        self.state = semantic.run(self.store, 'ISOLATED_FIXTURE', self.ctx, Transport(), lambda m: None)
        self.item = next(i for i in self.state['items'].values() if i['semantic_assessment']['category'] == 'potential relevance')

    def prepare(self, item=None):
        item = item or self.item
        return workflow.prepare(self.store, item['id'], item['content_sha256'], item['semantic_assessment']['cache_key'])

    def body(self, recommendation=None, **changes):
        r = recommendation or self.prepare()['opportunity_recommendations'][-1]
        return dict(explicit_action='record_opportunity_decision', recommendation_id=r['id'],
            recommendation_sha256=r['record_sha256'], choice='Test', rationale='ISOLATED TEST: review a bounded plan first.',
            next_action='ISOLATED TEST: agree acceptance criteria; no execution.', expected_head=None,
            request_id=str(uuid.uuid4()), **changes)

    def test_accepted_briefing_decision_retry_restart_amend_preserves_original_history(self):
        memory = initialize(self.root)
        original = call(self.root, 'decision_save', decision=dict(explicit_action='record_human_decision',
            choice='Defer', rationale='ISOLATED genuine-history preservation fixture, never a real decision.', next_action=None,
            request_id=str(uuid.uuid4()), expected_head=None, context=dict(manifest_id=memory['manifest_id'],
                artifact_hashes=memory['artifact_hashes'], run_id=memory['evaluation_results']['run_id'])))
        self.assertTrue(original['ok'])
        original_bytes = (self.root / app.INVESTIGATION / 'state.json').read_bytes()
        source_before = copy.deepcopy(self.state['items'])
        saved = self.prepare()
        r = saved['opportunity_recommendations'][-1]
        self.assertEqual(r['recommended_choice'], 'Defer')  # Existing investigation continuation.
        self.assertIn('First monitored-page observation', r['what_changed'])
        self.assertIn('Hypothesis:', r['potential_value'])
        self.assertIn('1/4', r['existing_findings_connection'])
        self.assertEqual(self.prepare(), saved)
        b = self.body(r)
        saved = workflow.decide(self.store, b)
        first = saved['opportunity_decisions'][-1]
        self.assertEqual(first['choice'], 'Test')  # Human may disagree, without executing anything.
        self.assertEqual(first['evidence_references']['recommendation_sha256'], r['record_sha256'])
        self.assertEqual(workflow.decide(discovery.Store(self.root), b), saved)
        identical = dict(b, request_id=str(uuid.uuid4()), expected_head=first['id'])
        self.assertEqual(workflow.decide(self.store, identical), saved)
        with self.assertRaisesRegex(ValueError, 'newer decision'):
            workflow.decide(self.store, dict(b, request_id=str(uuid.uuid4())))
        with self.assertRaisesRegex(ValueError, 'different decision'):
            workflow.decide(self.store, dict(b, choice='Adopt'))
        second_state = workflow.decide(self.store, dict(identical, request_id=str(uuid.uuid4()), choice='Defer'))
        entries = workflow.view(discovery.Store(self.root), discovery.Store(self.root).read())
        self.assertEqual(len(entries[0]['decisions']), 2)
        self.assertEqual(entries[0]['decisions'][0], first)
        self.assertEqual(second_state['items'], source_before)
        self.assertEqual(second_state['runs'], self.state['runs'])
        self.assertEqual(second_state['semantic_cache'], self.state['semantic_cache'])
        self.assertEqual((self.root / app.INVESTIGATION / 'state.json').read_bytes(), original_bytes)

    def test_rejected_assessment_and_forged_quote_cannot_be_promoted(self):
        state = self.store.read()
        item = state['items'][self.item['id']]
        key = item['semantic_assessment']['cache_key']
        state['semantic_cache'][key]['assessment']['evidence'][0]['exact_quote'] = 'Invented claim of verified benefits and perfect accuracy.'
        item['semantic_assessment'] = copy.deepcopy(state['semantic_cache'][key])
        self.store.save(state)
        with self.assertRaises(ValueError): self.prepare()
        self.assertNotIn('opportunity_recommendations', self.store.read())
        state = self.store.read()
        state['semantic_cache'][key]['status'] = 'failed'
        state['items'][self.item['id']]['semantic_assessment'] = copy.deepcopy(state['semantic_cache'][key])
        self.store.save(state)
        with self.assertRaisesRegex(ValueError, 'validated assessment'): self.prepare()

    def test_stale_revision_context_snapshot_and_changed_recommendation(self):
        saved = self.prepare(); r = saved['opportunity_recommendations'][-1]; b = self.body(r)
        with self.assertRaises(ValueError): workflow.prepare(self.store, self.item['id'], '0' * 64, r['evidence_references']['assessment_cache_key'])
        with self.assertRaises(ValueError): workflow.decide(self.store, dict(b, recommendation_sha256='0' * 64))
        changed_context = copy.deepcopy(self.ctx); changed_context['human_decision']['rationale'] = 'ISOLATED context changed'
        with patch.object(semantic, 'project_context', return_value=changed_context):
            with self.assertRaisesRegex(ValueError, 'validated assessment'): workflow.decide(self.store, b)
        path = self.store.directory / self.item['snapshot_path']; raw = path.read_bytes()
        path.write_bytes(b'TAMPERED ISOLATED SNAPSHOT')
        self.assertFalse(workflow.view(self.store, self.store.read())[0]['evidence_available'])
        with self.assertRaises(ValueError): workflow.decide(self.store, b)
        path.write_bytes(raw)
        self.fixture.page += ' Meaningful changed capability.'
        self.store.run(self.fixture, now=NOW)
        with self.assertRaises(ValueError): workflow.decide(self.store, b)
        self.assertFalse(workflow.view(self.store, self.store.read())[0]['current'])
        semantic.run(self.store, 'ISOLATED_FIXTURE', self.ctx, Transport(), lambda m: None)
        latest = self.store.read()['items'][self.item['id']]
        updated = self.prepare(latest)
        self.assertEqual(updated['opportunity_recommendations'][0], r)
        self.assertEqual(updated['opportunity_recommendations'][-1]['version'], 2)
        with self.assertRaises(ValueError): workflow.decide(self.store, b)
        workflow.verify(updated['opportunity_recommendations'])

    def test_uncertainty_low_relevance_and_nonexisting_candidate_policy(self):
        item = next(i for i in self.state['items'].values() if i['source'] == discovery.FEED)
        state = self.prepare(item)
        r = state['opportunity_recommendations'][-1]
        self.assertEqual(r['recommended_choice'], 'Defer')
        self.assertEqual(r['potential_value'], 'No practical benefit is established by the supplied material.')
        self.assertIn('Initial inventory', r['what_changed'])
        for category, expected in [('potential relevance', 'Test'), ('low relevance', 'Reject')]:
            state = self.store.read(); i = state['items'][item['id']]
            prepared = semantic.prepare(self.store, i, self.ctx)
            from semantic_fixture import assessment
            value = assessment(prepared['source'], positive=category == 'potential relevance')
            if category == 'low relevance': value.update(category=category, investigation_question=None, priority='low')
            semantic.validate(value, prepared)
            record = copy.deepcopy(i['semantic_assessment']); record['assessment'] = value; record['category'] = category
            # Use a new key to preserve earlier accepted evidence, as real reassessment does.
            new_key = semantic.digest({'fixture': category})
            record['cache_key'] = new_key
            state['semantic_cache'][new_key] = copy.deepcopy(record)
            i['semantic_assessment'] = copy.deepcopy(record)
            state.setdefault('semantic_overrides', {})[prepared['cache_key']] = new_key
            self.store.save(state)
            state = self.prepare(i)
            self.assertEqual(state['opportunity_recommendations'][-1]['recommended_choice'], expected)

    def test_history_tamper_lock_and_form_validation(self):
        saved = self.prepare(); r = saved['opportunity_recommendations'][-1]
        for updates in ({'choice': ''}, {'rationale': ''}, {'rationale': 'x' * 8001}, {'explicit_action': 'automatic'}, {'request_id': 'not-uuid'}):
            with self.assertRaises(ValueError): workflow.decide(self.store, dict(self.body(r), **updates))
        with self.store.exclusive():
            with self.assertRaises(RuntimeError): workflow.decide(self.store, self.body(r))
        saved = workflow.decide(self.store, self.body(r))
        saved['opportunity_decisions'][0]['choice'] = 'Adopt'
        self.store.save(saved)
        with self.assertRaisesRegex(ValueError, 'integrity'): workflow.view(self.store, self.store.read())

    def test_http_session_origin_actions_and_restart_history(self):
        state = app.State(self.root)
        server = app.ThreadingHTTPServer(('127.0.0.1', 0), app.make_handler(state, lambda unused: {}))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f'http://127.0.0.1:{server.server_port}'
        def request(path, body=None, cookie=True, origin=True):
            headers = {'Content-Type': 'application/json'}
            if cookie: headers['Cookie'] = f'nextwise={state.cookie}'
            if origin: headers['Origin'] = base
            req = urllib.request.Request(base + path, data=json.dumps(body).encode() if body and cookie and origin else None,
                                         headers=headers, method='POST' if body else 'GET')
            try: response = urllib.request.urlopen(req)
            except urllib.error.HTTPError as error: response = error
            with response: return response.status, json.load(response)
        try:
            b = dict(candidate_id=self.item['id'], revision_sha256=self.item['content_sha256'], assessment_cache_key=self.item['semantic_assessment']['cache_key'])
            self.assertEqual(request('/api/discovery/recommend', b, cookie=False)[0], 401)
            self.assertEqual(request('/api/discovery/recommend', b, origin=False)[0], 403)
            status, payload = request('/api/discovery/recommend', b)
            self.assertEqual(status, 200)
            r = payload['opportunities'][0]['recommendation']
            self.assertEqual(request('/api/discovery/decision', self.body(r))[0], 200)
            status, reopened = request('/api/discovery')
            self.assertEqual(status, 200)
            self.assertEqual(reopened['opportunities'][0]['decisions'][0]['choice'], 'Test')
        finally:
            server.shutdown(); server.server_close()


if __name__ == '__main__': unittest.main()
