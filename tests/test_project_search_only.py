"""Search-only isolation with synthetic wire responses and temporary H-MEM only."""
import copy
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import project_adapters as adapters
import project_discovery_run as runner
import project_workflow as workflow
import nextwise_app as app
from test_project_workflow import dispatch, hashes

ENV = {'NEXTWISE_PROJECT_PROVIDERS_ENABLED':'true', 'NEXTWISE_PROJECT_SEARCH_ENABLED':'true',
       'NEXTWISE_PROJECT_ASSESSMENT_ENABLED':'false', 'NEXTWISE_PROJECT_SEARCH_LIMIT':'2'}
PAGE = b'<main><p>The service supports public appointment booking and scheduling for independent clinics.</p></main>'


class OfflineCase(unittest.TestCase):
    def setUp(self):
        env={k:v for k,v in os.environ.items() if not k.startswith(('NEXTWISE_','TAVILY_'))}
        guard=patch.dict(os.environ,env,clear=True);guard.start();self.addCleanup(guard.stop)
        guard=patch('socket.socket',side_effect=AssertionError('No sockets permitted'))
        guard.start();self.addCleanup(guard.stop)
        guard=patch.object(adapters.analyzer,'request_claims',side_effect=AssertionError('No inference permitted'))
        self.model=guard.start();self.addCleanup(guard.stop)
        guard=patch.object(adapters.config,'secret',side_effect=AssertionError('No credentials permitted'))
        self.secret=guard.start();self.addCleanup(guard.stop)


