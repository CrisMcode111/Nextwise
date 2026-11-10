"""Offline orchestration integration: injected transports, real temporary H-MEM."""
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import uuid

from test_project_workflow import app, workflow, dispatch
import project_discovery_run as runner
import project_opportunities as planning
import project_adapters as adapters

PAGE = b'<main><p>The service provides public appointment booking and scheduling for independent clinics.</p></main>'
URL = 'https://example.com/appointments'


class AdaptiveDiscoveryIntegrationTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='nextwise-adaptive-offline-')
        self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)/'memory'
        self.search_calls=[]; self.page_calls=[]
        self.results=[{'title':'Appointment service','url':URL,'content':'UNTRUSTED SEARCH SNIPPET'}]
        self.search_effect=None; self.page_effect=None
        for name in ('socket.socket','tavily_discovery.search','tavily_discovery.public_page',
                     'project_adapters.config.secret','semantic_discovery.analyzer.request_claims'):
            guard=patch(name,side_effect=AssertionError('External operation forbidden'))
            guard.start(); self.addCleanup(guard.stop)
        actual_bridge=app.memory.call_bridge
        def bridge(request):
            self.assertTrue(Path(request['memory_root']).resolve().is_relative_to(self.root.resolve()))
            return actual_bridge(request)
        guard=patch.object(app.memory,'call_bridge',side_effect=bridge)
        guard.start(); self.addCleanup(guard.stop)
        self.services={'searcher':self.search,'fetcher':self.fetch,
                       'external_limits':{'discover':2,'assess':2}}
        self.projects=workflow.Projects(self.root,**self.services)
        self.saved=self.projects.create({'request_id':str(uuid.uuid4()),'name':'Clinic',
            'brief':'Goal: improve booking and repetitive manual administration for our clinic.',
            'reviewed_sanitized':True})
        self.pid=self.saved['project']['id']

    def search(self,query,*,max_results=5):
        self.search_calls.append((query,max_results))
        if self.search_effect:return self.search_effect(query,max_results)
        return copy.deepcopy(self.results[:max_results])

    def fetch(self,url):
        self.page_calls.append(url)
        if self.page_effect:return self.page_effect(url)
        return {'raw':PAGE,'error':None}

    def body(self,**fields):
        return {'request_id':str(uuid.uuid4()),'expected_version':self.projects.read(self.pid)['version'],
                'authorize_external_request':True,'authorize_adaptive_queries':True,**fields}

    def act(self,body=None):
        return self.projects.act(self.pid,'discover_adaptive',body or self.body())

    def job(self,saved):
        return next(iter(saved['adaptive_discovery_runs'].values()))

    def test_success_persists_evidence_and_reopens_without_assessment_or_selection(self):
        def verify_search(query,limit):
            disk=self.projects.store(self.pid).read(); job=self.job(disk)
            attempt=job['strategy']['reservations'][-1]['attempt_id']
            self.assertEqual(job['attempts'][attempt]['stage'],'search_reserved')
            self.assertEqual(disk['operations'][attempt]['status'],'started')
            return self.results
        def verify_page(url):
            disk=self.projects.store(self.pid).read(); job=self.job(disk)
            self.assertEqual(next(iter(job['attempts'].values()))['pages'][-1]['stage'],'reserved')
            return {'raw':PAGE}
        self.search_effect=verify_search; self.page_effect=verify_page
        saved=self.act(); job=self.job(saved)
        self.assertEqual(job['outcome'],'needs_assessment')
        self.assertEqual(len(self.search_calls),1); self.assertEqual(len(self.page_calls),1)
        self.assertEqual(saved['assessments'],[]); self.assertEqual(saved['briefings'],[]); self.assertEqual(saved['decisions'],[])
        item=next(iter(saved['items'].values()))
        self.assertEqual(item['raw_sha256'],workflow.discovery.sha(PAGE))
        self.assertEqual((self.projects.store(self.pid).directory/item['snapshot_path']).read_bytes(),PAGE)
        self.assertNotIn('UNTRUSTED SEARCH SNIPPET',workflow.json_dumps(saved))
        disabled=workflow.Projects(self.root)
        self.assertEqual(disabled.read(self.pid)['adaptive_discovery_runs'],saved['adaptive_discovery_runs'])

    def test_weak_results_adapt_queries_and_exhaust_cumulative_query_limit(self):
        self.results=[]
        saved=self.act(); job=self.job(saved)
        self.assertEqual(len(self.search_calls),2)
        self.assertNotEqual(self.search_calls[0][0],self.search_calls[1][0])
        self.assertEqual(job['outcome'],'budget_exhausted')
        self.assertEqual(job['strategy']['remaining']['queries'],0)
        self.assertEqual(len(job['strategy']['feedback']),2)
        self.assertEqual(self.page_calls,[])
        with self.assertRaises(workflow.WorkflowError):self.act(self.body(run_id=job['id']))
        with self.assertRaises(workflow.WorkflowError):self.act()
        self.assertEqual(len(self.search_calls),2)

    def test_duplicates_are_compared_and_same_url_is_not_refetched(self):
        original=self.projects.act(self.pid,'discover',{'request_id':str(uuid.uuid4()),
            'expected_version':self.saved['version'],'authorize_external_request':True,'query':'public clinic scheduling product documentation'})
        self.projects.external_limits['discover']=3
        old=copy.deepcopy(original['items']); self.page_calls.clear(); self.search_calls.clear()
        self.results=[{'url':URL,'title':'Duplicate'}, {'url':URL,'title':'Duplicate again'}]
        saved=self.act(); job=self.job(saved)
        self.assertEqual(len(self.search_calls),2)
        self.assertEqual(len(self.page_calls),1)
        self.assertEqual(saved['items'],old)
        self.assertTrue(all(e['outcome']=='weak' for e in job['strategy']['evaluations']))
        self.assertGreaterEqual(job['strategy']['evaluations'][0]['counts']['duplicates'],1)
        self.assertEqual(len(saved['discovery_evidence_history']),2)

    def test_query_result_and_page_caps_reach_actual_injected_transports(self):
        self.results=[{'url':URL+str(i),'title':'Source'} for i in range(5)]
        saved=self.act(self.body(limits={'max_queries':1,'results_per_query':2,'max_source_pages':1}))
        self.assertEqual(self.search_calls[0][1],2)
        self.assertEqual(len(self.search_calls),1); self.assertEqual(len(self.page_calls),1)
        self.assertEqual(self.job(saved)['strategy']['remaining'],{'queries':0,'results':0,'pages':0})

    def test_default_disabled_missing_approval_and_stale_versions_never_dispatch(self):
        disabled=workflow.Projects(self.root)
        with self.assertRaises(workflow.WorkflowError):disabled.act(self.pid,'discover_adaptive',self.body())
        for fields in ({'authorize_external_request':False},{'authorize_adaptive_queries':False},
                       {'expected_version':-1},{'limits':{'max_queries':3}}):
            with self.assertRaises(workflow.WorkflowError):self.act(self.body(**fields))
        self.assertEqual(self.search_calls,[]); self.assertEqual(self.page_calls,[])
        self.assertNotIn('adaptive_discovery_runs',self.projects.read(self.pid))

    def test_failed_search_reservation_survives_restart_and_cannot_replay(self):
        def fail(*args):raise RuntimeError('synthetic transport diagnostic must not persist')
        self.search_effect=fail; body=self.body()
        with self.assertRaises(workflow.WorkflowError):self.act(body)
        reopened=workflow.Projects(self.root,**self.services).read(self.pid); job=self.job(reopened)
        self.assertEqual(job['status'],'failed')
        self.assertEqual(len(job['strategy']['reservations']),1)
        self.assertFalse(job['strategy']['feedback'][0]['accounting_confirmed'])
        self.assertNotIn('synthetic transport diagnostic',workflow.json_dumps(reopened))
        with self.assertRaises(workflow.WorkflowError):self.act(body)
        self.assertEqual(len(self.search_calls),1)

    def test_interrupted_search_recovers_without_redispatch_even_with_disabled_transports(self):
        def interrupt(*args):raise KeyboardInterrupt()
        self.search_effect=interrupt; body=self.body()
        with self.assertRaises(KeyboardInterrupt):self.act(body)
        restarted=workflow.Projects(self.root)
        before=restarted.read(self.pid); self.assertEqual(self.job(before)['status'],'running')
        recovered=restarted.act(self.pid,'discover_adaptive',body)
        self.assertEqual(self.job(recovered)['status'],'interrupted')
        self.assertEqual(self.job(recovered)['strategy']['remaining']['queries'],1)
        self.assertEqual(len(self.search_calls),1)
        with self.assertRaises(workflow.WorkflowError):restarted.act(self.pid,'discover_adaptive',body)

    def test_interrupted_page_remains_consumed_and_is_not_refetched(self):
        def interrupt(url):raise KeyboardInterrupt()
        self.page_effect=interrupt; body=self.body()
        with self.assertRaises(KeyboardInterrupt):self.act(body)
        restarted=workflow.Projects(self.root,**self.services)
        recovered=restarted.act(self.pid,'discover_adaptive',body); job=self.job(recovered)
        self.assertEqual(len(next(iter(job['attempts'].values()))['pages']),1)
        self.assertEqual(job['strategy']['remaining']['pages'],0)
        self.assertEqual(len(self.search_calls),1); self.assertEqual(len(self.page_calls),1)

    def test_unconfirmed_reservation_save_stops_before_any_dispatch(self):
        real_save=workflow.discovery.Store.save; calls=[]
        def fail_after_reservation(store,saved):
            result=real_save(store,saved); calls.append(1)
            if len(calls)==2:raise OSError('synthetic readback failure')
            return result
        with patch.object(workflow.discovery.Store,'save',fail_after_reservation):
            with self.assertRaises(workflow.WorkflowError):self.act()
        job=self.job(self.projects.read(self.pid))
        self.assertEqual(len(job['strategy']['reservations']),1)
        self.assertEqual(self.search_calls,[]); self.assertEqual(self.page_calls,[])
        self.assertEqual(job['strategy']['remaining']['queries'],1)

    def test_page_failures_are_consumed_and_do_not_retry_the_same_url(self):
        self.results=[{'url':URL,'title':'Unavailable'}]
        self.page_effect=lambda url:{'error':'unavailable','raw':b''}
        saved=self.act(); job=self.job(saved)
        self.assertEqual(len(self.page_calls),1)
        self.assertEqual(len(self.search_calls),2)
        self.assertEqual(job['strategy']['remaining']['pages'],3)
        self.assertEqual(saved['items'],{})

    def test_legacy_search_and_adaptive_search_share_the_project_lifetime_limit(self):
        self.results=[]; saved=self.act()
        body={'request_id':str(uuid.uuid4()),'expected_version':saved['version'],
              'authorize_external_request':True,'query':'public scheduling documentation'}
        with self.assertRaises(workflow.WorkflowError):self.projects.act(self.pid,'discover',body)
        self.assertEqual(len(self.search_calls),2)

    def test_successful_request_replay_never_dispatches_again(self):
        body=self.body(); saved=self.act(body)
        self.assertEqual(self.act(body),saved)
        self.assertEqual(len(self.search_calls),1)
        with self.assertRaises(workflow.WorkflowError):self.act({**body,'authorize_adaptive_queries':False})

    def test_existing_projects_api_routes_and_session_origin_guards_apply(self):
        backend=app.State(self.root,project_services=self.services); backend.project_only=True
        body=self.body(); path='/api/projects/'+self.pid+'/discover_adaptive'
        self.assertEqual(dispatch(backend,path,'POST',body,authenticated=False)[0],401)
        self.assertEqual(dispatch(backend,path,'POST',body,origin=False)[0],403)
        self.assertEqual(self.search_calls,[])
        code,saved=dispatch(backend,path,'POST',body)
        self.assertEqual(code,200)
        code,reopened=dispatch(app.State(self.root),'/api/projects/'+self.pid)
        self.assertEqual(code,200)
        self.assertEqual(reopened['adaptive_discovery_runs'],saved['adaptive_discovery_runs'])

    def test_explicit_restart_continuation_uses_only_unspent_capacity(self):
        self.results=[]; body=self.body(); real_save=workflow.discovery.Store.save; interrupted=[]
        def stop_after_feedback(store,saved):
            result=real_save(store,saved)
            jobs=saved.get('adaptive_discovery_runs',{})
            if jobs and len(self.job(saved)['strategy']['feedback'])==1 and not interrupted:
                interrupted.append(True)
                raise KeyboardInterrupt()
            return result
        with patch.object(workflow.discovery.Store,'save',stop_after_feedback):
            with self.assertRaises(KeyboardInterrupt):self.act(body)
        self.assertEqual(len(self.search_calls),1)
        self.projects=workflow.Projects(self.root,**self.services)
        saved=self.act(self.body(run_id=body['request_id']))
        self.assertEqual(len(self.search_calls),2)
        self.assertNotEqual(self.search_calls[0][0],self.search_calls[1][0])
        self.assertEqual(len(self.job(saved)['strategy']['reservations']),2)
        self.assertEqual(saved['operations'][body['request_id']]['status'],'failed')
        with self.assertRaises(workflow.WorkflowError):self.act(self.body(run_id=body['request_id'],limits={'max_queries':2}))

    def test_historical_human_decision_and_evidence_remain_unchanged(self):
        old=self.projects.act(self.pid,'discover',{'request_id':str(uuid.uuid4()),
            'expected_version':self.saved['version'],'authorize_external_request':True,'query':'clinic public booking documentation'})
        cid=next(iter(old['items'])); self.projects.external_limits['discover']=3
        brief=workflow.opportunities.seal({'id':'historical-brief','candidate_id':cid,'project_id':self.pid,
            'assessment_id':'historical-assessment','version':1,'previous_record_sha256':None,
            'evidence_references':copy.deepcopy(old['items'][cid])})
        decision=workflow.opportunities.seal({'id':'historical-decision','candidate_id':cid,'project_id':self.pid,
            'briefing_id':brief['id'],'briefing_sha256':brief['record_sha256'],'choice':'Defer',
            'rationale':'Defer until clinic scheduling suitability is established.','version':1,
            'previous_record_sha256':None})
        old['briefings']=[brief]; old['decisions']=[decision]; self.projects.store(self.pid).save(old)
        snapshot=self.projects.store(self.pid).directory/old['items'][cid]['snapshot_path']
        self.page_calls.clear(); saved=self.act()
        self.assertEqual(saved['briefings'],[brief]); self.assertEqual(saved['decisions'],[decision])
        self.assertEqual(saved['items'],old['items']); self.assertEqual(snapshot.read_bytes(),PAGE)
        self.assertEqual(self.page_calls,[])

    def test_material_update_compares_saved_snapshots_without_rewriting_old_evidence(self):
        old=self.projects.act(self.pid,'discover',{'request_id':str(uuid.uuid4()),
            'expected_version':self.saved['version'],'authorize_external_request':True,'query':'clinic public booking documentation'})
        cid=next(iter(old['items'])); original=copy.deepcopy(old['items'][cid])
        new_raw=PAGE.replace(b'</p>',b' It provides inventory planning and supplier delivery scheduling.</p>')
        self.page_effect=lambda url:{'raw':new_raw}; saved=self.act()
        comparison=next(iter(self.job(saved)['attempts'].values()))['sources'][0]['comparison']
        self.assertEqual(comparison['classification'],'materially_updated')
        self.assertEqual((self.projects.store(self.pid).directory/original['snapshot_path']).read_bytes(),PAGE)
        self.assertNotEqual(saved['items'][cid]['snapshot_path'],original['snapshot_path'])
        self.assertIn(original,saved['discovery_evidence_history'])


