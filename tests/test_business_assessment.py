"""Offline integration: genuine publisher excerpts, explicitly MOCKED judgements.

No test here demonstrates model reasoning or measured business benefit. Food
input comes from the saved user project description, not a runtime default.
The unrelated service description is an explicitly synthetic test brief.
"""
import copy
import html
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import semantic_discovery as semantic


class BusinessAssessmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = SimpleNamespace(directory=Path(self.temp.name))
        (self.store.directory / 'runs').mkdir()
        self.addCleanup(patch.stopall)
        patch('socket.socket', side_effect=AssertionError('No network')).start()
        patch.object(semantic.analyzer, 'request_claims', side_effect=AssertionError('No live model')).start()
        patch.object(semantic.memory, 'call_bridge', side_effect=AssertionError('No memory access')).start()
        patch.object(semantic, 'project_context', side_effect=AssertionError('No default project')).start()
        profile = json.loads((ROOT / 'data/project_profile.json').read_text())
        self.food = profile['objective'] + '. ' + '; '.join(profile['constraints']) + '. ' + profile['stage']
        self.service = ('I run a local bicycle repair shop. I want to answer repeated customer questions '
                        'about opening hours and repair policies on our website. I have no coding skills '
                        'and need a service I can set up myself. Do not build software for me.')
        report = json.loads((ROOT / 'reports/tool_discovery/project_source_check.json').read_text(encoding='utf-8'))
        self.instructor = next(c for c in report['candidates'] if c['title'] == 'Instructor')
        self.lyro = json.loads((ROOT / 'tests/fixtures/business_product_source.json').read_text())

    def request(self, product, brief=None, name='Cycle repair', input_kind='text'):
        # Retain only the attributed excerpt; never masquerade as a full page snapshot.
        raw = ('<p>' + html.escape(product['description']) + '</p>').encode()
        path = self.store.directory / 'runs/product.html'
        path.write_bytes(raw)
        item = {'id': 'product-one', 'title': product['title'], 'url': product['url'],
                'publication_date': product.get('publication_date'),
                'retrieved_at': product['retrieved_at'], 'snapshot_path': 'runs/product.html',
                'raw_sha256': semantic.discovery.sha(raw),
                'content_sha256': semantic.discovery.sha(product['description']), 'source': 'saved-publisher-excerpt'}
        return semantic.prepare_business_assessment(self.store, item, brief or self.service,
                    name=name, input_kind=input_kind, sanitized=True)

    def mocked_response(self, request, relevant, need, benefit, action):
        """Hand-authored expectations, not a classifier or model simulation."""
        source = request['prepared']['source']
        claim = request['staged_plan']['claims'][0]
        value = {'candidate_id': source['candidate_id'],
            'category': 'potential relevance' if relevant else 'low relevance',
            'project_need_id': 'objective', 'project_need': need,
            'source_observation': claim['exact_quote'],
            'evidence': [{k: claim[k] for k in ('source_id', 'passage_id', 'exact_quote')}],
            'application_hypothesis': benefit if relevant else None,
            'limitations': ['Publisher claims only; business suitability and data handling are unverified.'],
            'missing_information': ['Current pricing, setup effort and performance on this business are unknown.'],
            'priority': 'medium' if relevant else 'low',
            'priority_reason': 'Review the stated capability against the business goal before adoption.',
            'investigation_question': 'Does this capability work on a small sanitized business example?' if relevant else None,
            'next_step': action, 'existing_findings_connection': None}
        return json.dumps({'assessments': [value]})

    def test_four_mocked_cross_industry_matches_and_rejections(self):
        cases = [
            (self.instructor, self.food, 'AI Raw Gourmet', True,
             'AI Raw Gourmet is developing an application that must preserve customer meal preferences.',
             'Hypothesis: If compatible with the prototype, this could help organize customer meal preferences before planning; the benefit is untested.',
             'Review one invented meal request with the developer before considering a small evaluation.'),
            (self.lyro, self.food, 'AI Raw Gourmet', False,
             'AI Raw Gourmet needs recipe and meal-plan adaptation; answering support questions is not that task.', None,
             'Set this aside unless a customer-support need is established.'),
            (self.lyro, self.service, 'Cycle repair', True,
             'Cycle repair needs to answer repeated customer questions from its website information.',
             'Hypothesis: If it can answer from approved shop policies, it could help customers find answers while the owner repairs bikes; this benefit is unverified.',
             'Review the public demo using one invented opening-hours question before sharing business data.'),
            (self.instructor, self.service, 'Cycle repair', False,
             'Cycle repair needs a ready-to-use customer service, not a programming library.', None,
             'Skip this library; look for a service the owner can use without coding.')]
        for product, brief, name, relevant, need, benefit, action in cases:
            with self.subTest(product=product['title'], business=name):
                request = self.request(product, brief, name)
                output = semantic.evaluate_business_response(
                    self.mocked_response(request, relevant, need, benefit, action), request)
                self.assertEqual(output['relevance'], 'potential relevance' if relevant else 'low relevance')
                self.assertEqual(output['possible_benefit'], benefit)
                self.assertEqual(output['next_step'], action)
                self.assertTrue(output['uncertainty'])
                self.assertIn('Unvalidated', output['label'])
                self.assertEqual(output['source_url'], product['url'])

    def test_actual_text_not_keyword_taxonomy_controls_prompt_and_identity(self):
        arbitrary = 'I run a ceramics studio. I want to describe commissioned glazes to customers in plain language.'
        a = self.request(self.lyro, arbitrary, 'Pottery studio', 'pdf')
        b = self.request(self.lyro, self.service, 'Cycle repair', 'txt')
        payload = json.loads(a['messages'][1]['content'])
        self.assertEqual(payload['approved_project_context']['profile']['objective'], arbitrary)
        self.assertEqual(payload['approved_project_context']['provenance']['input_kind'], 'pdf')
        self.assertNotEqual(a['prepared']['cache_key'], b['prepared']['cache_key'])
        self.assertNotIn('AI Raw Gourmet', json.dumps(payload))
        self.assertIn('Prefer usable products/services/agents', a['messages'][0]['content'])
        self.assertNotIn('explicitly discuss requirements extraction', a['messages'][0]['content'])
        self.assertEqual(set(semantic.output_contract([a['prepared']])['properties']['assessments']['items']['properties']), semantic.FIELDS)

    def test_no_default_or_unreviewed_brief(self):
        for brief in ('', 'short', 'x' * 12001, 'Project with a null\x00 character'):
            with self.assertRaises(ValueError): semantic.business_context(brief, sanitized=True)
        with self.assertRaises(ValueError): semantic.business_context(self.service)

    def test_strict_rejection_of_fabrications_guarantees_and_duplicate_outputs(self):
        request = self.request(self.lyro)
        content = self.mocked_response(request, True, 'Cycle repair needs answers to customer questions.',
            'Hypothesis: If suitable, it could help answer shop questions; this is unverified.',
            'Review one invented opening-hours question in the public demonstration.')
        original = json.loads(content)
        for field, change in [('evidence', [{'source_id': 'invented', 'passage_id': 'p1', 'exact_quote': 'Invented unsupported quotation.'}]),
                              ('source_observation', 'Invented but plausible capability description.'),
                              ('application_hypothesis', 'Hypothesis: This will guarantee 50% savings.'),
                              ('missing_information', []),
                              ('candidate_id', 'other-product')]:
            with self.subTest(field=field):
                changed = copy.deepcopy(original); changed['assessments'][0][field] = change
                with self.assertRaises(semantic.AssessmentError):
                    semantic.evaluate_business_response(json.dumps(changed), request)
        original['assessments'] *= 2
        with self.assertRaises(semantic.AssessmentError):
            semantic.evaluate_business_response(json.dumps(original), request)

    def test_input_and_snapshot_tampering_fail_closed(self):
        request = self.request(self.lyro)
        request['context']['profile']['objective'] = self.food
        with self.assertRaises(ValueError): semantic.evaluate_business_response('{}', request)
        request = self.request(self.lyro)
        request['prepared']['source']['passages'][0]['text'] = 'Altered source evidence with sufficient length.'
        with self.assertRaises(ValueError): semantic.evaluate_business_response('{}', request)

    def test_uncertainty_and_named_business_connection_remain_required(self):
        request = self.request(self.lyro)
        content = self.mocked_response(request, False, 'Cycle repair has an uncertain support need.', None,
                                      'Review whether customer questions are a real business priority.')
        value = json.loads(content)
        assessment = value['assessments'][0]
        assessment.update(category='uncertain relevance', project_need_id='uncertain',
                          investigation_question='Is the business actually seeking automated customer support?')
        output = semantic.evaluate_business_response(json.dumps(value), request)
        self.assertEqual(output['relevance'], 'uncertain relevance')
        self.assertIsNone(output['possible_benefit'])
        assessment['project_need'] = 'A generic business might need customer support.'
        with self.assertRaises(semantic.AssessmentError):
            semantic.evaluate_business_response(json.dumps(value), request)


if __name__ == '__main__': unittest.main()
