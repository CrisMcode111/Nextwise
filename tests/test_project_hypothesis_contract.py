"""Offline generation-to-validation checks with explicitly synthetic inputs."""
import copy
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import project_assessment_output as output
import semantic_discovery as semantic


class HypothesisContractTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(patch.stopall)
        patch('socket.socket', side_effect=AssertionError('Offline only')).start()
        patch.object(semantic.analyzer, 'request_claims', side_effect=AssertionError('No provider')).start()
        patch.object(semantic.memory, 'call_bridge', side_effect=AssertionError('No memory writes')).start()
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        directory = Path(temp.name)
        (directory / 'runs').mkdir()
        text = 'Synthetic publisher claim: this library produces schema-constrained structured text for applications.'
        raw = ('<p>' + text + '</p>').encode()
        (directory / 'runs/source.html').write_bytes(raw)
        item = {'id': 'synthetic-source', 'title': 'Synthetic library', 'url': 'https://example.com/library',
                'publication_date': None, 'retrieved_at': '2026-11-09T00:00:00Z',
                'snapshot_path': 'runs/source.html', 'raw_sha256': semantic.discovery.sha(raw),
                'content_sha256': semantic.discovery.sha(text), 'source': 'synthetic-fixture'}
        self.request = semantic.prepare_business_assessment(SimpleNamespace(directory=directory), item,
            'Example Project develops recipe software. Team size: 1. Windows 11, 16 GB RAM.',
            name='Example Project', sanitized=True)
        self.hypothesis = ('Hypothesis: If applicable to recipe schemas, this could help structure recipe output; '
                           'the project benefit is unverified.')

    def value(self, category, hypothesis):
        ids = list(output.claims(self.request))
        return {'candidate_id': 'synthetic-source', 'category': category,
            'project_need_id': 'uncertain' if category == 'uncertain relevance' else 'objective',
            'project_need': 'Example Project needs structured recipe output; suitability remains unverified.',
            'observation_claim_id': ids[0], 'evidence_claim_ids': ids,
            'application_hypothesis': hypothesis,
            'limitations': ['Publisher assertions do not establish project suitability.'],
            'missing_information': list(output.UNKNOWNS), 'priority': 'defer',
            'priority_reason': 'Project-specific suitability is not established.',
            'investigation_question': None if category == 'low relevance' else
                'Does the described capability apply to the project recipe schema?',
            'next_step': 'Review the stated capability against the project needs before considering adoption.',
            'existing_findings_connection': None}

    def render(self, value):
        before = copy.deepcopy(value)
        try:
            canonical = output.materialize(json.dumps({'assessments': [value]}), self.request)
            # Same second validation used by Projects._assess before persistence.
            semantic.evaluate_business_response(canonical, self.request)
            return json.loads(canonical)['assessments'][0]
        finally:
            self.assertEqual(value, before, 'Rejected or accepted output must never be silently repaired')

    def reject(self, value, code):
        with self.assertRaises(semantic.AssessmentError) as caught:
            self.render(value)
        self.assertEqual(caught.exception.diagnostic['code'], code)

    def test_all_categories_with_null_or_conditional_hypothesis(self):
        for category in semantic.CATEGORIES:
            for hypothesis in (None, self.hypothesis):
                with self.subTest(category=category, hypothesis=hypothesis):
                    value = self.value(category, hypothesis)
                    if category == 'potential relevance' and hypothesis is None:
                        self.reject(value, 'positive_grounding')
                    elif category != 'potential relevance' and hypothesis is not None:
                        self.reject(value, 'unsupported_hypothesis')
                    else:
                        actual = self.render(value)
                        self.assertEqual(actual['category'], category)
                        self.assertEqual(actual['application_hypothesis'], hypothesis)
                        claim = self.request['staged_plan']['claims'][0]
                        self.assertEqual(actual['source_observation'], claim['exact_quote'])
                        self.assertEqual(actual['evidence'][0], {k: claim[k] for k in
                            ('source_id', 'passage_id', 'exact_quote')})

    def test_invalid_hypothesis_values_for_every_category(self):
        for category in semantic.CATEGORIES:
            for invalid in ('null', '', False, [], {}):
                with self.subTest(category=category, invalid=invalid):
                    self.reject(self.value(category, invalid), 'hypothesis_type')

    def test_potential_hypothesis_label_condition_and_uncertainty_required(self):
        cases = [(self.hypothesis.removeprefix('Hypothesis: '), 'hypothesis_label'),
            ('Hypothesis: This could help structure recipe output; the benefit is unverified.', 'staged_unsupported_benefit'),
            ('Hypothesis: If applicable, this could help structure recipe output.', 'staged_unsupported_benefit'),
            ('Hypothesis: If applicable, this will improve recipe output; the benefit is unverified.', 'staged_unsupported_benefit')]
        for hypothesis, code in cases:
            with self.subTest(hypothesis=hypothesis):
                self.reject(self.value('potential relevance', hypothesis), code)

    def test_saved_constraint_exemption_does_not_extend_to_hypothesis(self):
        hypothesis = ('Hypothesis: If applicable, this could structure recipe output; '
                      'applicability is unverified. Environment: Windows 11.')
        self.assertFalse(output.quantified_outcome(hypothesis, self.request['context']['profile']['objective']))
        self.reject(self.value('potential relevance', hypothesis), 'staged_unsupported_benefit')

    def test_related_category_need_question_and_priority_requirements(self):
        for category in ('potential relevance', 'uncertain relevance'):
            value = self.value(category, self.hypothesis if category == 'potential relevance' else None)
            value['investigation_question'] = None
            self.reject(value, 'question_required')
        value = self.value('potential relevance', self.hypothesis)
        value['project_need_id'] = 'uncertain'
        self.reject(value, 'positive_grounding')
        value = self.value('uncertain relevance', None)
        value['project_need_id'] = 'objective'
        self.reject(value, 'uncertain_need')
        for category in ('low relevance', 'uncertain relevance'):
            value = self.value(category, None)
            value['priority'] = 'high'
            self.reject(value, 'uncertain_priority')

    def test_wire_schema_and_all_prompt_layers_express_category_rule(self):
        before = copy.deepcopy(self.request)
        schema = output.contract(self.request)
        fields = schema['properties']['assessments']['items']['properties']
        description = fields['application_hypothesis']['description']
        self.assertIn('MUST be JSON null for low relevance and uncertain relevance', description)
        self.assertIn('For potential relevance it MUST be a non-null string', description)
        self.assertIn('No quantities, including saved team-size', description)
        self.assertEqual(fields['application_hypothesis']['type'], ['string', 'null'])
        self.assertIn('Name the specific approved task/constraint', fields['project_need']['description'])
        messages = output.messages(self.request)
        system = messages[0]['content']
        self.assertIn(json.dumps(schema, ensure_ascii=False), system)
        self.assertIn('Only for potential relevance, describe one concrete possible benefit', system)
        self.assertIn('application_hypothesis must be null unless category is potential relevance', system)
        self.assertIn('application_hypothesis MUST be JSON null for low relevance and uncertain relevance', system)
        self.assertEqual(messages[1:], self.request['messages'][1:])
        self.assertEqual(self.request, before)


if __name__ == '__main__':
    unittest.main()
