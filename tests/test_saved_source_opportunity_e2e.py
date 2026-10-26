"""Saved real evidence/context, synthetic model response, isolated official H-MEM.

The API is dispatched in memory. No HTTP/network or production memory operations.
"""
import tempfile
import unittest
from unittest.mock import patch

from saved_source_opportunity_fixture import build, api_get, semantic


class SavedSourceOpportunityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='nextwise-saved-source-e2e-')
        cls.addClassCleanup(cls.temp.cleanup)
        with patch('socket.socket', side_effect=AssertionError('Network forbidden')), \
             patch.object(semantic.analyzer, 'request_claims', side_effect=AssertionError('Model forbidden')), \
             patch.object(semantic.discovery, 'fetch', side_effect=AssertionError('Source fetch forbidden')):
            cls.result = build(cls.temp.name)

    def test_actual_runner_validation_retention_restart_and_api_payload(self):
        result = self.result
        self.assertEqual(result['report']['validation_status'], 'validated')
        self.assertTrue(result['report']['assessment_persisted'])
        self.assertTrue(result['report']['briefing_persisted'])
        self.assertFalse(result['report']['human_decision_written'])
        self.assertEqual(result['replay']['status'], 'validated')
        entries = result['discovery']['opportunities']
        self.assertEqual(len(entries), 1)
        self.assertTrue(entries[0]['current'])
        self.assertTrue(entries[0]['evidence_available'])
        self.assertEqual(entries[0]['decisions'], [])
        self.assertTrue(result['retained']['data']['fixture_only'])
        self.assertEqual(api_get(self.temp.name)['opportunities'], entries)

    def test_business_briefing_preserves_real_identity_and_defer_boundary(self):
        result = self.result
        r = result['discovery']['opportunities'][0]['recommendation']
        self.assertEqual(r['recommended_choice'], 'Defer')
        self.assertEqual(r['existing_investigation_id'], semantic.INVESTIGATION)
        self.assertTrue(r['potential_value'].startswith('Hypothesis:'))
        self.assertIn('First monitored-page observation', r['what_changed'])
        self.assertIn('not a duplicate', r['existing_findings_connection'])
        self.assertTrue(r['risks'] and r['uncertainty'] and r['next_action'])
        refs = r['evidence_references']
        item = result['reopened']['items'][r['candidate_id']]
        self.assertEqual(refs['publication_date'], item['publication_date'])
        self.assertEqual(refs['retrieved_at'], item['retrieved_at'])
        self.assertEqual(refs['raw_sha256'], item['raw_sha256'])
        prepared = semantic.prepare(semantic.discovery.Store(self.temp.name), item, result['context'])
        supplied = {p['passage_id']: p['text'] for p in prepared['source']['passages']}
        for quote in r['supporting_evidence']:
            self.assertEqual(quote['source_id'], prepared['source']['source_id'])
            self.assertEqual(quote['exact_quote'], supplied[quote['passage_id']])
        self.assertEqual(result['history']['history'][0]['choice'], 'Defer')
        self.assertEqual(result['history']['history'][0]['version'], 1)

    def test_existing_failures_allowances_and_observation_histories_preserved(self):
        before, after = self.result['before'], self.result['reopened']
        self.assertEqual(len(after['semantic_requests']), len(before['semantic_requests']) + 1)
        self.assertEqual(after['semantic_authorizations'].get('opportunity-e2e-nemotron-20261026-v1'),
                         before['semantic_authorizations'].get('opportunity-e2e-nemotron-20261026-v1'))
        for cid, item in before['items'].items():
            self.assertEqual(semantic.digest(after['items'][cid]['revisions']), semantic.digest(item['revisions']))
        self.assertFalse(after.get('opportunity_decisions'))
        self.assertEqual(len(before.get('opportunity_recommendations', [])), 0)

    def test_invalid_generated_quote_cannot_become_a_briefing(self):
        with tempfile.TemporaryDirectory(prefix='nextwise-rejected-source-e2e-') as tmp, \
             patch('socket.socket', side_effect=AssertionError('Network forbidden')), \
             patch.object(semantic.analyzer, 'request_claims', side_effect=AssertionError('Model forbidden')):
            result = build(tmp, invalid=True)
        self.assertEqual(result['report']['validation_status'], 'failed')
        self.assertEqual(result['report']['validation_failure']['code'], 'quote_not_exact')
        self.assertFalse(result['report']['assessment_persisted'])
        self.assertFalse(result['report']['briefing_persisted'])
        self.assertEqual(result['discovery']['opportunities'], [])
        self.assertEqual(semantic.digest(result['before']['semantic_cache']), semantic.digest(result['reopened']['semantic_cache']))


if __name__ == '__main__': unittest.main()
