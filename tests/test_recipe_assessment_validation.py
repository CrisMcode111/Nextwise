"""Offline replay of the retained Recipe API failure; never repairs its output."""
import copy
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import project_assessment_output as output
import opportunity_assessment as opportunity
from project_workflow import Projects
import semantic_discovery as semantic

RETAINED_QUESTION = (
    "How can the Recipe API be integrated into AI Raw Gourmet's Windows 11, 16 GB RAM environment "
    'without exceeding limited development time or unjustified costs?')
MEMORY = ROOT / 'data/memory/hmem'
PROJECT = 'project-9d95b23e5f28432595742ef0ece67607'
SAVED = MEMORY / 'projects' / PROJECT / 'update-discovery'
RAW_SHA256 = 'd3e67e0466a647db298e5903031388a4e6d75cf039ac69bcbb3200dd06728b30'


class RecipeQuestionGuardTests(unittest.TestCase):
    def setUp(self):
        self.value = {'investigation_question': RETAINED_QUESTION}
        # Synthetic brief for portable numeric-rule checks, not project evidence.
        self.brief = 'Synthetic constraints: Windows 11, 16 GB RAM. Team size: 1.'

    def question_rejected(self, text, brief=None):
        return output.quantified_outcome(text, self.brief if brief is None else brief,
                                         field='investigation_question')

    def test_actual_question_false_positive(self):
        text = self.value['investigation_question']
        self.assertTrue(output.quantified_outcome(text, self.brief))
        self.assertFalse(self.question_rejected(text))

    def test_only_qualitative_cost_uncertainty_in_questions_is_exempted(self):
        for adjective in ('unknown', 'unverified', 'unjustified'):
            text = f'How can integration on Windows 11 avoid {adjective} costs?'
            with self.subTest(text=text):
                self.assertFalse(self.question_rejected(text))
                for field in output.REASONING_FIELDS:
                    if field != 'investigation_question':
                        self.assertTrue(output.quantified_outcome(text, self.brief, field=field))
                self.assertTrue(self.question_rejected(text.removesuffix('?') + '.'))

    def test_unsupported_quantities_and_outcomes_still_rejected(self):
        cases = (
            'How can integration on Windows 12 avoid unjustified costs?',
            'How can integration with 32 GB RAM avoid unknown costs?',
            'How can integration with 16 MB RAM avoid unverified costs?',
            'How can integration on Windows 11.1 avoid unknown costs?',
            'How can integration on Windows 11 avoid unjustified costs of $20?',
            'How can integration on Windows 11 reduce unknown costs by ten percent?',
            'How can we save 16 GB RAM without unjustified costs?',
            'Could estimated costs on Windows 11 be unknown costs?',
            'Can team size 1 improve throughput without unknown costs?',
            'Could costs be 16 GB RAM?',
            'Can Windows 11 deliver a twofold benefit despite unverified costs?',
        )
        for text in cases:
            with self.subTest(text=text):
                self.assertTrue(self.question_rejected(text))

    def test_constraints_must_exist_in_saved_brief(self):
        self.assertTrue(self.question_rejected(self.value['investigation_question'],
                                               'No environment constraints supplied.'))


@unittest.skipUnless((SAVED / 'state.json').is_file() and
                     (SAVED / 'runs/2b5b9830-e8cd-4823-b9fd-cc71e2c5f065/assessment-output.json').is_file(),
                     'Saved project and retained response required for full replay')
class SavedRecipeResponseReplayTests(unittest.TestCase):
    def test_full_response_passes_question_guard_but_rejects_wrong_quote_provenance(self):
        # No H-MEM bridge, transport, ledger reservation or write action is used.
        preserved = {p: hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in SAVED.rglob('*') if p.is_file()}
        retained = SAVED / 'runs/2b5b9830-e8cd-4823-b9fd-cc71e2c5f065/assessment-output.json'
        retained_bytes = retained.read_bytes()
        self.assertEqual(hashlib.sha256(retained_bytes).hexdigest(), RAW_SHA256)
        raw_records = json.loads((SAVED / 'state.json').read_text(encoding='utf-8'))['records']
        states = [json.loads(r['content'])['value'] for r in raw_records]
        state = next(s for s in states if s['version'] == 32)
        before = copy.deepcopy(state)
        with patch('socket.socket', side_effect=AssertionError('Offline only')), \
             patch.object(semantic.analyzer, 'request_claims', side_effect=AssertionError('No inference')), \
             patch.object(semantic.memory, 'call_bridge', side_effect=AssertionError('No project writes')):
            project = Projects(MEMORY)
            candidate = state['items']['recipe-api-com-1db17c9da495']
            request = project.prepare_assessment(SimpleNamespace(directory=SAVED), state, candidate, [])
            request['opportunity_contract'] = opportunity.VERSION
            response = json.loads(retained_bytes)['assessments'][0]
            self.assertEqual(response['investigation_question'], RETAINED_QUESTION)
            self.assertFalse(output.quantified_outcome(response['investigation_question'],
                request['context']['profile']['objective'], field='investigation_question'))
            quote = response['opportunity_details']['improvement_mechanism']['project_quote']
            self.assertNotIn(quote, request['context']['profile']['objective'])
            self.assertIn('Recipe API returns a complete schema', quote)
            with self.assertRaises(semantic.AssessmentError) as caught:
                output.materialize(retained_bytes.decode('utf-8'), request)
            self.assertEqual(caught.exception.diagnostic['code'], 'opportunity_details_invalid')
            self.assertEqual(caught.exception.diagnostic['field'], 'improvement_mechanism.project_quote')
        self.assertEqual(state, before)
        self.assertEqual(retained.read_bytes(), retained_bytes)
        self.assertEqual({p: hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in SAVED.rglob('*') if p.is_file()}, preserved)


if __name__ == '__main__':
    unittest.main()
