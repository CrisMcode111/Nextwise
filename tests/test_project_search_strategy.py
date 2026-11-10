"""Focused offline adaptive strategy tests; no service, provider or saved data."""
import copy
import uuid

from test_project_opportunities import OfflineTests, state, page, planning


def attempt(number=1):
    return str(uuid.UUID(int=number))


def strategy(saved=None, **allowance):
    saved = saved or state('Clinic', 'Goal: improve booking and repetitive manual administration.')
    plan = planning.plan_discovery(saved)
    return saved, planning.create_strategy(saved,plan,allowance={
        'queries':2,'results':10,'pages':4,**allowance})


def reserve(saved, ledger, number=1):
    return planning.reserve_search(saved,ledger,ledger['proposals'][0]['proposal_id'],attempt_id=attempt(number))


def source(saved, candidate='source-1', category=None, url=None):
    quote = 'The service provides public appointment booking and scheduling for independent clinics.'
    item, _ = page(quote,url=url or 'https://example.com/'+candidate)
    item['id'] = candidate; item['title'] = candidate
    saved['items'][candidate] = item
    if category:
        record = {'id':'assessment-'+candidate,'candidate_id':candidate,
                  'validation':'contract_and_source_quotes_checked',
                  'assessment':{'category':category,'evidence':[{'exact_quote':quote}]}}
        saved.setdefault('assessments',[]).append(record)
        brief = {'id':'brief-'+candidate,'candidate_id':candidate,'assessment_id':record['id'],
                 'evidence_references':copy.deepcopy(item)}
        saved['briefings'].append(brief)
        saved.setdefault('briefing_current',{})[brief['id']] = True
    return {'source_key':candidate,'candidate_id':candidate,'usability':'usable','coverage':'saved_page',
            'comparison':{'classification':'new','comparison_status':'source_identity_only'}}


def feedback(*sources, number=1, **overrides):
    return {'feedback_id':'feedback-'+str(number),'attempt_id':attempt(number),
            'accounting_confirmed':True,'status':'completed','results_received':len(sources),
            'pages_attempted':sum(s['coverage']=='saved_page' for s in sources),
            'sources':list(sources),**overrides}


