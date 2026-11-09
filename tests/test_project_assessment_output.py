"""Focused offline replay against retained failure and unchanged saved sources.

Hand-authored contract fixtures below are test inputs, never AI recommendations.
Local replay skips when the operator's retained files are not present.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import project_assessment_output as output
import project_adapters as adapters
from project_workflow import Projects
import semantic_discovery as semantic

DIRECTORY = ROOT / 'data/memory/hmem/projects/project-9d95b23e5f28432595742ef0ece67607/update-discovery'
RETAINED = Path(os.environ.get('TEMP', '')) / 'nextwise-actual-rejected-assessment.json'


def hashes():
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in DIRECTORY.rglob('*') if p.is_file()}


@unittest.skipUnless(RETAINED.is_file() and (DIRECTORY / 'state.json').is_file(),
                     'Local retained failure and saved evidence required')
class RetainedOutputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.before = hashes()
        cls.retained_bytes = RETAINED.read_bytes()
        cls.failed = json.loads(cls.retained_bytes)['assessment']
        records = json.loads((DIRECTORY / 'state.json').read_text(encoding='utf-8'))['records']
        state = json.loads(records[-1]['content'])['value']
        cls.requests = {}
        for candidate_id, item in state['items'].items():
            cls.requests[candidate_id] = Projects(ROOT / 'data/memory/hmem').prepare_assessment(
                SimpleNamespace(directory=DIRECTORY), state, item,
                [i for i in state['items'] if i != candidate_id])
        cls.request = cls.requests[cls.failed['candidate_id']]

    @classmethod
    def tearDownClass(cls):
        if cls.before != hashes() or cls.retained_bytes != RETAINED.read_bytes():
            raise AssertionError('Saved project/evidence/history/retained response changed')

    def setUp(self):
        p = patch('socket.socket', side_effect=AssertionError('Offline verification only'))
        p.start(); self.addCleanup(p.stop)

    def fixture(self, request=None):
        """Explicit hand-authored low-relevance contract fixture, not AI output."""
        request = request or self.request
        ids = list(output.claims(request))
        return {'candidate_id': request['prepared']['source']['candidate_id'],
            'category': 'low relevance', 'project_need_id': 'objective',
            'project_need': 'AI Raw Gourmet needs recipe generation; project applicability is unverified.',
            'observation_claim_id': ids[0], 'evidence_claim_ids': ids,
            'application_hypothesis': None,
            'limitations': ['Publisher statements do not establish project-specific performance.'],
            'missing_information': list(output.UNKNOWNS), 'priority': 'low',
            'priority_reason': 'Project suitability has not been established.',
            'investigation_question': None,
            'next_step': 'Review project-specific applicability before considering adoption.',
            'existing_findings_connection': None}

    def render(self, value, request=None):
        return output.materialize(json.dumps({'assessments': [value]}), request or self.request)

    def test_retained_response_still_fails_unchanged_strict_validator(self):
        with self.assertRaises(semantic.AssessmentError) as caught:
            semantic.evaluate_business_response(json.dumps({'assessments': [self.failed]}), self.request)
        self.assertEqual(caught.exception.diagnostic['code'], 'quote_not_exact')
        self.assertEqual(caught.exception.diagnostic['field'], 'evidence[1].exact_quote')
        saved = output.claims(self.request)[self.failed['evidence'][1]['passage_id']]['exact_quote']
        self.assertIn('\u2019', saved)
        self.assertEqual(saved.replace('\u2019', "'"), self.failed['evidence'][1]['exact_quote'])

    def test_all_saved_sources_materialize_every_selected_quote_exactly(self):
        for request in self.requests.values():
            with self.subTest(candidate=request['prepared']['source']['candidate_id']):
                fixture = self.fixture(request)
                result = json.loads(self.render(fixture, request))['assessments'][0]
                bank = output.claims(request)
                self.assertEqual(result['source_observation'], bank[fixture['observation_claim_id']]['exact_quote'])
                for actual, selected in zip(result['evidence'], fixture['evidence_claim_ids']):
                    self.assertEqual(actual, {k: bank[selected][k] for k in ('source_id', 'passage_id', 'exact_quote')})
                semantic.evaluate_business_response(json.dumps({'assessments': [result]}), request)

    def test_retained_numerical_benefit_is_rejected_even_with_exact_claim_selection(self):
        value = copy.deepcopy(self.failed)
        value['observation_claim_id'] = self.failed['evidence'][0]['passage_id']
        value.pop('source_observation')
        value['evidence_claim_ids'] = [e['passage_id'] for e in value.pop('evidence')]
        with self.assertRaises(semantic.AssessmentError) as caught:
            self.render(value)
        self.assertEqual(caught.exception.diagnostic['code'], 'generation_quantified_outcome')
        self.assertEqual(caught.exception.diagnostic['field'], 'application_hypothesis')

    def test_quantities_are_rejected_in_every_generated_prose_field(self):
        for field in output.REASONING_FIELDS + ('limitations', 'missing_information'):
            for claim in ('Reduce errors below 35%.', 'Halve recipe errors.', 'Save thirty percent.'):
                with self.subTest(field=field, claim=claim):
                    value = self.fixture()
                    if field in ('limitations', 'missing_information'):
                        value[field].append(claim)
                    else:
                        value[field] = claim
                    with self.assertRaises(semantic.AssessmentError) as caught:
                        self.render(value)
                    self.assertEqual(caught.exception.diagnostic['code'], 'generation_quantified_outcome')

    def test_unknowns_are_required_never_silently_inserted(self):
        for unknown in output.UNKNOWNS:
            value = self.fixture(); value['missing_information'].remove(unknown)
            original = copy.deepcopy(value)
            with self.assertRaises(semantic.AssessmentError) as caught:
                self.render(value)
            self.assertEqual(caught.exception.diagnostic['code'], 'generation_unknowns_required')
            self.assertEqual(value, original)

    def test_conditional_unquantified_hypothesis_passes_but_missing_label_does_not(self):
        value = self.fixture()
        value['category'] = 'potential relevance'
        value['application_hypothesis'] = (
            'Hypothesis: If applicable to recipe schemas, this could help structure recipe output; '
            'the project benefit is unverified.')
        value['investigation_question'] = 'Does the described method apply to the project recipe schema?'
        result = json.loads(self.render(value))['assessments'][0]
        self.assertEqual(result['application_hypothesis'], value['application_hypothesis'])
        value['application_hypothesis'] = value['application_hypothesis'].removeprefix('Hypothesis: ')
        with self.assertRaises(semantic.AssessmentError) as caught:
            self.render(value)
        self.assertEqual(caught.exception.diagnostic['code'], 'hypothesis_label')

    def test_invalid_claim_ids_duplicates_and_model_quotation_text_rejected(self):
        value = self.fixture()
        cases = [dict(value, observation_claim_id='not-in-bank'),
                 dict(value, evidence_claim_ids=[]),
                 dict(value, evidence_claim_ids=[value['observation_claim_id']] * 2),
                 dict(value, source_observation='Paraphrased quotation'),
                 dict(value, evidence_claim_ids=[{'passage_id': 'p8'}])]
        for invalid in cases:
            with self.subTest(value=invalid), self.assertRaises(ValueError):
                self.render(invalid)

    def test_prompt_and_wire_schema_agree_and_preserve_saved_input(self):
        original = copy.deepcopy(self.request)
        messages = output.messages(self.request)
        schema = output.contract(self.request)
        fields = schema['properties']['assessments']['items']['properties']
        self.assertNotIn('source_observation', fields)
        self.assertNotIn('evidence', fields)
        self.assertIn('observation_claim_id', fields)
        self.assertIn(json.dumps(schema, ensure_ascii=False), messages[0]['content'])
        self.assertEqual(messages[1:], self.request['messages'][1:])
        self.assertEqual(self.request, original)

    def test_strict_validator_still_rejects_mutated_materialized_quotation(self):
        canonical = json.loads(self.render(self.fixture()))
        canonical['assessments'][0]['evidence'][0]['exact_quote'] += ' invented'
        with self.assertRaises(semantic.AssessmentError) as caught:
            semantic.evaluate_business_response(json.dumps(canonical), self.request)
        self.assertEqual(caught.exception.diagnostic['code'], 'quote_not_exact')

    def test_adapter_uses_selection_contract_and_returns_validated_canonical_shape(self):
        fixture = self.fixture()
        response = {'ok': True, 'http_status': 200, 'data': {'choices': [
            {'finish_reason': 'stop', 'message': {'role': 'assistant',
             'content': json.dumps({'assessments': [fixture]})}}]}}
        with patch.object(adapters.config, 'secret', return_value='offline-test-token'), \
             patch('sys.stderr'), \
             patch.object(adapters.config, 'settings', return_value=SimpleNamespace(
                 meterless_url='http://127.0.0.1:8088', completions_url='http://127.0.0.1:8088/v1/chat/completions', model='pinned-test-model')), \
             patch.object(adapters.analyzer, 'request_claims', return_value=response) as transport:
            result = adapters.assess(self.request)
        transport.assert_called_once()
        self.assertEqual(transport.call_args.kwargs['response_schema'], output.contract(self.request))
        semantic.evaluate_business_response(result, self.request)


if __name__ == '__main__':
    unittest.main()
