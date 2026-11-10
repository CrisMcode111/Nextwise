"""Offline Phase 2A planning/comparison; synthetic fixtures, no stored data reads."""
import copy
import hashlib
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import project_opportunities as planning


def state(name='AI Raw Gourmet', brief=None):
    return {'project':{'id':'project-synthetic', 'name':name,
        'brief':brief or ('AI Raw Gourmet is an existing prototype under development. '
            'Goal: deliver a usable application that generates and adapts recipes and meal plans to user constraints. '
            'Team size: 1. Environment: Windows 11, 16 GB RAM.')},
        'version':15, 'items':{}, 'briefings':[], 'decisions':[]}


def page(text, *, path='new.html', url='https://example.com/docs', when='2026-02-01T00:00:00Z'):
    raw = ('<main><p>'+text+'</p></main>').encode()
    readable = planning.html_extract.extract_readable_text(raw.decode())
    return {'url':url,'snapshot_path':path,'retrieved_at':when,
            'raw_sha256':hashlib.sha256(raw).hexdigest(),
            'content_sha256':hashlib.sha256(readable.encode()).hexdigest()}, raw


class OfflineTests(unittest.TestCase):
    def setUp(self):
        for target in ('socket.socket', 'tavily_discovery.search', 'tavily_discovery.public_page',
                       'tavily_discovery.runtime_config.secret',
                       'update_discovery.memory.call_bridge', 'semantic_discovery.analyzer.request_claims'):
            guard = patch(target, side_effect=AssertionError('Planning must not perform I/O'))
            guard.start()
            self.addCleanup(guard.stop)