class BoundedAdapterTests(unittest.TestCase):
    def test_smaller_result_limit_reaches_tavily_payload_and_rejects_over_limit_response(self):
        class Response:
            def __init__(self,count):self.stream=io.BytesIO(json.dumps({'results':[{'url':URL}]*count}).encode())
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read1(self,n):return self.stream.read(n)
        with patch('socket.socket',side_effect=AssertionError('No network')), \
             patch.object(workflow.tavily,'build_opener') as opener:
            opener.return_value.open.return_value=Response(1)
            self.assertEqual(len(workflow.tavily.search('clinic booking documents','synthetic-key',max_results=1)),1)
            payload=json.loads(opener.return_value.open.call_args.args[0].data)
            self.assertEqual(payload['max_results'],1)
            opener.return_value.open.return_value=Response(2)
            with self.assertRaises(workflow.tavily.SearchUnavailable):
                workflow.tavily.search('clinic booking documents','synthetic-key',max_results=1)

    def test_project_adapter_forwards_bounded_cap_and_validates_before_secret_lookup(self):
        with patch.object(adapters.config,'secret',return_value='synthetic-key') as secret, \
             patch.object(adapters.tavily,'search',return_value=[]) as search:
            adapters.search('clinic scheduling documents',max_results=2)
            search.assert_called_once_with('clinic scheduling documents','synthetic-key',max_results=2)
            secret.reset_mock()
            with self.assertRaises(ValueError):adapters.search('clinic scheduling documents',max_results=True)
            secret.assert_not_called()


if __name__=='__main__':
    unittest.main()
