"""Synthetic reproductions of the saved failures; no transport or memory access."""
import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import semantic_discovery as semantic
from semantic_fixture import assessment, context


class OutputContractTests(unittest.TestCase):
    def prepared(self, cid='fixture-candidate', existing=True):
        return {'source': {'candidate_id': cid, 'source_id': 'fixture-source-' + cid,
            'existing_investigation': existing,
            'passages': [{'passage_id': 'p' + str(i),
                'text': f'ISOLATED passage {i}: a task interface preserves explicitly stated requirements in structured data.'}
                for i in range(1, 9)]}}

    def value(self, prepared):
        value = assessment(prepared['source'])
        value.update(category='low relevance', priority='low', investigation_question=None)
        return value

    def test_prompt_counts_and_limits_come_from_common_constants_for_one_and_many(self):
        for size in (1, 2):
            batch = [self.prepared('candidate-' + str(i)) for i in range(size)]
            before = copy.deepcopy(batch)
            system, user = semantic.messages(batch, context())
            text = system['content']
            self.assertIn(f'return exactly {size} assessment objects total', text)
            self.assertIn(f'evidence array has at most {semantic.EVIDENCE_CAP} entries', text)
            self.assertIn(f'array requires 1–{semantic.GAP_CAP} substantive strings', text)
            self.assertIn('not an output checklist', text)
            self.assertIn('Do not append alternative, summary or placeholder copies', text)
            schema = semantic.output_contract(batch)['properties']['assessments']
            self.assertEqual(schema['minItems'], size)
            self.assertEqual(schema['maxItems'], size)
            self.assertEqual(schema['items']['properties']['evidence']['maxItems'], semantic.EVIDENCE_CAP)
            self.assertEqual(json.loads(user['content'])['untrusted_sources'], [p['source'] for p in batch])
            self.assertEqual(batch, before)  # All eight complete paragraphs remain supplied.

    def test_distinct_and_identical_duplicate_candidates_remain_rejected_without_dedup(self):
        prepared = self.prepared(); first = self.value(prepared)
        for skeleton in (False, True):
            second = copy.deepcopy(first)
            if skeleton: second.update(evidence=[], limitations=[], missing_information=[])
            values = [first, second]; before = copy.deepcopy(values)
            with self.assertRaises(semantic.AssessmentError) as error:
                semantic.parse_batch(json.dumps({'assessments': values}), [prepared])
            self.assertEqual(error.exception.diagnostic['code'], 'batch_identity')
            self.assertEqual(error.exception.diagnostic['duplicate_count'], 1)
            self.assertEqual(values, before)

    def test_eight_exact_quotes_rejected_three_allowed_no_truncation(self):
        prepared = self.prepared(); value = self.value(prepared); source = prepared['source']
        value['evidence'] = [{'source_id': source['source_id'], 'passage_id': p['passage_id'], 'exact_quote': p['text']}
                             for p in source['passages']]
        before = copy.deepcopy(value)
        with self.assertRaises(semantic.AssessmentError) as error: semantic.validate(value, prepared)
        self.assertEqual(error.exception.diagnostic['code'], 'evidence_type')
        self.assertEqual(value, before)
        # A separately generated fixture with three quotations remains valid.
        bounded = self.value(prepared)
        bounded['evidence'] = copy.deepcopy(value['evidence'][:semantic.EVIDENCE_CAP])
        self.assertEqual(semantic.validate(bounded, prepared), bounded)

    def test_empty_gaps_missing_support_and_null_existing_link_stay_invalid_for_low_relevance(self):
        prepared = self.prepared()
        for field, empty, code in [('limitations', [], 'evidence_gaps'),
                                    ('missing_information', [], 'evidence_gaps'),
                                    ('evidence', [], 'supporting_passage_required'),
                                    ('existing_findings_connection', None, 'existing_findings')]:
            value = self.value(prepared); value[field] = empty; before = copy.deepcopy(value)
            with self.assertRaises(semantic.AssessmentError) as error: semantic.validate(value, prepared)
            self.assertEqual(error.exception.diagnostic['code'], code)
            self.assertEqual(value, before)

    def test_bounded_low_uncertain_and_positive_fixtures_keep_strict_source_checks(self):
        prepared = self.prepared()
        for value in (self.value(prepared), assessment(prepared['source']), assessment(prepared['source'], True)):
            self.assertEqual(semantic.validate(value, prepared), value)
            for field, bad in [('source_id', 'wrong'), ('passage_id', 'absent'), ('exact_quote', 'An invented quotation that is not in any supplied paragraph.')]:
                invalid = copy.deepcopy(value); invalid['evidence'][0][field] = bad
                with self.assertRaises(semantic.AssessmentError): semantic.validate(invalid, prepared)


if __name__ == '__main__': unittest.main()