class IsolationTests(OfflineCase):
    def test_master_gate_and_legacy_defaults_are_preserved(self):
        self.assertEqual(adapters.configured_services(),{})
        with patch.dict(os.environ,{'NEXTWISE_PROJECT_SEARCH_ENABLED':'true',
                                    'NEXTWISE_PROJECT_ASSESSMENT_ENABLED':'true'}):
            self.assertEqual(adapters.configured_services(),{})
        with patch.dict(os.environ,{'NEXTWISE_PROJECT_PROVIDERS_ENABLED':'true'}):
            services=adapters.configured_services()
            self.assertTrue(callable(services['searcher']))
            self.assertTrue(callable(services['assessor']))
            self.assertFalse(services['search_only'])
            self.assertEqual(services['external_limits'],{'discover':2,'assess':4})
        self.secret.assert_not_called();self.model.assert_not_called()

    def test_independent_assessment_only_and_search_only_wiring(self):
        with patch.dict(os.environ,ENV):
            services=adapters.configured_services()
            self.assertTrue(callable(services['searcher']));self.assertTrue(callable(services['fetcher']))
            self.assertIsNone(services['assessor']);self.assertTrue(services['search_only'])
            self.assertEqual(services['external_limits'],{'discover':2})
        with patch.dict(os.environ,{**ENV,'NEXTWISE_PROJECT_SEARCH_ENABLED':'false',
                                    'NEXTWISE_PROJECT_ASSESSMENT_ENABLED':'true'}):
            services=adapters.configured_services()
            self.assertIsNone(services['searcher']);self.assertIsNone(services['fetcher'])
            self.assertTrue(callable(services['assessor']))
            self.assertEqual(services['external_limits'],{'assess':4})
        with patch.dict(os.environ,{**ENV,'NEXTWISE_PROJECT_SEARCH_ENABLED':'false'}):
            self.assertEqual(adapters.configured_services(),{})
        self.secret.assert_not_called();self.model.assert_not_called()

    def test_disabled_assessment_adapter_fails_before_contract_or_credentials(self):
        with patch.dict(os.environ,ENV), patch.object(adapters.output,'messages') as messages:
            with self.assertRaisesRegex(adapters.config.ConfigError,'assessment is disabled'):
                adapters.assess({})
            messages.assert_not_called()
        self.secret.assert_not_called();self.model.assert_not_called()

    def test_search_only_rejects_assessment_injection_and_ignores_disabled_model_limits(self):
        with self.assertRaisesRegex(ValueError,'assessment transport'):
            workflow.Projects('unused',search_only=True,assessor=lambda _:None)
        with self.assertRaisesRegex(ValueError,'assessment transport'):
            workflow.Projects('unused',search_only=True,external_limits={'assess':1})
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,
                {**ENV,'NEXTWISE_PROJECT_ASSESSMENT_LIMIT':'invalid-disabled-value'}):
            state=app.State(tmp,project_services={'assessor':lambda _:self.fail('Injected inference'),
                                                'external_limits':{'assess':99}})
            self.assertTrue(state.project_only);self.assertIsNone(state.projects.assessor)
            self.assertNotIn('assess',state.projects.external_limits)
            self.assertNotIn('assess',adapters.configured_services()['external_limits'])

    def test_search_only_automatically_blocks_pilot_endpoints(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,ENV):
            state=app.State(tmp)
            self.assertTrue(state.project_only)
            for path in ('/api/discovery','/api/report','/api/opportunities'):
                self.assertEqual(dispatch(state,path)[0],404)
            for path in ('/api/load','/api/discovery/check','/api/discovery/select',
                         '/api/discovery/recommend','/api/discovery/decision'):
                self.assertEqual(dispatch(state,path,'POST',{})[0],404)
            self.assertEqual(dispatch(state,'/api/projects')[1]['transports'],{'search':True,'assessment':False})
            self.assertFalse((Path(tmp)/'projects').exists())
        self.secret.assert_not_called();self.model.assert_not_called()

    def test_startup_without_projects_flag_uses_only_project_checks_and_no_service_is_started(self):
        with patch.dict(os.environ,ENV), \
             patch('runtime_health.check_dependencies',return_value={'ready':True}) as health, \
             patch.object(app,'LocalHTTPServer') as server,patch.object(app.getpass,'getpass') as prompt, \
             patch.object(app,'make_handler',wraps=app.make_handler) as handler, \
             patch('sys.stdout',new_callable=io.StringIO):
            server.return_value.serve_forever.side_effect=KeyboardInterrupt
            self.assertEqual(app.main([]),0)
            self.assertTrue(health.call_args.kwargs['project_only'])
            self.assertTrue(handler.call_args.args[0].project_only)
            prompt.assert_not_called();self.secret.assert_not_called();self.model.assert_not_called()

    def test_search_only_readiness_never_checks_model_or_pilot_dependencies(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,ENV), \
             patch('runtime_health.check_dependencies',return_value={'ready':True}) as health:
            state=app.State(tmp)
            self.assertEqual(dispatch(state,'/health/ready')[0],200)
            self.assertTrue(health.call_args.kwargs['project_only'])
            self.assertNotIn('network',health.call_args.kwargs)
            self.secret.assert_not_called();self.model.assert_not_called()

    def test_search_only_cannot_resume_a_broader_legacy_run_or_dispatch_assessments(self):
        from contextlib import nullcontext
        projects=workflow.Projects('unused',search_only=True,external_limits={'discover':2},
            searcher=lambda *a,**k:self.fail('Must not search'),fetcher=lambda _:self.fail('Must not fetch'))
        saved={'project':{'id':'project-synthetic'},'version':1,'operations':{},
               'adaptive_discovery_runs':{'legacy':{'strategy':{'reservations':[],'feedback':[],
                    'allowance':{'queries':2,'results':10,'pages':4}}}}}
        store=SimpleNamespace(exclusive=nullcontext,save=lambda _:self.fail('Must not write'))
        with patch.object(projects,'store',return_value=store),patch.object(projects,'_read',return_value=saved):
            with self.assertRaisesRegex(ValueError,'exceeds search-only bounds'):
                projects.act('project-synthetic','discover_adaptive',{
                    'request_id':str(uuid.uuid4()),'expected_version':1,'run_id':'legacy',
                    'authorize_external_request':True,'authorize_adaptive_queries':True})
            # The policy still rejects actions if an internal stale reference is restored.
            projects.assessor=lambda _:self.fail('Stale model callback')
            for action in ('assess','assess_opportunities'):
                with self.assertRaisesRegex(ValueError,'disabled in search-only mode'):
                    projects.act('project-synthetic',action,{})


