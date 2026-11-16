"""Offline provenance regressions; test inputs never repair retained assessments."""
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
import opportunity_assessment as opportunity
import project_assessment_output as output
from project_workflow import Projects
import semantic_discovery as semantic

MEMORY = ROOT / 'data/memory/hmem'
PROJECT = 'project-9d95b23e5f28432595742ef0ece67607'
SAVED = MEMORY / 'projects' / PROJECT / 'update-discovery'
RETAINED = SAVED / 'runs/2b5b9830-e8cd-4823-b9fd-cc71e2c5f065/assessment-output.json'


class AttributionContractTests(unittest.TestCase):
    def test_wire_schema_distinguishes_project_quote_from_external_claim_ids(self):
        schema = opportunity.schema({'staged_plan': {'claims': [{'passage_id': 'p1'}]}})
        mechanism = schema['properties']['improvement_mechanism']['properties']
        description = mechanism['project_quote']['description']
        self.assertIn('ONLY from approved_project_context.profile.objective', description)
        self.assertIn('provenance.brief_sha256', description)
        self.assertIn('Never use publisher text', description)
        external = mechanism['evidence_claim_ids']
        self.assertIn('External publisher evidence ONLY', external['description'])
        self.assertEqual(external['items']['enum'], ['p1'])
        self.assertIn('ONLY from approved_project_context.profile.objective',
                      schema['properties']['feasibility']['properties']['resource_quotes']['description'])

    def test_instructions_identify_existing_origins_and_forbid_relabeling(self):
        instructions = opportunity.instructions()
        for origin in ('approved_project_context.profile.objective',
                       'approved_project_context.provenance.brief_sha256',
                       'untrusted_sources', 'extracted_publisher_claims', 'supporting_source_context'):
            self.assertIn(origin, instructions)
        self.assertIn('Copy project_quote verbatim ONLY from this brief', instructions)
        self.assertIn('Do not paraphrase, manufacture, silently replace or relabel quotations', instructions)


@unittest.skipUnless((SAVED / 'state.json').is_file() and RETAINED.is_file(),
                     'Saved project and failed response required')
