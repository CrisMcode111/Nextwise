"""Phase 2F: local understanding, clarification, focus and strategy integration."""
import copy
import tempfile
import uuid
from pathlib import Path
from unittest.mock import patch

from test_project_opportunities import OfflineTests, state, planning
import project_understanding as understanding


class UnderstandingTests(OfflineTests):
    def plan(self, saved=None, **options):
        return understanding.prepare_research(saved or state(), **options)

    def test_prior_search_is_deprioritized_without_forbidding_a_revisit(self):
        saved = state()
        first = self.plan(saved, max_queries=1)
        previous = first['queries'][0]['query']
        saved['adaptive_discovery_runs'] = {'old':{'strategy':{'reservations':[{'query':previous}]}}}
        again = self.plan(saved, max_queries=1)
        topics = again['queries'] + again['queued_topics']
        matched = next(t for t in topics if t['query'] == previous)
        self.assertTrue(matched['previously_searched'])
        if len(topics) > 1:
            self.assertNotEqual(again['queries'][0]['query'], previous)

    def test_recipe_goal_is_specific_without_unnecessary_questions(self):
        result = self.plan()
        self.assertEqual(result['understanding']['clarification_questions'], [])
        first = result['queries'][0]
        self.assertIn('recipe generation meal planning', first['query'])
        self.assertIn('documentation', first['query'])
        self.assertIn('?', first['research_question'])
        self.assertNotIn('goal deliver', first['query'])
        self.assertFalse(result['execution_authorized'])
        self.assertFalse(result['understanding']['model_call_authorized'])

    def test_roles_and_attribution_do_not_promote_hypotheses_to_facts(self):
        result = self.plan(state('Clinic', 'Goal: reduce appointment delays. We need booking integration. '
                         'Problem: manual administration. Constraints: limited budget. '
                         'Team: two staff. Unknown: whether APIs support our workflow. Priority: technology.'))
        u = result['understanding']
        kinds = {k for f in u['confirmed_facts'] for k in f['kinds']}
        self.assertTrue({'goals','needs','problems','constraints','resources','uncertainties','priorities'} <= kinds)
        self.assertTrue(all(not f['independently_verified'] for f in u['confirmed_facts']))
        self.assertTrue(u['hypotheses'])
        self.assertTrue(all(h['status'] == 'unverified' for h in u['hypotheses']))

    def test_vague_marketing_asks_two_material_questions_and_waits(self):
        result = self.plan(state('Idea', 'I have a small business and want help.'), research_focus='marketing')
        self.assertEqual([q['id'] for q in result['understanding']['clarification_questions']], ['subject','outcome'])
        self.assertEqual(result['queries'], [])
        self.assertEqual(result['status'], 'needs_project_clarification')

    def test_answers_create_preview_with_separate_provenance_without_mutation(self):
        saved = state('Idea', 'I have a small business and want help.')
        before = copy.deepcopy(saved)
        result = self.plan(saved, research_focus='marketing', clarifications={
            'subject':'A bakery serving local families.', 'outcome':'Increase visits from local customers.'})
        self.assertEqual(result['understanding']['clarification_questions'], [])
        self.assertEqual(result['queries'][0]['domain'], 'marketing')
        self.assertIn('bakery', result['queries'][0]['query'])
        self.assertIn('local customers', result['queries'][0]['query'])
        self.assertIn('store visits', result['queries'][0]['query'])
        self.assertEqual(saved, before)
        self.assertTrue(any(f['provenance']=='current_user_answer' for f in result['understanding']['confirmed_facts']))
        self.assertFalse(result['execution_authorized'])

    def test_clear_marketing_goal_needs_no_questions_but_audience_gap_does(self):
        result = self.plan(state('Bakery', 'Goal: increase bakery visits from local customers.'), research_focus='marketing')
        self.assertFalse(result['understanding']['clarification_questions'])
        vague = self.plan(state('Bakery', 'Goal: improve bakery marketing.'), research_focus='marketing')
        self.assertEqual([q['id'] for q in vague['understanding']['clarification_questions']], ['audience','outcome'])

    def test_multiple_industries_have_distinct_evidence_queries(self):
        cases = [('Bakery','Goal: reduce bakery inventory waste.', 'bakery'),
                 ('Dentist','Goal: improve dental appointment booking.', 'dental practice'),
                 ('Bookshop','Goal: improve bookshop cash flow.', 'bookshop'),
                 ('Museum','Goal: improve museum accessibility.', 'museum'),
                 ('Education','Goal: improve learning platform onboarding.', 'learning platform')]
        queries = []
        for name, brief, anchor in cases:
            with self.subTest(name=name):
                plan = self.plan(state(name, brief))
                self.assertFalse(plan['understanding']['clarification_questions'])
                self.assertIn(anchor, plan['queries'][0]['query'])
                queries.append(plan['queries'][0]['query'])
        self.assertEqual(len(set(queries)),len(cases))

    def test_focus_changes_priorities_without_dropping_context_or_history(self):
        saved=state(); saved['items']={'old':{'title':'Saved evidence'}}
        before=copy.deepcopy(saved)
        for focus, domain in [('technology','technology'),('product development','product'),('funding','financial')]:
            result=self.plan(saved,research_focus=focus,max_queries=1)
            self.assertEqual(result['queries'][0]['domain'],domain)
            self.assertEqual(result['project_context'][0]['text'],saved['project']['brief'])
            self.assertEqual(result['limits']['max_queries'],1)
        self.assertEqual(saved,before)

    def test_explicit_saved_priority_and_general_override(self):
        saved=state(brief=state()['project']['brief']+' Priority: funding.')
        self.assertEqual(self.plan(saved)['queries'][0]['domain'],'financial')
        self.assertEqual(self.plan(saved,research_focus='general')['queries'][0]['domain'],'technology')

    def test_focus_cannot_override_explicit_exclusion(self):
        saved=state(brief=state()['project']['brief']+' Do not pursue funding.')
        result=self.plan(saved,research_focus='funding')
        self.assertEqual(result['queries'],[])
        self.assertEqual(result['understanding']['clarification_questions'][0]['id'],'focus_conflict')

    def test_negation_uncertainty_and_unknown_vocabulary_fail_closed(self):
        for brief in ('Do not pursue recipes or meal planning. We need help.',
                      'We are not sure whether to build a restaurant or clinic.',
                      'Goal: improve quantum ferret harmonization.'):
            with self.subTest(brief=brief):
                result=self.plan(state('Private',brief))
                self.assertEqual(result['queries'],[])
                self.assertTrue(result['understanding']['clarification_questions'])

    def test_unrelated_uncertainty_does_not_force_project_reclarification(self):
        result=self.plan(state(brief=state()['project']['brief']+
                              ' Goal: improve onboarding. Unknown: operating budget.'))
        self.assertFalse(result['understanding']['clarification_questions'])
        self.assertIn('Unknown: operating budget.',result['understanding']['open_project_questions'])

    def test_multilingual_ambiguity_is_explicit_and_questions_are_localized(self):
        for language, brief, phrase in [('fr','Je souhaite améliorer notre boutique.','Quel besoin'),
                                        ('es','Quiero mejorar nuestro negocio.','Qué necesidad'),
                                        ('zh','我们希望改善预约服务。','Which project need')]:
            with self.subTest(language=language):
                result=self.plan(state('Private',brief),language=language)
                self.assertEqual(result['queries'],[])
                self.assertIn(phrase,result['understanding']['clarification_questions'][0]['question'])
                self.assertLessEqual(len(result['understanding']['clarification_questions']),2)

    def test_existing_reviewed_semantic_contract_accepts_native_queries(self):
        brief='Objectif : améliorer les rendez-vous de notre clinique.'
        saved=state('Clinique',brief)
        topic={'direction':'technology','context_excerpt':brief,
               'query':'logiciel rendez-vous clinique API documentation nouveautés',
               'source_categories':['official_documentation'],'reviewed':True,'review_reference':'human-review'}
        result=self.plan(saved,language='fr',semantic_topics=[topic])
        self.assertEqual(result['queries'][0]['query'],topic['query'])
        self.assertFalse(result['understanding']['clarification_questions'])
        self.assertFalse(result['execution_authorized'])
        for override in ({'reviewed':False},{'context_excerpt':'Unstated project objective'}):
            with self.assertRaises(ValueError):self.plan(saved,language='fr',semantic_topics=[{**topic,**override}])

    def test_queries_never_copy_private_identifiers_or_numeric_resources(self):
        saved=state('Secret Name', 'Goal: improve recipe generation. Contact secret@private.example. '
                    'Resources: budget 99999. Internal URL https://secret.example/key. '
                    'Do not share code, recipes or prompts.')
        plan=self.plan(saved)
        queries=' '.join(q['query'] for q in plan['queries']+plan['queued_topics'])
        for value in ('Secret Name','secret','private.example','99999','https:','prompts'):
            self.assertNotIn(value,queries)

    def test_clarified_need_adds_a_direction_without_rewriting_saved_input(self):
        saved=state('Idea','We have a small business and need help.')
        result=self.plan(saved,clarifications={'subject':'A bakery serving local families.',
                                             'outcome':'Reduce inventory waste.'})
        self.assertEqual(result['queries'][0]['domain'],'operations')
        self.assertEqual(result['project_context'][0]['text'],saved['project']['brief'])

    def test_strategy_retains_focus_answers_bounds_and_failed_reservations(self):
        saved=state(); result=self.plan(saved,research_focus='funding',max_queries=1)
        ledger=planning.create_strategy(saved,result,allowance={'queries':1,'results':5,'pages':4})
        self.assertIn('funding grants',ledger['proposals'][0]['query'])
        reserved=planning.reserve_search(saved,ledger,ledger['proposals'][0]['proposal_id'],attempt_id=str(uuid.uuid4()))
        self.assertEqual(reserved['remaining']['queries'],0)
        self.assertEqual(reserved['status'],'awaiting_reserved_search_outcome')
        again=planning.adapt_strategy(saved,reserved)
        self.assertEqual(again['reservations'],reserved['reservations'])
        self.assertFalse(again['execution_authorized'])

    def test_invalid_focus_answers_and_limits_fail(self):
        for options in ({'research_focus':'invented'}, {'research_focus':[]},
                        {'clarifications':{'authorize_external_request':'yes'}},
                        {'clarifications':{'subject':42}}, {'max_queries':3}):
            with self.assertRaises(ValueError):self.plan(**options)

    def test_decision_changes_refresh_priority_without_reservation_reset(self):
        saved=state();plan=self.plan(saved)
        ledger=planning.create_strategy(saved,plan,allowance={'queries':2,'results':10,'pages':4})
        aid=str(uuid.uuid4())
        ledger=planning.reserve_search(saved,ledger,ledger['proposals'][0]['proposal_id'],attempt_id=aid)
        ledger=planning.adapt_strategy(saved,ledger,feedback=[{
            'feedback_id':aid,'attempt_id':aid,'status':'completed','accounting_confirmed':True,
            'results_received':0,'pages_attempted':0,'sources':[]}])
        saved['decisions']=[{'id':'human','candidate_id':'old','version':1,'choice':'Defer',
                             'rationale':'Recipe product features need evidence.'}]
        refreshed=planning.adapt_strategy(saved,ledger)
        self.assertEqual(refreshed['remaining'],ledger['remaining'])
        self.assertEqual(refreshed['reservations'],ledger['reservations'])
        self.assertEqual(refreshed['proposals'][0]['direction'],'product')

    def test_clarification_blocks_execution_before_any_journal_write(self):
        from test_project_workflow import workflow
        saved=state('Idea','I have a small business and want help.')
        saved['operations']={}
        projects=workflow.Projects(Path(tempfile.gettempdir())/'unused-phase2f')
        from contextlib import nullcontext
        from types import SimpleNamespace
        store=SimpleNamespace(exclusive=nullcontext,save=lambda _:self.fail('Must not journal'))
        projects.searcher=lambda *a,**k:self.fail('Must not search')
        projects.fetcher=lambda *a,**k:self.fail('Must not fetch')
        projects.external_limits={'discover':2}
        with patch.object(projects,'store',return_value=store), patch.object(projects,'_read',return_value=saved):
            with self.assertRaisesRegex(ValueError,'clarification'):
                projects.act('project-synthetic','discover_adaptive',{
                    'request_id':str(uuid.uuid4()),'expected_version':15,
                    'authorize_external_request':True,'authorize_adaptive_queries':True,'research_focus':'marketing'})

    def test_clarification_answer_never_substitutes_for_external_consent(self):
        from test_project_workflow import workflow
        from contextlib import nullcontext
        from types import SimpleNamespace
        saved=state();saved['operations']={}
        store=SimpleNamespace(exclusive=nullcontext,save=lambda _:self.fail('Must not journal'))
        projects=workflow.Projects(Path(tempfile.gettempdir())/'unused-phase2f',
            searcher=lambda *a,**k:self.fail('Must not search'), fetcher=lambda *a,**k:self.fail('Must not fetch'),
            external_limits={'discover':2})
        with patch.object(projects,'store',return_value=store),patch.object(projects,'_read',return_value=saved):
            with self.assertRaisesRegex(ValueError,'authorization'):
                projects.act('project-synthetic','discover_adaptive',{
                    'request_id':str(uuid.uuid4()),'expected_version':15,
                    'clarifications':{'outcome':'Improve recipe generation.'}})

    def test_new_project_fields_invalidate_existing_strategy_scope(self):
        saved=state();plan=self.plan(saved)
        ledger=planning.create_strategy(saved,plan,allowance={'queries':2,'results':10,'pages':4})
        changed=copy.deepcopy(saved);changed['project']['needs']='Improve recipe API validation.'
        with self.assertRaisesRegex(ValueError,'context changed'):
            planning.adapt_strategy(changed,ledger)