class SearchOnlyExecutionTests(OfflineCase):
    def setUp(self):
        super().setUp()
        temp=tempfile.TemporaryDirectory(prefix='nextwise-search-only-offline-');self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)/'memory'
        guard=patch.dict(os.environ,ENV);guard.start();self.addCleanup(guard.stop)
        self.results=[];self.wire_error=None;self.payloads=[]
        def secret(name,**options):
            if name!='TAVILY_API_KEY':raise AssertionError('Model credential requested')
            return 'SYNTHETIC_SEARCH_KEY'
        self.secret.side_effect=secret
        guard=patch.object(adapters.tavily,'build_opener',return_value=SimpleNamespace(open=self.open_wire))
        guard.start();self.addCleanup(guard.stop)
        guard=patch.object(adapters.tavily,'public_page',return_value={'raw':PAGE})
        self.pages=guard.start();self.addCleanup(guard.stop)
        actual_bridge=workflow.discovery.memory.call_bridge
        def bridge(request):
            self.assertTrue(Path(request['memory_root']).resolve().is_relative_to(self.root.resolve()))
            return actual_bridge(request)
        guard=patch.object(workflow.discovery.memory,'call_bridge',side_effect=bridge)
        guard.start();self.addCleanup(guard.stop)
        self.backend=app.State(self.root);self.projects=self.backend.projects
        saved=self.projects.create({'request_id':str(uuid.uuid4()),'name':'Clinic',
            'brief':'Goal: improve appointment booking for our clinic. Team size: 1.', 'reviewed_sanitized':True})
        self.pid=saved['project']['id']

    def open_wire(self,request,timeout):
        self.assertEqual(request.full_url,'https://api.tavily.com/search')
        self.payloads.append(json.loads(request.data))
        if self.wire_error:raise self.wire_error
        return io.BytesIO(json.dumps({'results':self.results,'usage':{'credits':1}}).encode())

    def body(self,**fields):
        return {'request_id':str(uuid.uuid4()),'expected_version':self.projects.read(self.pid)['version'],
                'authorize_external_request':True,'authorize_adaptive_queries':True,**fields}

    def test_ceiling_increase_preserves_consumed_reservation_and_dispatches_only_one_basic_search(self):
        with patch.dict(os.environ,{'NEXTWISE_PROJECT_SEARCH_LIMIT':'1'}):
            old=app.State(self.root).projects
            initial=old.read(self.pid)
            saved=old.act(self.pid,'discover',{'request_id':str(uuid.uuid4()),'expected_version':initial['version'],
                'query':'public clinic appointment scheduling documentation','authorize_external_request':True})
            with self.assertRaisesRegex(ValueError,'cumulative search limit'):
                old.act(self.pid,'discover_adaptive',self.body())
        before=hashes(self.root);old_operations=copy.deepcopy(saved['operations'])
        self.projects=app.State(self.root).projects
        self.assertEqual(before,hashes(self.root))
        self.assertEqual(runner.search_attempts(self.projects.read(self.pid)),1)
        self.payloads.clear()
        self.results=[{'title':'Public documentation','url':f'https://source-{i}.example/docs'} for i in range(5)]
        body=self.body();result=self.projects.act(self.pid,'discover_adaptive',body)
        self.assertEqual(len(self.payloads),1);self.assertEqual(self.pages.call_count,4)
        payload=self.payloads[0]
        self.assertEqual(payload['search_depth'],'basic');self.assertEqual(payload['max_results'],5)
        self.assertFalse(payload['auto_parameters']);self.assertFalse(payload['include_answer'])
        job=next(iter(result['adaptive_discovery_runs'].values()))
        self.assertEqual(job['strategy']['allowance'],{'queries':1,'results':5,'pages':4})
        self.assertEqual(len(job['strategy']['reservations']),1)
        self.assertEqual(runner.search_attempts(result),2)
        self.assertTrue(all(result['operations'][key]==value for key,value in old_operations.items()))
        self.assertEqual(result['assessments'],[]);self.assertEqual(result['briefings'],[])
        replay=app.State(self.root).projects.act(self.pid,'discover_adaptive',body)
        self.assertEqual(replay['adaptive_discovery_runs'],result['adaptive_discovery_runs'])
        with self.assertRaises(ValueError):self.projects.act(self.pid,'discover_adaptive',self.body())
        self.assertEqual(len(self.payloads),1);self.model.assert_not_called()

    def test_over_limit_requests_and_missing_consent_do_not_reserve_or_dispatch(self):
        before=hashes(self.root)
        for fields in ({'limits':{'max_queries':2}},{'limits':{'max_queries':True}},
                       {'limits':{'results_per_query':6}},{'limits':{'max_source_pages':5}},
                       {'authorize_external_request':False},{'authorize_adaptive_queries':False}):
            with self.subTest(fields=fields),self.assertRaises(ValueError):
                self.projects.act(self.pid,'discover_adaptive',self.body(**fields))
        self.assertEqual(before,hashes(self.root));self.assertEqual(self.payloads,[])
        plan=self.projects.act(self.pid,'research_plan',{'expected_version':self.projects.read(self.pid)['version']})
        self.assertEqual(plan['limits']['max_queries'],1)
        with self.assertRaises(ValueError):self.projects.act(self.pid,'research_plan',{
            'expected_version':plan['project_version'],'limits':{'max_queries':2}})
        self.secret.assert_not_called();self.model.assert_not_called()

    def test_project_assessment_endpoints_are_blocked_without_changing_history(self):
        before=hashes(self.root)
        for action in ('assess','assess_opportunities'):
            body=self.body(candidate_id='source',authorize_opportunity_assessments=True)
            code,_=dispatch(self.backend,f'/api/projects/{self.pid}/{action}','POST',body)
            self.assertEqual(code,409)
        self.assertEqual(before,hashes(self.root));self.secret.assert_not_called();self.model.assert_not_called()

    def test_empty_results_cannot_trigger_a_second_query_or_model_fallback(self):
        saved=self.projects.act(self.pid,'discover_adaptive',self.body())
        self.assertEqual(len(self.payloads),1);self.pages.assert_not_called();self.model.assert_not_called()
        job=next(iter(saved['adaptive_discovery_runs'].values()))
        self.assertEqual(job['outcome'],'budget_exhausted')
        self.assertEqual(job['strategy']['remaining']['queries'],0)

    def test_search_failure_is_consumed_without_retries_or_model_fallback(self):
        self.wire_error=TimeoutError('Synthetic timeout')
        body=self.body()
        with self.assertRaises(ValueError):self.projects.act(self.pid,'discover_adaptive',body)
        restarted=app.State(self.root).projects
        with self.assertRaises(ValueError):restarted.act(self.pid,'discover_adaptive',body)
        saved=restarted.read(self.pid)
        self.assertEqual(runner.search_attempts(saved),1)
        self.assertEqual(len(self.payloads),1);self.pages.assert_not_called();self.model.assert_not_called()

    def test_interrupted_search_recovers_without_redispatch_or_restoring_allowance(self):
        self.wire_error=KeyboardInterrupt()
        body=self.body()
        with self.assertRaises(KeyboardInterrupt):self.projects.act(self.pid,'discover_adaptive',body)
        saved=app.State(self.root).projects.act(self.pid,'discover_adaptive',body)
        self.assertEqual(runner.search_attempts(saved),1)
        self.assertEqual(len(self.payloads),1);self.model.assert_not_called()
        job=next(iter(saved['adaptive_discovery_runs'].values()))
        self.assertEqual(job['status'],'interrupted')
        with self.assertRaises(ValueError):self.projects.act(self.pid,'discover_adaptive',self.body(run_id=job['id']))
        self.assertEqual(len(self.payloads),1)