class PlanningTests(OfflineTests):
    def test_ai_raw_gourmet_uses_saved_goal_and_resource_context(self):
        saved = state()
        before = copy.deepcopy(saved)
        result = planning.plan_discovery(saved)
        self.assertEqual(saved, before)
        self.assertEqual({q['domain'] for q in result['queries']}, {'technology','product'})
        self.assertIn('recipes', ' '.join(q['query'] for q in result['queries']))
        self.assertIn('meal', ' '.join(q['query'] for q in result['queries']))
        self.assertNotIn('AI Raw Gourmet', ' '.join(q['query'] for q in result['queries']))
        self.assertFalse(result['execution_authorized'])
        self.assertTrue(result['requires_query_review'])
        self.assertEqual(result['project_version'], 15)
        self.assertTrue(all(q['basis'] for q in result['queries']))
        checks = ' '.join(c['text'] for c in result['constraints_and_resources_to_check'])
        self.assertIn('Team size: 1', checks)
        self.assertIn('Windows 11, 16 GB RAM', checks)
        self.assertEqual(result['project_context'][0]['text'], saved['project']['brief'])

    def test_different_industries_produce_different_topics_without_forced_domains(self):
        fixtures = [
            ('Bakery', 'Goal: reduce ingredient inventory waste and improve delivery scheduling.', {'operations'}),
            ('Dental practice', 'Goal: automate repetitive appointment administration and booking.', {'productivity','operations'}),
            ('Bookshop', 'Goal: improve cash flow and manage invoices within a limited budget.', {'financial'}),
            ('Craft studio', 'Goal: improve social media marketing campaigns and acquire new clients.', {'marketing','commercial'}),
            ('Museum', 'Goal: improve accessibility and navigation in the visitor interface.', {'UX'}),
            ('Learning platform', 'Goal: improve onboarding and retention using customer feedback.', {'product'}),
        ]
        queries = []
        for name, brief, expected in fixtures:
            with self.subTest(name=name):
                result = planning.plan_discovery(state(name, brief))
                self.assertEqual({q['domain'] for q in result['queries']}, expected)
                queries.append([q['query'] for q in result['queries']])
        self.assertEqual(len({str(q) for q in queries}), len(fixtures))

    def test_all_domains_available_but_searches_remain_bounded(self):
        saved = state('Cooperative', 'Goal: improve software integration, product features, usability, '
                      'manual administration, cash flow, sales, marketing and inventory.')
        plan = planning.plan_discovery(saved)
        self.assertEqual(len(plan['queries']), 2)
        self.assertEqual({q['domain'] for q in plan['queries']+plan['queued_topics']}, set(planning.DOMAINS))
        self.assertEqual(plan['limits'], {'max_queries':2,'results_per_query':5,
                         'max_search_results':10,'max_source_pages':4,'max_retries':0})
        self.assertEqual(planning.plan_discovery(saved, max_queries=1)['limits']['max_queries'], 1)

    def test_limits_match_existing_transport_and_invalid_overrides_fail(self):
        plan = planning.plan_discovery(state())
        self.assertEqual(plan['limits']['max_queries'], planning.tavily.MAX_SEARCHES)
        self.assertEqual(plan['limits']['results_per_query'], planning.tavily.RESULTS_PER_SEARCH)
        self.assertEqual(plan['limits']['max_source_pages'], planning.tavily.MAX_SOURCE_PAGES)
        for key, values in [('max_queries', (0,3,True,1.5)), ('results_per_query',(0,6)), ('max_source_pages',(0,5))]:
            for value in values:
                with self.subTest(key=key,value=value), self.assertRaises(ValueError):
                    planning.plan_discovery(state(), **{key:value})

    def test_deterministic_plan_and_basis_digest(self):
        saved = state()
        self.assertEqual(planning.plan_discovery(saved), planning.plan_discovery(copy.deepcopy(saved)))
        altered = copy.deepcopy(saved)
        altered['project']['resources'] = {'team':'solo developer','budget':'limited'}
        changed = planning.plan_discovery(altered)
        self.assertNotEqual(changed['basis_sha256'], planning.plan_discovery(saved)['basis_sha256'])
        self.assertTrue(any(b['field']=='project.resources' for q in changed['queries']+changed['queued_topics'] for b in q['basis']))

    def test_stated_goals_outrank_resource_only_topics(self):
        saved = state('Museum', 'Goal: improve accessibility in our interface. Budget: limited costs.')
        result = planning.plan_discovery(saved, max_queries=1)
        self.assertEqual(result['queries'][0]['domain'], 'UX')
        self.assertEqual(result['queued_topics'][0]['domain'], 'financial')
        self.assertEqual(result['queued_topics'][0]['priority'], 'normal')

    def test_prior_decisions_change_priority_without_adding_goals_or_reopening(self):
        saved = state('Cooperative', 'Goal: improve software integration and marketing campaigns.')
        decision = {'id':'decision-1','candidate_id':'old-tool','version':1,'choice':'Defer',
                    'rationale':'Marketing campaign suitability remains unknown.'}
        saved['decisions'] = [decision]
        result = planning.plan_discovery(saved)
        self.assertEqual(result['queries'][0]['domain'], 'marketing')
        self.assertEqual(result['queries'][0]['decision_gap_references'], ['decision-1'])
        self.assertEqual(result['decision_constraints'][0]['choice'], 'Defer')
        saved['decisions'].append({**decision,'id':'decision-2','version':2,'choice':'Test'})
        self.assertEqual(planning.plan_discovery(saved)['decision_constraints'], [])
        self.assertEqual(planning.plan_discovery(saved)['decision_context'][0]['choice'], 'Test')
        saved['decisions'].append({**decision,'candidate_id':'unrelated','id':'decision-3','rationale':'Improve cash flow.'})
        self.assertNotIn('financial', [q['domain'] for q in planning.plan_discovery(saved)['queries']])

    def test_invalid_or_cross_project_decisions_fail_closed(self):
        for record in ({'choice':'Defer'}, {'candidate_id':'a','version':True,'choice':'Reject'},
                       {'candidate_id':'a','version':1,'choice':'Reject','project_id':'another'}):
            saved = state(); saved['decisions'] = [record]
            with self.assertRaises(ValueError): planning.plan_discovery(saved)
        saved = state(); saved['decisions'] = [
            {'id':'a','candidate_id':'a','version':1,'choice':'Reject'},
            {'id':'b','candidate_id':'a','version':1,'choice':'Defer'}]
        with self.assertRaises(ValueError): planning.plan_discovery(saved)

    def test_explicit_exclusions_and_unknown_vocabulary_do_not_force_searches(self):
        for brief in ('Do not pursue marketing or sales.', 'Explore a better way for our community.'):
            result = planning.plan_discovery(state('Community', brief))
            self.assertEqual(result['queries'], [])
            self.assertEqual(result['status'], 'needs_project_clarification')

    def test_queries_do_not_copy_contact_details_urls_or_numeric_resources(self):
        saved = state('Private Studio', 'Goal: improve inventory scheduling. '
                      'Resources: budget 5000, contact owner@example.com https://private.example.com.')
        result = planning.plan_discovery(saved)
        queries = ' '.join(q['query'] for q in result['queries'])
        for private in ('Private Studio','5000','owner','example.com','https:'):
            self.assertNotIn(private, queries)

    def test_planning_does_not_classify_or_recommend_candidates(self):
        result = planning.plan_discovery(state('Clinic', 'Goal: improve booking and scheduling.'))
        for q in result['queries']:
            self.assertNotIn('relevance', q)
            self.assertNotIn('recommended_choice', q)
        self.assertIn('not evidence of relevance', result['limitations'][0])