class AdaptiveStrategyTests(OfflineTests):
    def test_weak_empty_results_propose_different_direction_within_allowance(self):
        saved,ledger=strategy()
        first=ledger['proposals'][0]
        ledger=reserve(saved,ledger)
        self.assertEqual(ledger['status'],'awaiting_reserved_search_outcome')
        result=planning.adapt_strategy(saved,ledger,feedback=[feedback()])
        self.assertEqual(result['evaluations'][0]['outcome'],'weak')
        self.assertEqual(result['remaining'],{'queries':1,'results':10,'pages':4})
        self.assertEqual(len(result['proposals']),1)
        self.assertNotEqual(result['proposals'][0]['query'],first['query'])
        self.assertNotEqual(result['proposals'][0]['direction'],first['direction'])
        self.assertFalse(result['execution_authorized'])

    def test_single_direction_uses_alternative_source_category(self):
        saved=state('Shop','Goal: improve inventory scheduling for our shop.')
        saved,ledger=strategy(saved)
        original=ledger['proposals'][0]['query']
        result=planning.adapt_strategy(saved,reserve(saved,ledger),feedback=[feedback()])
        self.assertEqual(result['proposals'][0]['reason'],'alternative_source_category')
        self.assertNotEqual(result['proposals'][0]['query'],original)

    def test_usable_novel_current_potential_result_stops_search_for_review(self):
        saved,ledger=strategy()
        item=source(saved,category='potential relevance')
        result=planning.adapt_strategy(saved,reserve(saved,ledger),feedback=[feedback(item)])
        self.assertEqual(result['status'],'promising')
        self.assertEqual(result['proposals'],[])
        self.assertEqual(result['priority_feedback'][0]['adjustment'],2)
        self.assertFalse(result['evaluations'][0]['selection_made'])

    def test_keyword_like_source_without_assessment_is_not_relevance_proof(self):
        saved,ledger=strategy()
        item=source(saved)
        result=planning.adapt_strategy(saved,reserve(saved,ledger),feedback=[feedback(item)])
        self.assertEqual(result['status'],'needs_assessment')
        self.assertEqual(result['evaluations'][0]['counts']['potential'],0)
        self.assertFalse(result['evaluations'][0]['selection_made'])

    def test_low_uncertain_and_stale_results_have_distinct_feedback(self):
        for category,expected in [('low relevance','weak'),('uncertain relevance','needs_evidence_review'),
                                  ('potential relevance','needs_evidence_review')]:
            with self.subTest(category=category):
                saved,ledger=strategy(); item=source(saved,category=category)
                if category=='potential relevance':saved['briefing_current']['brief-source-1']=False
                result=planning.adapt_strategy(saved,reserve(saved,ledger),feedback=[feedback(item)])
                self.assertEqual(result['evaluations'][0]['outcome'],expected)

    def test_unusable_or_snippet_only_results_cannot_be_successful(self):
        for coverage,usability in [('snippet','usable'),('saved_page','unsafe'),('unknown','unavailable')]:
            saved,ledger=strategy(); item=source(saved,category='potential relevance')
            item.update(coverage=coverage,usability=usability)
            result=planning.adapt_strategy(saved,reserve(saved,ledger),feedback=[feedback(item)])
            self.assertEqual(result['evaluations'][0]['outcome'],'weak')
            self.assertEqual(result['evaluations'][0]['counts']['usable'],0)

    def test_duplicates_and_unknown_comparisons_are_not_novel(self):
        for comparison in ({'classification':'duplicate','comparison_status':'matching_content_digest'},
                           {'classification':'already_known','comparison_status':'insufficient_comparison'},{}):
            saved,ledger=strategy(); item=source(saved,category='potential relevance'); item['comparison']=comparison
            result=planning.adapt_strategy(saved,reserve(saved,ledger),feedback=[feedback(item)])
            self.assertNotEqual(result['evaluations'][0]['outcome'],'promising')
            self.assertEqual(result['evaluations'][0]['counts']['novel'],0)

    def test_duplicate_content_at_different_urls_is_counted_once(self):
        saved,ledger=strategy()
        first=source(saved,'first','low relevance','https://one.example/docs')
        second=source(saved,'second','potential relevance','https://two.example/docs')
        result=planning.adapt_strategy(saved,reserve(saved,ledger),feedback=[feedback(first,second)])
        self.assertEqual(result['evaluations'][0]['counts']['duplicates'],1)
        self.assertEqual(result['evaluations'][0]['outcome'],'weak')

    def test_latest_reject_or_defer_blocks_source_and_product_alias(self):
        for choice in ('Reject','Defer'):
            saved,ledger=strategy(); first=source(saved,'old','potential relevance')
            alias=source(saved,'alias','potential relevance',url='https://example.com/new-page')
            saved['decisions']=[{'id':'human','candidate_id':'old','choice':choice,'version':1,'rationale':'Not suitable.'}]
            ledger=planning.adapt_strategy(saved,ledger)
            result=planning.adapt_strategy(saved,reserve(saved,ledger),feedback=[feedback(alias)])
            self.assertEqual(result['evaluations'][0]['counts']['blocked'],1)
            self.assertEqual(result['evaluations'][0]['outcome'],'weak')
            self.assertEqual(saved['decisions'][0]['choice'],choice)

    def test_human_decision_change_requires_refresh_without_resetting_budget(self):
        saved=state('Studio','Goal: improve software integration and marketing campaigns.')
        saved,ledger=strategy(saved)
        ledger=planning.adapt_strategy(saved,reserve(saved,ledger),feedback=[feedback()])
        saved['decisions']=[{'id':'human','candidate_id':'old','version':1,'choice':'Defer',
                             'rationale':'Marketing campaign evidence is missing.'}]
        with self.assertRaises(ValueError):reserve(saved,ledger,2)
        refreshed=planning.adapt_strategy(saved,ledger)
        self.assertEqual(refreshed['remaining'],ledger['remaining'])
        self.assertEqual(refreshed['proposals'][0]['direction'],'marketing')

    def test_queries_do_not_target_a_previously_rejected_named_product(self):
        saved=state('Studio','Goal: improve OldVendor software integration for our project.')
        item=source(saved,'old'); saved['items']['old']['title']='OldVendor'
        saved['decisions']=[{'id':'human','candidate_id':'old','version':1,'choice':'Reject','rationale':'Not suitable.'}]
        saved,ledger=strategy(saved)
        self.assertEqual(ledger['proposals'],[])

    def test_repeated_feedback_is_idempotent_and_conflicts_fail(self):
        saved,ledger=strategy(); ledger=reserve(saved,ledger)
        report=feedback(); once=planning.adapt_strategy(saved,ledger,feedback=[report])
        again=planning.adapt_strategy(saved,once,feedback=[report])
        self.assertEqual(once,again)
        with self.assertRaises(ValueError):planning.adapt_strategy(saved,once,feedback=[{**report,'status':'failed'}])
        with self.assertRaises(ValueError):planning.adapt_strategy(saved,ledger,feedback=[feedback(number=2)])

    def test_reservation_is_idempotent_but_never_reused_for_another_query(self):
        saved,ledger=strategy(); proposal=ledger['proposals'][0]['proposal_id']
        reserved=reserve(saved,ledger)
        self.assertEqual(reserved,planning.reserve_search(saved,reserved,proposal,attempt_id=attempt()))
        with self.assertRaises(ValueError):planning.reserve_search(saved,reserved,'other',attempt_id=attempt())
        with self.assertRaises(ValueError):planning.reserve_search(saved,reserved,proposal,attempt_id=attempt(2))

    def test_failures_consume_queries_and_unknown_accounting_keeps_capacity_reserved(self):
        saved,ledger=strategy(); ledger=reserve(saved,ledger)
        result=planning.adapt_strategy(saved,ledger,feedback=[feedback(status='failed',accounting_confirmed=False,
                                              results_received=None,pages_attempted=None)])
        self.assertEqual(result['remaining'],{'queries':1,'results':5,'pages':0})
        self.assertEqual(result['proposals'],[])
        with self.assertRaises(ValueError):planning.adapt_strategy(saved,ledger,feedback=[feedback(
            status='failed',accounting_confirmed=False,results_received=0,pages_attempted=0)])

    def test_two_consumed_queries_exhaust_allowance_even_if_both_return_nothing(self):
        saved,ledger=strategy()
        for number in (1,2):
            ledger=reserve(saved,ledger,number)
            ledger=planning.adapt_strategy(saved,ledger,feedback=[feedback(number=number)])
        self.assertEqual(ledger['remaining']['queries'],0)
        self.assertEqual(ledger['status'],'budget_exhausted')
        self.assertEqual(ledger['proposals'],[])
        with self.assertRaises(ValueError):planning.reserve_search(saved,ledger,'anything',attempt_id=attempt(3))

    def test_each_cumulative_budget_can_stop_search_independently(self):
        for caps in ({'queries':0},{'results':0},{'pages':0}):
            saved,ledger=strategy(**caps)
            self.assertEqual(ledger['status'],'budget_exhausted')
        saved,ledger=strategy(results=1,pages=1)
        item=source(saved,category='low relevance')
        ledger=planning.adapt_strategy(saved,reserve(saved,ledger),feedback=[feedback(item)])
        self.assertEqual(ledger['remaining'],{'queries':1,'results':0,'pages':0})
        self.assertEqual(ledger['proposals'],[])

    def test_over_budget_or_false_accounting_is_rejected_without_mutation(self):
        saved,ledger=strategy(); ledger=reserve(saved,ledger); before=copy.deepcopy(ledger)
        for override in ({'results_received':6},{'pages_attempted':5},{'results_received':True},{'pages_attempted':-1}):
            with self.assertRaises(ValueError):planning.adapt_strategy(saved,ledger,feedback=[feedback(**override)])
        self.assertEqual(ledger,before)
        for allowance in ({'queries':3},{'results':11},{'pages':5},{'queries':True}):
            with self.assertRaises(ValueError):strategy(**allowance)

    def test_integrity_and_project_changes_cannot_reset_a_ledger(self):
        saved,ledger=strategy(); tampered=copy.deepcopy(ledger); tampered['allowance']['queries']=3
        with self.assertRaises(ValueError):planning.adapt_strategy(saved,tampered)
        saved['project']['brief']+=' The objective has changed.'
        with self.assertRaises(ValueError):planning.adapt_strategy(saved,ledger)

    def test_feedback_and_inputs_are_immutable_and_deterministic(self):
        saved,ledger=strategy(); reserved=reserve(saved,ledger); report=feedback()
        before=copy.deepcopy((saved,reserved,report))
        first=planning.adapt_strategy(saved,reserved,feedback=[report])
        self.assertEqual(first,planning.adapt_strategy(saved,reserved,feedback=[report]))
        self.assertEqual((saved,reserved,report),before)

    def test_same_source_in_a_later_search_uses_feedback_history(self):
        saved,ledger=strategy(); item=source(saved,category='low relevance')
        ledger=planning.adapt_strategy(saved,reserve(saved,ledger),feedback=[feedback(item)])
        ledger=planning.adapt_strategy(saved,reserve(saved,ledger,2),feedback=[feedback(item,number=2)])
        self.assertEqual(ledger['evaluations'][1]['counts']['duplicates'],1)
        self.assertEqual(ledger['evaluations'][1]['counts']['novel'],0)

    def test_confirmed_failed_attempt_is_consumed_and_not_retried(self):
        saved,ledger=strategy(); query=ledger['proposals'][0]['query']
        result=planning.adapt_strategy(saved,reserve(saved,ledger),feedback=[feedback(status='failed')])
        self.assertEqual(result['remaining']['queries'],1)
        self.assertTrue(all(p['query']!=query for p in result['proposals']))

    def test_pending_reservation_escrows_pages_until_confirmed(self):
        saved,ledger=strategy(); ledger=reserve(saved,ledger)
        self.assertEqual(ledger['remaining'],{'queries':1,'results':5,'pages':0})
        self.assertEqual(ledger['proposals'],[])
        item=source(saved)
        with self.assertRaises(ValueError):planning.adapt_strategy(saved,ledger,feedback=[feedback(item,pages_attempted=0)])

    def test_coverage_records_searched_and_unsearched_directions_without_claiming_fit(self):
        saved,ledger=strategy(); direction=ledger['proposals'][0]['direction']
        item=source(saved); item['coverage']='snippet'
        result=planning.adapt_strategy(saved,reserve(saved,ledger),feedback=[feedback(item)])
        covered=result['coverage_feedback']['directions'][direction]
        self.assertEqual(covered['queries_reserved'],1)
        self.assertEqual(covered['queries_reported'],1)
        self.assertEqual(covered['usable_saved_pages'],0)
        self.assertEqual(covered['validated_potential_signals'],0)
        self.assertEqual(len(result['coverage_feedback']['not_yet_searched']),1)


