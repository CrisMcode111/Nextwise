"""Focused offline numeric-guard replay; never promotes rejected assessments."""
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
from project_workflow import Projects
import semantic_discovery as semantic

DIRECTORY = ROOT / 'data/memory/hmem/projects/project-9d95b23e5f28432595742ef0ece67607/update-discovery'
RETAINED = Path(os.environ.get('TEMP', '')) / 'nextwise-new-actual-rejected-assessment.json'


@unittest.skipUnless(RETAINED.is_file() and (DIRECTORY / 'state.json').is_file(),
                     'Retained second assessment and saved brief required')
class NumericGuardRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        network = patch('socket.socket', side_effect=AssertionError('Offline checks only'))
        network.start(); cls.addClassCleanup(network.stop)
        paths = [p for p in DIRECTORY.rglob('*') if p.is_file()]
        paths += [RETAINED, RETAINED.with_name('nextwise-actual-rejected-assessment.json'),
                  Path(os.environ['LOCALAPPDATA']) / 'ai.meterless.runtime/receipts.jsonl']
        cls.preserved = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        cls.retained = json.loads(RETAINED.read_text(encoding='utf-8'))
        cls.value = cls.retained['assessment']
        records = json.loads((DIRECTORY / 'state.json').read_text(encoding='utf-8'))['records']
        state = json.loads(records[-1]['content'])['value']
        cls.brief = state['project']['brief']
        candidate = cls.value['candidate_id']
        cls.request = Projects(ROOT / 'data/memory/hmem').prepare_assessment(
            SimpleNamespace(directory=DIRECTORY), state, state['items'][candidate],
            sorted(i for i in state['items'] if i != candidate))

    @classmethod
    def tearDownClass(cls):
        if any(hashlib.sha256(p.read_bytes()).hexdigest() != h for p, h in cls.preserved.items()):
            raise AssertionError('Historical response, evidence, project history or receipts changed')

    def test_retained_priority_reason_passes_numeric_guard_only(self):
        self.assertFalse(output.quantified_outcome(self.value['priority_reason'], self.brief))
        original = copy.deepcopy(self.value)
        with self.assertRaises(semantic.AssessmentError) as caught:
            output.materialize(json.dumps({'assessments': [self.value]}), self.request)
        # The separate category/hypothesis defect is NOT repaired or accepted.
        self.assertEqual(caught.exception.diagnostic['code'], 'unsupported_hypothesis')
        self.assertEqual(self.value, original)
        self.assertFalse(self.retained['accepted'])

    def test_exact_saved_constraints_allow_presentation_colon_variation(self):
        for text in ('Team size: 1.', 'team size 1, Windows 11, 16 GB RAM.',
                     'Environment: Windows 11; available memory: 16 GB RAM.'):
            with self.subTest(text=text):
                self.assertFalse(output.quantified_outcome(text, self.brief))

    def test_bare_numbers_changed_values_and_units_still_rejected(self):
        for text in ('Team size 2.', 'Windows 110.', 'Windows 11.1.', '32 GB RAM.',
                     '16 MB RAM.', 'There are 16.', 'Team size 1.5.',
                     'Windows 11, 16 GB RAM, 35% fewer errors.'):
            with self.subTest(text=text):
                self.assertTrue(output.quantified_outcome(text, self.brief))

    def test_numerical_benefits_performance_and_estimates_still_rejected(self):
        for text in ('Save 16 GB RAM.', 'Estimated requirement: 16 GB RAM.',
                     'Team size 1 improves throughput.', 'Reduce errors by 16%.',
                     'Accuracy is 11%.', 'Complete recipes in 1 second.',
                     'Save thirty percent.', 'Halve recipe errors.'):
            with self.subTest(text=text):
                self.assertTrue(output.quantified_outcome(text, self.brief))
                value = copy.deepcopy(self.value); value['priority_reason'] = text
                with self.assertRaises(semantic.AssessmentError) as caught:
                    output.materialize(json.dumps({'assessments': [value]}), self.request)
                self.assertEqual(caught.exception.diagnostic['code'], 'generation_quantified_outcome')

    def test_exemptions_come_from_saved_brief_not_global_number_allowlist(self):
        for fact in ('Team size: 1', 'Windows 11', '16 GB RAM'):
            with self.subTest(fact=fact):
                self.assertTrue(output.quantified_outcome(fact, 'No environment or team facts supplied.'))

    def test_exact_quotation_and_unknown_requirements_remain_enforced(self):
        bank = output.claims(self.request)
        canonical = copy.deepcopy(self.value)
        canonical['source_observation'] = bank[canonical.pop('observation_claim_id')]['exact_quote']
        canonical['evidence'] = [{k: bank[i][k] for k in ('source_id', 'passage_id', 'exact_quote')}
                                 for i in canonical.pop('evidence_claim_ids')]
        canonical['evidence'][0]['exact_quote'] += ' invented'
        with self.assertRaises(semantic.AssessmentError) as caught:
            semantic.evaluate_business_response(json.dumps({'assessments': [canonical]}), self.request)
        self.assertEqual(caught.exception.diagnostic['code'], 'quote_not_exact')
        value = copy.deepcopy(self.value); value['missing_information'].remove(output.UNKNOWNS[0])
        with self.assertRaises(semantic.AssessmentError) as caught:
            output.materialize(json.dumps({'assessments': [value]}), self.request)
        self.assertEqual(caught.exception.diagnostic['code'], 'generation_unknowns_required')


if __name__ == '__main__':
    unittest.main()
