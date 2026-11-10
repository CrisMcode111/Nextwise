"""Offline selection integration with injected wire output and real temp H-MEM."""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid

from test_project_workflow import workflow, app, dispatch, mocked_assessment
import opportunity_assessment as contract
import project_assessment_output as output
import project_adapters as adapters

PAGE=b'<main><p>PolicyHelp answers customer questions using published clinic hours and appointment policies.</p></main>'
BRIEF='Goal: Clinic needs answers to customer questions using its public appointment policies. Goal: improve booking support. Team size: 1. Environment: Windows 11, 16 GB RAM.'


def wire(request):
    value=json.loads(mocked_assessment(request))['assessments'][0]
    del value['source_observation'], value['evidence']
    claim=request['staged_plan']['claims'][0]['passage_id']
    value.update(observation_claim_id=claim,evidence_claim_ids=[claim],missing_information=list(output.UNKNOWNS))
    value['opportunity_details']={'impact_domain':'productivity','evidence_quality':'publisher_claims_only',
        'improvement_mechanism':{'explanation':'Using published policies could help Clinic draft answers for human review.',
            'project_quote':'Clinic needs answers to customer questions using its public appointment policies.',
            'evidence_claim_ids':[claim]},
        'feasibility':{'status':'plausible_for_bounded_review','rationale':'A public evidence review appears plausible before any integration.',
            'resource_fit':'plausible_for_bounded_review','resource_rationale':'The stated team could review an invented question before a trial.',
            'resource_quotes':['Team size: 1'],'conditions':['Review public documentation without sharing private customer data.'],
            'blocking_unknowns':[]}}
    return value


class SelectionIntegrationTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix='nextwise-selection-offline-'); self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)/'memory'; self.calls=[]; self.effects={}
        for name in ('socket.socket','tavily_discovery.search','tavily_discovery.public_page',
                     'project_adapters.config.secret','semantic_discovery.analyzer.request_claims'):
            guard=patch(name,side_effect=AssertionError('No external operations permitted'))
            guard.start(); self.addCleanup(guard.stop)
        bridge=app.memory.call_bridge
        def local_bridge(request):
            self.assertTrue(Path(request['memory_root']).resolve().is_relative_to(self.root.resolve()))
            return bridge(request)
        guard=patch.object(app.memory,'call_bridge',side_effect=local_bridge); guard.start(); self.addCleanup(guard.stop)
        self.services={'assessor':self.model,'external_limits':{'assess':2}}
        self.projects=workflow.Projects(self.root,**self.services)
        saved=self.projects.create({'request_id':str(uuid.uuid4()),'name':'Clinic','brief':BRIEF,'reviewed_sanitized':True})
        self.pid=saved['project']['id']; self.cid=self.add_source()

    def add_source(self,suffix='policy',raw=PAGE):
        store=self.projects.store(self.pid); state=store.read(); url='https://'+suffix+'.example/docs'
        cid=workflow.discovery.collector.stable_source_id(url)
        path=store.directory/'runs'/('fixture-'+suffix)/'source.html'; path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(raw)
        text=workflow.semantic.html_extract.extract_readable_text(raw.decode())
        state['items'][cid]={'id':cid,'title':suffix,'url':url,'snapshot_path':str(path.relative_to(store.directory)).replace('\\','/'),
            'raw_sha256':workflow.discovery.sha(raw),'content_sha256':workflow.discovery.sha(text),'source':'tavily-page',
            'kind':'saved_page','publication_date':None,'retrieved_at':'2026-01-01T00:00:00Z'}
        store.save(state); return cid

    def model(self,request):
        self.calls.append(copy.deepcopy(request))
        disk=self.projects.store(self.pid).read()
        self.assertGreaterEqual(sum(o['action']=='assess' for o in disk['operations'].values()),len(self.calls))
        self.assertTrue(any(o['action']=='assess' and o['status']=='started' for o in disk['operations'].values()))
        value=wire(request)
        effect=self.effects.get(request['prepared']['source']['candidate_id'])
        if callable(effect):value=effect(value)
        elif effect:
            value['category']=effect
            if effect!='potential relevance':
                value['application_hypothesis']=None; value['priority']='low'
                if effect=='uncertain relevance':value['project_need_id']='uncertain'
        return json.dumps({'assessments':[value]},ensure_ascii=False)

    def body(self,**fields):
        return {'request_id':str(uuid.uuid4()),'expected_version':self.projects.read(self.pid)['version'],
                'authorize_external_request':True,'authorize_opportunity_assessments':True,**fields}

    def act(self,body=None):return self.projects.act(self.pid,'assess_opportunities',body or self.body())

    def reasons(self,saved):return [r['reason'] for r in saved.get('opportunity_exclusions',[])]

    def test_relevant_opportunity_generates_briefing_and_reopens_with_exact_quotes(self):
        body=self.body(); saved=self.act(body)
        self.assertEqual(len(saved['selected_opportunities']),1); self.assertEqual(len(saved['briefings']),1)
        self.assertEqual(saved['decisions'],[]); self.assertEqual(len(self.calls),1)
        selection=saved['selected_opportunities'][0]
        self.assertEqual(selection['benefit_status'],'unverified_hypothesis')
        self.assertEqual(selection['supporting_evidence'],saved['assessments'][0]['assessment']['evidence'])
        self.assertEqual(saved['briefings'][0]['supporting_evidence'],selection['supporting_evidence'])
        self.assertEqual(selection['opportunity_details']['impact_domain'],'productivity')
        self.assertEqual(saved['opportunity_assessment_receipts'][0]['status'],'validated')
        reopened=workflow.Projects(self.root).read(self.pid)
        self.assertEqual(reopened['selected_opportunities'],saved['selected_opportunities'])
        self.assertEqual(self.act(body)['selected_opportunities'],saved['selected_opportunities'])
        again=self.act(); self.assertEqual(len(self.calls),1)
        self.assertEqual(len(again['opportunity_selections']),1)

    def test_irrelevant_and_uncertain_assessments_are_preserved_but_not_briefed(self):
        other=self.add_source('unrelated',PAGE.replace(b'PolicyHelp',b'OtherTool'))
        self.effects[self.cid]='low relevance'; self.effects[other]='uncertain relevance'
        saved=self.act()
        self.assertEqual(len(saved['assessments']),2); self.assertEqual(saved['selected_opportunities'],[])
        self.assertEqual(saved['briefings'],[])
        self.assertEqual(set(self.reasons(saved)),{'low_relevance','uncertain_relevance'})

    def test_resource_incompatible_or_unknown_fit_is_excluded_without_forcing_selection(self):
        other=self.add_source('other',PAGE.replace(b'PolicyHelp',b'OtherTool'))
        def incompatible(v):v['opportunity_details']['feasibility']['resource_fit']='incompatible'; return v
        def unknown(v):v['opportunity_details']['feasibility']['status']='unknown'; return v
        self.effects[self.cid]=incompatible; self.effects[other]=unknown
        saved=self.act()
        self.assertEqual(saved['selected_opportunities'],[]); self.assertEqual(saved['briefings'],[])
        self.assertEqual(set(self.reasons(saved)),{'resource_or_constraint_incompatible','feasibility_or_resources_unconfirmed'})

    def test_duplicate_saved_content_uses_only_one_inference(self):
        self.add_source('mirror')
        saved=self.act(); self.assertEqual(len(self.calls),1)
        self.assertEqual(len(saved['selected_opportunities']),1)
        self.assertIn('duplicate_evidence',self.reasons(saved))

    def test_unsupported_mechanism_rejected_output_and_receipt_are_retained(self):
        def unsupported(v):v['opportunity_details']['improvement_mechanism']['evidence_claim_ids']=['invented-claim']; return v
        self.effects[self.cid]=unsupported; body=self.body()
        with self.assertRaises(workflow.WorkflowError):self.act(body)
        saved=self.projects.read(self.pid)
        self.assertEqual(saved['assessments'],[]); self.assertEqual(saved['selected_opportunities'],[])
        receipt=saved['opportunity_assessment_receipts'][0]
        self.assertEqual(receipt['failure_code'],'opportunity_details_invalid')
        self.assertTrue((self.projects.store(self.pid).directory/receipt['output_reference']['path']).is_file())
        self.assertEqual(len(self.calls),1)
        with self.assertRaises(workflow.WorkflowError):self.act(body)
        self.act(); self.assertEqual(len(self.calls),1)

    def test_human_reject_or_defer_has_authority_over_selection_and_reassessment(self):
        saved=self.act(); brief=saved['briefings'][0]; records=copy.deepcopy(saved['assessments'])
        for choice in ('Reject','Defer'):
            current=self.projects.read(self.pid)
            head=current['decisions'][-1]['id'] if current['decisions'] else None
            decision=self.projects.act(self.pid,'decide',{'request_id':str(uuid.uuid4()),'expected_version':current['version'],
                'explicit_action':'record_project_decision','briefing_id':brief['id'],'briefing_sha256':brief['record_sha256'],
                'expected_head':head,'choice':choice,'rationale':'Human rationale: do not proceed without project-specific proof.'})
            reopened=self.projects.read(self.pid); self.assertEqual(reopened['selected_opportunities'],[])
            self.assertIn('human_reject_or_defer',self.reasons(reopened))
            after=self.act(); self.assertIn('human_reject_or_defer',self.reasons(after))
            self.assertEqual(after['decisions'],decision['decisions']); self.assertEqual(after['assessments'],records)
        self.assertEqual(len(self.calls),1)

    def test_stale_evidence_and_superseded_assessment_remove_current_selection(self):
        saved=self.act(); original=copy.deepcopy(saved['opportunity_selections'])
        store=self.projects.store(self.pid); item=saved['items'][self.cid]
        path=store.directory/item['snapshot_path']; path.write_bytes(b'<main>Changed snapshot</main>')
        reopened=self.projects.read(self.pid)
        self.assertEqual(reopened['selected_opportunities'],[])
        self.assertEqual(reopened['opportunity_selections'],original)
        self.assertEqual(next(iter(reopened['opportunity_selection_status'].values()))['exclusion_reason'],'stale_or_invalid_assessment')
        path.write_bytes(PAGE)
        self.projects.act(self.pid,'assess',{'request_id':str(uuid.uuid4()),'expected_version':reopened['version'],
            'candidate_id':self.cid,'authorize_external_request':True,'opportunity_contract':contract.VERSION})
        self.assertEqual(self.projects.read(self.pid)['selected_opportunities'],[])

    def test_budget_exhaustion_and_failed_inference_reservations_are_cumulative(self):
        self.projects.external_limits['assess']=1
        self.add_source('different',PAGE.replace(b'PolicyHelp',b'OtherTool'))
        saved=self.act(); self.assertEqual(len(self.calls),1)
        self.assertIn('assessment_budget_exhausted',self.reasons(saved))
        self.act(); self.assertEqual(len(self.calls),1)

    def test_interrupted_inference_recovers_without_redispatch_even_when_disabled(self):
        def interrupt(v):raise KeyboardInterrupt()
        self.effects[self.cid]=interrupt; body=self.body()
        with self.assertRaises(KeyboardInterrupt):self.act(body)
        disabled=workflow.Projects(self.root)
        recovered=disabled.act(self.pid,'assess_opportunities',body)
        self.assertEqual(recovered['opportunity_assessment_runs'][body['request_id']]['status'],'interrupted')
        self.assertEqual(sum(o['action']=='assess' for o in recovered['operations'].values()),1)
        self.effects.clear(); self.projects=workflow.Projects(self.root,**self.services)
        self.act(); self.assertEqual(len(self.calls),1)

    def test_default_disabled_missing_consent_and_stale_versions_do_not_dispatch(self):
        disabled=workflow.Projects(self.root)
        with self.assertRaises(workflow.WorkflowError):disabled.act(self.pid,'assess_opportunities',self.body())
        for fields in ({'authorize_external_request':False},{'authorize_opportunity_assessments':False},{'expected_version':-1}):
            with self.assertRaises(workflow.WorkflowError):self.act(self.body(**fields))
        self.assertEqual(self.calls,[])

    def test_versioned_fields_do_not_change_the_legacy_assessment_contract(self):
        request=self.projects.prepare_assessment(self.projects.store(self.pid),self.projects.read(self.pid),
            self.projects.read(self.pid)['items'][self.cid],[])
        self.assertNotIn('opportunity_details',output.contract(request)['properties']['assessments']['items']['properties'])
        request['opportunity_contract']=contract.VERSION
        self.assertIn('opportunity_details',output.contract(request)['properties']['assessments']['items']['properties'])
        valid=wire(request)
        for edit in (
            lambda v:v['opportunity_details']['improvement_mechanism'].update(project_quote='A goal absent from the saved brief.'),
            lambda v:v['opportunity_details']['improvement_mechanism'].update(explanation='This will reduce costs by twenty percent.'),
            lambda v:v['opportunity_details']['improvement_mechanism'].update(explanation='The mechanism produces verified project benefits and measured savings.'),
            lambda v:v['opportunity_details']['feasibility'].update(resource_quotes=[]),
            lambda v:v['opportunity_details'].update(evidence_quality='verified_project_benefit')):
            value=copy.deepcopy(valid); edit(value)
            with self.assertRaises(workflow.semantic.AssessmentError):output.materialize(json.dumps({'assessments':[value]}),request)
        canonical=output.materialize(json.dumps({'assessments':[valid]}),request)
        record,details=contract.evaluate(canonical,request)
        self.assertEqual(set(record['assessment']),workflow.semantic.FIELDS)
        self.assertEqual(details['evidence_quality'],'publisher_claims_only')

    def test_existing_api_exposes_selection_and_preserves_session_origin_guards(self):
        backend=app.State(self.root,project_services=self.services); backend.project_only=True
        body=self.body(); path='/api/projects/'+self.pid+'/assess_opportunities'
        self.assertEqual(dispatch(backend,path,'POST',body,authenticated=False)[0],401)
        self.assertEqual(dispatch(backend,path,'POST',body,origin=False)[0],403)
        code,saved=dispatch(backend,path,'POST',body); self.assertEqual(code,200)
        code,reopened=dispatch(app.State(self.root),'/api/projects/'+self.pid); self.assertEqual(code,200)
        self.assertEqual(saved['selected_opportunities'],reopened['selected_opportunities'])

    def test_discovery_to_assessment_and_backend_selection_without_search_during_assessment(self):
        searches=[]; raw=PAGE.replace(b'PolicyHelp',b'DiscoveredHelp')
        def search(query,*,max_results=5):
            searches.append(query)
            return [] if len(searches)==1 else [{'url':'https://discovered.example/docs','title':'DiscoveredHelp'}]
        self.services.update(searcher=search,fetcher=lambda url:{'raw':raw},external_limits={'discover':2,'assess':2})
        self.projects=workflow.Projects(self.root,**self.services)
        discovered=self.projects.act(self.pid,'discover_adaptive',self.body(authorize_adaptive_queries=True))
        candidates=[cid for cid in discovered['items'] if cid!=self.cid]
        self.assertEqual(len(candidates),1); self.assertEqual(len(searches),2); self.assertEqual(self.calls,[])
        self.assertNotEqual(searches[0],searches[1])
        job=next(iter(discovered['adaptive_discovery_runs'].values()))
        self.assertEqual(len(job['strategy']['reservations']),2)
        self.assertEqual(job['strategy']['remaining']['queries'],0)
        self.assertEqual(job['strategy']['evaluations'][0]['outcome'],'weak')
        evidence=job['strategy']['feedback'][-1]['sources'][0]
        self.assertEqual(evidence['comparison']['classification'],'new')
        saved=self.act(self.body(candidate_ids=candidates))
        self.assertEqual(len(searches),2); self.assertEqual(len(self.calls),1)
        self.assertEqual(saved['selected_opportunities'][0]['candidate_id'],candidates[0])
        # Reconstruct the backend with no transports: restart/reopen is read-only.
        code,reopened=dispatch(app.State(self.root),'/api/projects/'+self.pid)
        self.assertEqual(code,200)
        self.assertEqual(reopened['selected_opportunities'],saved['selected_opportunities'])
        self.assertEqual(reopened['adaptive_discovery_runs'],saved['adaptive_discovery_runs'])
        self.assertEqual(reopened['decisions'],discovered['decisions'])
        self.assertEqual(reopened['items'],discovered['items'])
        source=reopened['items'][candidates[0]]
        self.assertEqual(source['raw_sha256'],workflow.discovery.sha(raw))
        # Render the actual API payload through the shipped UI, without HTTP or writes.
        program=r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