class ComparisonTests(OfflineTests):
    OLD = 'The service supports appointment booking using a shared public calendar for the clinic.'
    NEW = 'The service supports appointment booking using a shared public calendar for the clinic. It provides inventory management and supplier delivery scheduling for independent practices.'

    def setup_pages(self):
        old, raw = page(self.OLD, path='old.html', when='2026-01-01T00:00:00Z')
        saved = state(); saved['items'] = {'source':old}
        return saved, old, raw

    def test_new_source_does_not_imply_novel_claim_or_opportunity(self):
        candidate, raw = page(self.OLD)
        result = planning.compare_evidence(candidate, state(), snapshot=raw)
        self.assertEqual(result['classification'],'new')
        self.assertIn('novelty',result['reason'])
        self.assertFalse(result['opportunity_selected'])

    def test_known_current_content_and_cross_url_duplicates(self):
        saved, old, raw = self.setup_pages()
        candidate, new_raw = page(self.OLD)
        self.assertEqual(planning.compare_evidence(candidate,saved,snapshot=new_raw)['classification'],'already_known')
        candidate['url']='https://elsewhere.example/docs'
        self.assertEqual(planning.compare_evidence(candidate,saved,snapshot=new_raw)['classification'],'duplicate')

    def test_material_text_delta_requires_verified_snapshots_and_chronology(self):
        saved, old, raw = self.setup_pages()
        candidate, new_raw = page(self.NEW)
        before = copy.deepcopy(saved)
        result = planning.compare_evidence(candidate,saved,snapshot=new_raw,previous_snapshots={'old.html':raw})
        self.assertEqual(result['classification'],'materially_updated')
        self.assertEqual(result['comparison_status'],'verified_textual_delta')
        self.assertIn(self.NEW,result['added_passages'])
        self.assertIn(self.OLD,result['removed_passages'])
        self.assertFalse(result['reconsideration_authorized'])
        self.assertEqual(saved,before)

    def test_hash_or_timestamp_alone_cannot_establish_change(self):
        saved, old, raw = self.setup_pages()
        candidate, new_raw = page(self.NEW)
        for kwargs in ({}, {'snapshot':new_raw}, {'snapshot':new_raw,'previous_snapshots':{'old.html':b'tampered'}}):
            result = planning.compare_evidence(candidate,saved,**kwargs)
            self.assertEqual(result['classification'],'already_known')
            self.assertEqual(result['comparison_status'],'insufficient_comparison')
        for when in ('2025-12-01T00:00:00Z','2026-01-01T00:00:00Z',None,'invalid'):
            candidate['retrieved_at']=when
            self.assertEqual(planning.compare_evidence(candidate,saved,snapshot=new_raw,
                previous_snapshots={'old.html':raw})['comparison_status'],'insufficient_comparison')

    def test_cosmetic_and_small_deltas_do_not_claim_material_update(self):
        saved, old, raw = self.setup_pages()
        for text in (self.OLD.upper(),self.OLD.replace('calendar','calendar!'),self.OLD.replace('shared','common')):
            candidate, new_raw = page(text)
            result = planning.compare_evidence(candidate,saved,snapshot=new_raw,previous_snapshots={'old.html':raw})
            self.assertNotEqual(result['classification'],'materially_updated')

    def test_appended_navigation_does_not_relabel_an_unchanged_fact(self):
        saved,old,raw=self.setup_pages()
        candidate,new_raw=page(self.OLD+' Contact our team today for more information and subscribe to the newsletter.')
        result=planning.compare_evidence(candidate,saved,snapshot=new_raw,previous_snapshots={'old.html':raw})
        self.assertEqual(result['comparison_status'],'no_material_change_established')

    def test_raw_markup_change_with_same_readable_content_is_known(self):
        saved, old, raw = self.setup_pages()
        candidate = copy.deepcopy(old)
        new_raw = raw+b'<!-- new markup -->'
        candidate['raw_sha256']=hashlib.sha256(new_raw).hexdigest()
        self.assertEqual(planning.compare_evidence(candidate,saved,snapshot=new_raw)['classification'],'already_known')

    def test_previous_briefings_and_checkpoints_prevent_false_newness(self):
        saved, old, raw = self.setup_pages()
        saved['briefings']=[{'evidence_references':old,'context_evidence_references':[]}]
        saved['items']={}
        candidate, new_raw = page(self.OLD,url='https://mirror.example/docs')
        self.assertEqual(planning.compare_evidence(candidate,saved,snapshot=new_raw)['classification'],'duplicate')
        current=state()
        self.assertEqual(planning.compare_evidence(candidate,current,history=[saved])['classification'],'duplicate')
        saved['project']['id']='another'
        with self.assertRaises(ValueError): planning.compare_evidence(candidate,current,history=[saved])

    def test_reappearing_historical_content_is_duplicate_not_a_new_update(self):
        saved, old, raw = self.setup_pages()
        newer, newer_raw=page(self.NEW,path='current.html')
        saved['items']['source']=newer
        saved['briefings']=[{'evidence_references':old}]
        candidate, new_raw=page(self.OLD,when='2026-03-01T00:00:00Z')
        self.assertEqual(planning.compare_evidence(candidate,saved,snapshot=new_raw)['classification'],'duplicate')

    def test_ambiguous_latest_snapshot_does_not_invent_chronology(self):
        saved, old, raw = self.setup_pages()
        other, _=page('The service provides a different publicly documented capability for booking.',when=old['retrieved_at'])
        saved['items']['conflicting']=other
        candidate,new_raw=page(self.NEW)
        self.assertEqual(planning.compare_evidence(candidate,saved,snapshot=new_raw,
            previous_snapshots={'old.html':raw})['comparison_status'],'insufficient_comparison')

    def test_unsafe_sources_bad_digests_and_tampering_fail_closed(self):
        saved, old, raw = self.setup_pages()
        for url in ('http://example.com/','https://127.0.0.1/','https://localhost/','file:///tmp/a'):
            with self.assertRaises(ValueError): planning.compare_evidence({**old,'url':url},saved)
        with self.assertRaises(ValueError): planning.compare_evidence({**old,'content_sha256':'bad'},saved)
        with self.assertRaises(ValueError): planning.compare_evidence(old,saved,snapshot=b'tampered')

    def test_missing_content_comparison_remains_known_and_unknown(self):
        saved, old, raw=self.setup_pages()
        candidate={'url':old['url'],'retrieved_at':'2026-02-01T00:00:00Z'}
        result=planning.compare_evidence(candidate,saved)
        self.assertEqual(result['classification'],'already_known')
        self.assertEqual(result['comparison_status'],'insufficient_comparison')

    def test_large_text_delta_stays_bounded_and_requires_manual_review(self):
        saved,old,raw=self.setup_pages()
        candidate,new_raw=page('The service provides '+ 'different inventory functions '*2500)
        result=planning.compare_evidence(candidate,saved,snapshot=new_raw,previous_snapshots={'old.html':raw})
        self.assertEqual(result['comparison_status'],'insufficient_comparison')


if __name__ == '__main__':
    unittest.main()
