"""Opt-in stages: genuine saved inputs, SYNTHETIC outputs, isolated H-MEM only."""
import copy
import json
import tempfile
import unittest
from unittest.mock import patch

from saved_source_opportunity_fixture import build, api_get, semantic, once
import staged_opportunity as stages
import opportunity_workflow as workflow


class StagedOpportunityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='nextwise-staged-opportunity-')
        cls.addClassCleanup(cls.temp.cleanup)
        with patch('socket.socket', side_effect=AssertionError('Network forbidden')), \
             patch.object(semantic.analyzer, 'request_claims', side_effect=AssertionError('Live model forbidden')):
            cls.fixture = build(cls.temp.name, staged=True)

    def value(self):
        return copy.deepcopy(self.fixture['replay']['assessment'])

    def evaluate(self, values):
        artifact = copy.deepcopy(self.fixture['retained'])
        artifact['content'] = json.dumps({'assessments': values})
        artifact['content_sha256'] = semantic.discovery.sha(artifact['content'])
        artifact['data']['choices'][0]['message']['content'] = artifact['content']
        return once.evaluate(artifact)

    def test_one_synthetic_connection_reaches_briefing_restart_api_without_decision(self):
        fixture = self.fixture
        self.assertEqual(fixture['report']['validation_status'], 'validated')
        self.assertEqual(fixture['report']['staged_policy'], stages.POLICY)
        self.assertTrue(fixture['report']['assessment_persisted'] and fixture['report']['briefing_persisted'])
        self.assertFalse(fixture['report']['human_decision_written'])
        self.assertEqual(fixture['replay']['status'], 'validated')
        entries = api_get(self.temp.name)['opportunities']
        self.assertEqual(len(entries), 1)
        self.assertTrue(entries[0]['current'])
        r = entries[0]['recommendation']
        self.assertEqual(r['recommended_choice'], 'Defer')
        self.assertEqual(r['existing_investigation_id'], semantic.INVESTIGATION)
        self.assertIn('Hypothesis:', r['potential_value'])
        self.assertIn('unverified', r['potential_value'])
        self.assertEqual(entries[0]['decisions'], [])
        self.assertEqual(fixture['history']['history'][0]['choice'], 'Defer')
        self.assertEqual(fixture['history']['history'][0]['version'], 1)

    def test_extraction_is_exact_bounded_and_contract_remains_identical(self):
        artifact = self.fixture['retained']
        prepared = artifact['prepared_inputs'][0]
        context = self.fixture['context']
        plan = stages.extract(prepared, context)
        self.assertEqual(plan, artifact['staged_plan'])
        self.assertGreater(len(plan['claims']), 0)
        self.assertLessEqual(len(plan['claims']), semantic.EVIDENCE_CAP)
        paragraphs = {p['passage_id']: p['text'] for p in prepared['source']['passages']}
        for claim in plan['claims']:
            self.assertEqual(claim['exact_quote'], paragraphs[claim['passage_id']])
            self.assertEqual(claim['source_id'], prepared['source']['source_id'])
            self.assertEqual(claim['claim_kind'], 'publisher_claim')
        self.assertEqual(artifact['output_contract'], semantic.output_contract([prepared]))
        self.assertEqual(set(self.value()), semantic.FIELDS)
        payload = json.loads(artifact['messages'][1]['content'])
        # All eight original paragraphs stay available; no coverage is overstated.
        self.assertEqual(payload['untrusted_sources'], [prepared['source']])
        self.assertEqual(payload['extracted_publisher_claims'], plan)
        original_chars = sum(len(m['content']) for m in semantic.messages([prepared], context))
        staged_chars = sum(len(m['content']) for m in artifact['messages'])
        print(f'OFFLINE synthetic fixture: {len(prepared["source"]["passages"])} source paragraphs, '
            f'{len(plan["claims"])} selected claim candidates, {len(semantic.FIELDS)} unchanged output fields; '
            f'prompt characters {original_chars} default / {staged_chars} staged.', flush=True)

    def test_invented_quotes_or_publisher_claims_are_rejected_without_mutation(self):
        for field in ('exact_quote', 'source_observation'):
            value = self.value()
            if field == 'exact_quote': value['evidence'][0][field] = 'An invented quotation that is not in the saved source.'
            else: value[field] = 'This source proves perfect extraction accuracy for this business.'
            before = copy.deepcopy(value)
            outcome = self.evaluate([value])
            self.assertEqual(outcome['status'], 'failed')
            self.assertEqual(outcome['validation_failure']['code'], 'quote_not_exact' if field == 'exact_quote' else 'staged_claim_not_exact')
            self.assertEqual(value, before)

    def test_duplicate_assessments_remain_batch_failure_without_selection(self):
        value = self.value()
        outcome = self.evaluate([value, copy.deepcopy(value)])
        self.assertEqual(outcome['status'], 'failed')
        self.assertEqual(outcome['validation_failure']['code'], 'batch_identity')
        self.assertIsNone(outcome['assessment'])

    def test_exact_but_unselected_passage_is_not_silently_accepted_or_dropped(self):
        prepared = self.fixture['retained']['prepared_inputs'][0]
        ids = {c['passage_id'] for c in self.fixture['retained']['staged_plan']['claims']}
        other = next(p for p in prepared['source']['passages'] if p['passage_id'] not in ids)
        value = self.value()
        value['evidence'].append({'source_id': prepared['source']['source_id'],
            'passage_id': other['passage_id'], 'exact_quote': other['text']})
        before = copy.deepcopy(value)
        outcome = self.evaluate([value])
        self.assertEqual(outcome['validation_failure']['code'], 'staged_evidence_bank')
        self.assertEqual(value, before)

    def test_missing_project_pilot_evaluator_or_uncertainty_is_rejected(self):
        mutations = [('project_need', 'Generic deployment may be relevant to this project.', 'staged_project_connection'),
            ('existing_findings_connection', None, 'existing_findings'),
            ('existing_findings_connection', 'The 1/4 pilot and Defer Version 1 remain in effect.', 'staged_evaluator_connection'),
            ('limitations', [], 'evidence_gaps'), ('missing_information', [], 'evidence_gaps')]
        for field, text, code in mutations:
            with self.subTest(field=field, code=code):
                value = self.value(); value[field] = text
                outcome = self.evaluate([value])
                self.assertEqual(outcome['status'], 'failed')
                self.assertEqual(outcome['validation_failure']['code'], code)

    def test_unsupported_benefits_rejected_even_with_valid_quote_and_hypothesis_label(self):
        values = ['Hypothesis: If deployed, this will guarantee 100% extraction accuracy.',
            'Hypothesis: If compatible, it could save 30% of project cost; the benefit is unverified.',
            'Hypothesis: This improves project accuracy.']
        for text in values:
            value = self.value(); value['application_hypothesis'] = text
            self.assertEqual(semantic.validate(value, self.fixture['retained']['prepared_inputs'][0]), value)
            outcome = self.evaluate([value])
            self.assertEqual(outcome['validation_failure']['code'], 'staged_unsupported_benefit')
        value = self.value(); value['project_need'] += ' It will reduce business costs.'
        self.assertEqual(self.evaluate([value])['validation_failure']['code'], 'staged_unsupported_benefit')

    def test_staged_plan_tamper_cannot_reach_recommendation(self):
        state = copy.deepcopy(self.fixture['reopened'])
        item = state['items'][once.CANDIDATE]
        key = item['semantic_assessment']['cache_key']
        item['semantic_assessment']['staged_plan']['claims'][0]['exact_quote'] = 'Invented claim.'
        state['semantic_cache'][key] = copy.deepcopy(item['semantic_assessment'])
        with self.assertRaises(semantic.AssessmentError):
            workflow.current(semantic.discovery.Store(self.temp.name), state, once.CANDIDATE, self.fixture['context'])

    def test_low_and_uncertain_remain_allowed_without_positive_benefits(self):
        for category in ('low relevance', 'uncertain relevance'):
            value = self.value(); value.update(category=category, project_need_id='uncertain',
                priority='defer', application_hypothesis=None)
            self.assertEqual(self.evaluate([value])['status'], 'validated')

    def test_default_preparation_and_consumed_allowance_are_unchanged(self):
        store = semantic.discovery.Store(self.temp.name)
        state = self.fixture['reopened']; context = self.fixture['context']
        default = once.preparation(store, state, context)
        self.assertNotIn('staged_plan', default)
        self.assertEqual(default['messages'], semantic.messages(default['prepared_inputs'], context))
        self.assertTrue(once.used(state, once.directory(store)))
        self.assertEqual(once.run_once(store, '', context,
            lambda *args: self.fail('Consumed allowance called transport'), staged=True)['new_requests_sent'], 0)


if __name__ == '__main__': unittest.main()