class Element {
  constructor(){this.children=[];this.textContent='';}
  append(n){this.children.push(n);} replaceChildren(){this.children=[];} setAttribute(){}
}
const elements=new Map(), payload=JSON.parse(fs.readFileSync(0,'utf8'));
const context=vm.createContext({URL,crypto:{randomUUID:()=> 'offline-request'},
  document:{createElement:()=>new Element(),querySelector:s=>{
    if(!elements.has(s))elements.set(s,new Element());return elements.get(s);
  }},fetch:path=>{assert.equal(path,'/api/projects');return new Promise(()=>{});},payload});
vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),context);
vm.runInContext('project=payload;render()',context);
const text=n=>n.textContent+' '+n.children.map(text).join(' ');
const cards=elements.get('#opportunities').children;
assert.equal(cards.length,1);
const selected=payload.selected_opportunities[0], content=text(cards[0]);
for(const value of [payload.briefings[0].title,selected.project_need,selected.potential_value,
  selected.opportunity_details.improvement_mechanism.explanation,selected.next_step,
  selected.supporting_evidence[0].exact_quote,
  payload.items[selected.candidate_id].raw_sha256])assert.ok(content.includes(value),value);
assert.match(content,/unverified hypothesis/);
assert.match(text(elements.get('#project-runs')),/Budget exhausted/);
'''
        result=subprocess.run(['node','-e',program,str(Path(__file__).resolve().parents[1]/'web/projects.js')],
                              input=json.dumps(reopened),capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_reserved_inference_checkpoint_failure_never_dispatches_or_regains_capacity(self):
        real_save=workflow.discovery.Store.save; failed=[]
        def fail_after_reservation(store,state):
            result=real_save(store,state)
            if any(o['action']=='assess' and o['status']=='started' for o in state['operations'].values()) and not failed:
                failed.append(True); raise OSError('Synthetic persistence confirmation failure')
            return result
        with patch.object(workflow.discovery.Store,'save',fail_after_reservation):
            with self.assertRaises(workflow.WorkflowError):self.act()
        saved=self.projects.read(self.pid)
        self.assertEqual(sum(o['action']=='assess' for o in saved['operations'].values()),1)
        self.assertEqual(self.calls,[])
        self.act(); self.assertEqual(self.calls,[])

    def test_interruption_after_validated_output_recovers_with_local_briefing_only(self):
        body=self.body(); real_save=workflow.discovery.Store.save; failed=[]
        def interrupt_after_validated(store,state):
            result=real_save(store,state)
            if state['assessments'] and not state['briefings'] and not failed:
                failed.append(True); raise KeyboardInterrupt()
            return result
        with patch.object(workflow.discovery.Store,'save',interrupt_after_validated):
            with self.assertRaises(KeyboardInterrupt):self.act(body)
        workflow.Projects(self.root).act(self.pid,'assess_opportunities',body)
        self.projects=workflow.Projects(self.root,**self.services)
        saved=self.act()
        self.assertEqual(len(self.calls),1); self.assertEqual(len(saved['selected_opportunities']),1)
        self.assertEqual(len(saved['briefings']),1)

    def test_tampered_retained_output_invalidates_selection_without_repair(self):
        saved=self.act(); retained=saved['assessments'][0]['output_reference']
        path=self.projects.store(self.pid).directory/retained['path']; path.write_bytes(b'{}')
        reopened=self.projects.read(self.pid)
        self.assertEqual(reopened['selected_opportunities'],[])
        self.assertEqual(reopened['opportunity_selections'],saved['opportunity_selections'])
        self.assertEqual(len(self.calls),1)

    def test_requesting_only_a_mirror_does_not_bypass_duplicate_exclusion(self):
        mirror=self.add_source('mirror')
        saved=self.act(self.body(candidate_ids=[mirror]))
        self.assertEqual(self.calls,[]); self.assertIn('duplicate_evidence',self.reasons(saved))

    def test_v2_adapter_sends_extended_schema_and_retains_wire_text_for_workflow_validation(self):
        saved=self.projects.read(self.pid)
        request=self.projects.prepare_assessment(self.projects.store(self.pid),saved,saved['items'][self.cid],[])
        request['opportunity_contract']=contract.VERSION
        raw=json.dumps({'assessments':[wire(request)]})
        response={'ok':True,'http_status':200,'data':{'choices':[{'finish_reason':'stop',
            'message':{'role':'assistant','content':raw}}]}}
        settings=SimpleNamespace(meterless_url='http://127.0.0.1:8088',
            completions_url='http://127.0.0.1:8088/v1/chat/completions',model='nvidia/nemotron-3.5-lightning-30b-a3b')
        with patch.object(adapters.config,'settings',return_value=settings), \
             patch.object(adapters.config,'secret',return_value='offline-provider-token'), \
             patch.object(adapters.analyzer,'request_claims',return_value=response) as transport:
            returned=adapters.assess(request)
            self.assertEqual(returned,raw)
            transport.assert_called_once()
            sent=transport.call_args.kwargs['response_schema']['properties']['assessments']['items']
            self.assertIn('opportunity_details',sent['required'])
            self.assertEqual(sent['properties']['opportunity_details'],contract.schema(request))
            self.assertIn('OPPORTUNITY V2',transport.call_args.args[1][0]['content'])
        result,details=contract.evaluate(output.materialize(returned,request),request)
        self.assertEqual(result['assessment']['evidence'][0]['exact_quote'],request['staged_plan']['claims'][0]['exact_quote'])
        self.assertEqual(details['evidence_quality'],'publisher_claims_only')


if __name__=='__main__':unittest.main()