class SavedProjectAttributionTests(unittest.TestCase):
    def setUp(self):
        self.preserved = {p: hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in SAVED.rglob('*') if p.is_file()}
        self.addCleanup(self.verify_preservation)
        for target in ('socket.socket', 'semantic_discovery.analyzer.request_claims',
                       'semantic_discovery.memory.call_bridge'):
            guard = patch(target, side_effect=AssertionError('No network, inference or project writes'))
            guard.start()
            self.addCleanup(guard.stop)
        records = json.loads((SAVED / 'state.json').read_text(encoding='utf-8'))['records']
        states = [json.loads(r['content'])['value'] for r in records]
        state = next(s for s in states if s['version'] == 32)
        candidate = state['items']['recipe-api-com-1db17c9da495']
        self.request = Projects(MEMORY).prepare_assessment(SimpleNamespace(directory=SAVED), state, candidate, [])
        self.request['opportunity_contract'] = opportunity.VERSION
        self.brief = self.request['context']['profile']['objective']
        self.raw = RETAINED.read_text(encoding='utf-8')
        self.failed = json.loads(self.raw)['assessments'][0]

    def verify_preservation(self):
        self.assertEqual({p: hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in SAVED.rglob('*') if p.is_file()}, self.preserved)

    def separate_test_inputs(self):
        # A new, explicitly synthetic validation case using real input origins.
        # Never edit, materialize or persist a corrected version of the failure.
        claim = self.request['staged_plan']['claims'][0]
        assessment = {'category': 'potential relevance', 'evidence': [
            {k: claim[k] for k in ('source_id', 'passage_id', 'exact_quote')}]}
        details = {'impact_domain': 'productivity', 'evidence_quality': 'publisher_claims_only',
            'improvement_mechanism': {'explanation': 'The described capability could merit a bounded evidence review.',
                'project_quote': self.brief[:160], 'evidence_claim_ids': [claim['passage_id']]},
            'feasibility': {'status': 'unknown', 'rationale': 'Project-specific compatibility remains unknown.',
                'resource_fit': 'unknown', 'resource_rationale': 'Integration effort has not been established.',
                'resource_quotes': [], 'conditions': ['Review the saved evidence before considering adoption.'],
                'blocking_unknowns': ['Project-specific feasibility is not established.']}}
        return details, assessment

    def test_prompt_keeps_exact_project_context_and_external_provenance_separate(self):
        original = copy.deepcopy(self.request)
        messages = output.messages(self.request)
        payload = json.loads(messages[1]['content'])
        project = payload['approved_project_context']
        self.assertEqual(project['profile']['objective'], self.brief)
        self.assertEqual(project['provenance']['brief_sha256'], semantic.digest(self.brief))
        self.assertEqual(payload['extracted_publisher_claims'], self.request['staged_plan'])
        external = payload['untrusted_sources'][0]
        self.assertEqual(external['url'], 'https://recipe-api.com/recipe-api-for-meal-planning')
        self.assertTrue(all(c['source_id'] == external['source_id']
                            for c in payload['extracted_publisher_claims']['claims']))
        self.assertIn(opportunity.instructions(), messages[0]['content'])
        self.assertIn('For external publisher quotations, return claim IDs only', messages[0]['content'])
        self.assertEqual(messages[1:], original['messages'][1:])
        self.assertEqual(self.request, original)

    def test_retained_failure_remains_rejected_at_project_quote(self):
        original = copy.deepcopy(self.failed)
        wrong_quote = self.failed['opportunity_details']['improvement_mechanism']['project_quote']
        self.assertNotIn(wrong_quote, self.brief)
        # Prompt correction must not repair or silently substitute the old output.
        with self.assertRaises(semantic.AssessmentError) as caught:
            output.materialize(self.raw, self.request)
        self.assertEqual(caught.exception.diagnostic['code'], 'opportunity_details_invalid')
        self.assertEqual(caught.exception.diagnostic['field'], 'improvement_mechanism.project_quote')
        self.assertEqual(self.failed, original)

    def test_exact_project_quote_and_separately_attributed_external_claim_pass(self):
        details, assessment = self.separate_test_inputs()
        self.assertEqual(opportunity.validate(details, self.request, assessment), details)
        self.assertIn(details['improvement_mechanism']['project_quote'], self.brief)
        external = assessment['evidence'][0]
        self.assertIn(external, [{k: c[k] for k in ('source_id', 'passage_id', 'exact_quote')}
                                for c in self.request['staged_plan']['claims']])

    def test_external_or_fabricated_project_quotes_still_rejected(self):
        for quote in (self.failed['opportunity_details']['improvement_mechanism']['project_quote'],
                      self.brief[:160] + ' invented project statement'):
            with self.subTest(origin='external or fabricated'):
                details, assessment = self.separate_test_inputs()
                details['improvement_mechanism']['project_quote'] = quote
                with self.assertRaises(semantic.AssessmentError) as caught:
                    opportunity.validate(details, self.request, assessment)
                self.assertEqual(caught.exception.diagnostic['field'], 'improvement_mechanism.project_quote')

    def test_external_resource_quotes_and_project_ids_in_external_evidence_still_rejected(self):
        details, assessment = self.separate_test_inputs()
        details['feasibility']['resource_quotes'] = [
            self.failed['opportunity_details']['improvement_mechanism']['project_quote']]
        with self.assertRaises(semantic.AssessmentError) as caught:
            opportunity.validate(details, self.request, assessment)
        self.assertEqual(caught.exception.diagnostic['field'], 'feasibility.resource_quotes')
        details, assessment = self.separate_test_inputs()
        details['improvement_mechanism']['evidence_claim_ids'] = ['project-brief']
        with self.assertRaises(semantic.AssessmentError) as caught:
            opportunity.validate(details, self.request, assessment)
        self.assertEqual(caught.exception.diagnostic['field'], 'improvement_mechanism.evidence_claim_ids')


if __name__ == '__main__':
    unittest.main()