class MultilingualAndCategoryTests(OfflineTests):
    def test_unknown_multilingual_semantics_are_explicit_not_English_guesses(self):
        for brief in ('Je souhaite une application pour organiser les rendez-vous.',
                      'Quiero mejorar la gestión del inventario y las entregas.',
                      '我想改善诊所预约安排，减少重复工作。',
                      'Notre application doit aider les clients.'):
            with self.subTest(brief=brief):
                saved=state('Projet',brief); plan=planning.plan_discovery(saved)
                self.assertEqual(plan['queries'],[])
                self.assertEqual(plan['status'],'needs_semantic_interpretation')

    def test_explicit_language_and_reviewed_native_query_remain_inspectable(self):
        brief='我想改善诊所预约安排，减少重复工作。'; saved=state('诊所',brief)
        topic={'direction':'诊所预约流程','context_excerpt':brief,'query':'诊所 预约安排 工作流程 官方产品文档',
               'source_categories':['official_documentation'],'reviewed':True,'review_reference':'human-reviewed-fixture'}
        plan=planning.plan_discovery(saved,language='zh',semantic_topics=[topic])
        self.assertEqual(plan['queries'][0]['query'],topic['query'])
        self.assertEqual(plan['language_context']['semantic_interpretation'],'caller_reviewed_topics')
        ledger=planning.create_strategy(saved,plan,allowance={'queries':2,'results':10,'pages':4})
        self.assertEqual(ledger['proposals'][0]['query'],topic['query'])
        self.assertFalse(ledger['execution_authorized'])

        ledger=planning.adapt_strategy(saved,reserve(saved,ledger),feedback=[feedback()])
        self.assertEqual(ledger['status'],'needs_semantic_interpretation')
        self.assertEqual(ledger['proposals'],[])  # No invented translation or English suffix.

    def test_unreviewed_or_ungrounded_interpretations_are_not_accepted(self):
        saved=state('Projet','Je souhaite organiser les rendez-vous de notre clinique.')
        topic={'direction':'booking','context_excerpt':saved['project']['brief'],
               'query':'clinique rendez-vous documentation officielle','source_categories':['official_documentation'],
               'reviewed':True,'review_reference':'human-review'}
        for override in ({'reviewed':False},{'context_excerpt':'This goal is not in the saved project.'},
                         {'source_categories':['invented_unsubstantiated_category']}):
            with self.assertRaises(ValueError):planning.plan_discovery(saved,language='fr',semantic_topics=[{**topic,**override}])

    def category_fixture(self):
        saved=state('Supplier','Goal: improve sales through public procurement contracts for our company.')
        item=source(saved,category='potential relevance')
        saved,ledger=strategy(saved)
        record=saved['assessments'][0]
        proposal={'direction':'public_procurement','source_category':'government_tender_notices',
                  'context_excerpt':saved['project']['brief'],'candidate_id':'source-1','assessment_id':record['id'],
                  'evidence_quote':record['assessment']['evidence'][0]['exact_quote'],
                  'query':'public procurement supplier eligibility official tender notices',
                  'reviewed':True,'review_reference':'reviewed-category-interpretation'}
        # This fixture represents validated procurement evidence, not generic
        # clinic text being reused as proof of a new source category.
        quote='The government portal provides public procurement notices and supplier eligibility terms.'
        item,_=page(quote); item['id']='source-1'; item['title']='Procurement portal'
        saved['items']['source-1']=item
        record['assessment']['evidence']=[{'exact_quote':quote}]
        saved['briefings'][0]['evidence_references']=copy.deepcopy(item)
        proposal['evidence_quote']=quote
        return saved,ledger,proposal

    def test_evidence_supported_source_category_can_extend_the_fixed_taxonomy(self):
        saved,ledger,proposal=self.category_fixture()
        result=planning.adapt_strategy(saved,ledger,category_proposals=[proposal])
        self.assertTrue(result['category_feedback'][0]['accepted'])
        self.assertEqual(result['proposals'][0]['source_categories'],['government_tender_notices'])
        self.assertEqual(result['proposals'][0]['direction'],'public_procurement')
        self.assertNotIn('public_procurement',planning.DOMAINS)
        self.assertEqual(result['allowance'],ledger['allowance'])

    def test_category_extension_requires_current_evidence_and_project_context(self):
        for override in ({'context_excerpt':'Not a project objective.'},{'evidence_quote':'Invented quotation, not saved evidence.'},
                         {'assessment_id':'missing'},{'reviewed':False}):
            saved,ledger,proposal=self.category_fixture()
            result=planning.adapt_strategy(saved,ledger,category_proposals=[{**proposal,**override}])
            self.assertFalse(result['category_feedback'][0]['accepted'])
        saved,ledger,proposal=self.category_fixture()
        saved['briefing_current']['brief-source-1']=False
        result=planning.adapt_strategy(saved,ledger,category_proposals=[proposal])
        self.assertFalse(result['category_feedback'][0]['accepted'])

    def test_new_category_support_is_rechecked_after_human_rejection(self):
        saved,ledger,proposal=self.category_fixture()
        ledger=planning.adapt_strategy(saved,ledger,category_proposals=[proposal])
        self.assertEqual(ledger['proposals'][0]['direction'],'public_procurement')
        saved['decisions']=[{'id':'human','candidate_id':'source-1','version':1,'choice':'Reject','rationale':'Not suitable.'}]
        refreshed=planning.adapt_strategy(saved,ledger)
        self.assertFalse(any(p['direction']=='public_procurement' for p in refreshed['proposals']))

    def test_historical_assessment_cannot_support_a_new_category(self):
        saved,ledger,proposal=self.category_fixture()
        latest=copy.deepcopy(saved['assessments'][0]); latest['id']='new-assessment'
        saved['assessments'].append(latest)
        saved['briefings'][0]['assessment_id']=latest['id']
        result=planning.adapt_strategy(saved,ledger,category_proposals=[proposal])
        self.assertFalse(result['category_feedback'][0]['accepted'])

    def test_rejected_source_cannot_open_a_new_category(self):
        saved,ledger,proposal=self.category_fixture()
        saved['decisions']=[{'id':'human','candidate_id':'source-1','version':1,'choice':'Reject','rationale':'Not suitable.'}]
        result=planning.adapt_strategy(saved,ledger,category_proposals=[proposal])
        self.assertFalse(result['category_feedback'][0]['accepted'])


if __name__ == '__main__':
    import unittest
    unittest.main()