class PreviewIntegrationTests(OfflineTests):
    def test_existing_post_contract_preview_is_read_only_and_requires_no_authorization(self):
        from test_project_workflow import app, workflow, dispatch
        saved=state();saved['version']=15
        projects=workflow.Projects(Path(tempfile.gettempdir())/'unused-phase2f')
        with patch.object(projects,'read',return_value=copy.deepcopy(saved)) as read, \
             patch.object(workflow.discovery.Store,'save',side_effect=AssertionError('Preview must not write')):
            result=projects.act('project-synthetic','research_plan',{'expected_version':15})
            self.assertEqual(result['project_version'],15)
            self.assertFalse(result['execution_authorized'])
            for body in ({'expected_version':14}, {'expected_version':15,'authorize_external_request':True}):
                with self.assertRaises(ValueError):projects.act('project-synthetic','research_plan',body)
            backend=app.State(memory_root=Path(tempfile.gettempdir())/'unused-phase2f',project_services={})
            backend.projects=projects
            path='/api/projects/project-synthetic/research_plan'
            self.assertEqual(dispatch(backend,path,'POST',{'expected_version':15},authenticated=False)[0],401)
            self.assertEqual(dispatch(backend,path,'POST',{'expected_version':15},origin=False)[0],403)
            code,preview=dispatch(backend,path,'POST',{'expected_version':15})
            self.assertEqual(code,200)
            self.assertFalse(preview['execution_authorized'])
