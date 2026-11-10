"""Project opportunity assessment/selection; no searches or human decisions."""
import copy
import uuid

import opportunity_assessment as contract
import project_opportunities as planning
import project_workflow as workflow
from project_discovery_run import _save


POLICY = 'project-opportunity-selection-v1'


def _append(state, field, candidate_id, **values):
    records=state.setdefault(field,[])
    previous=next((r for r in reversed(records) if r['candidate_id']==candidate_id),None)
    record=workflow.opportunities.seal({'id':str(uuid.uuid4()),'candidate_id':candidate_id,
        'project_id':state['project']['id'],'policy':POLICY,'created_at':workflow.semantic.now(),
        'version':previous['version']+1 if previous else 1,
        'previous_record_sha256':previous['record_sha256'] if previous else None,**values})
    records.append(record)
    return record


def _reason(projects, store, state, record):
    cid=record['candidate_id']
    if planning._blocked(state,cid):return 'human_reject_or_defer'
    try:current=projects._assessment(store,state,record['id'])
    except (ValueError,OSError,KeyError,TypeError):return 'stale_or_invalid_assessment'
    if current['assessment']['category']!='potential relevance':
        return 'low_relevance' if current['assessment']['category']=='low relevance' else 'uncertain_relevance'
    if current.get('opportunity_contract')!=contract.VERSION:return 'historical_contract_missing_opportunity_details'
    fit=current['opportunity_details']['feasibility']
    if fit['status']=='incompatible' or fit['resource_fit']=='incompatible':return 'resource_or_constraint_incompatible'
    if (fit['status']!='plausible_for_bounded_review' or fit['resource_fit']!='plausible_for_bounded_review'
            or fit['blocking_unknowns']):return 'feasibility_or_resources_unconfirmed'
    if current['assessment']['priority'] not in ('medium','high'):return 'not_actionable_priority'
    return None


def present(projects, store, state):
    """Read-only current view; invalidate history without rewriting its records."""
    heads={}
    for record in state.get('opportunity_selections',[]):heads[record['candidate_id']]=record
    selected=[]; status={}; seen=set()
    for cid,selection in heads.items():
        assessment=next((a for a in state['assessments'] if a['id']==selection['assessment_id']),None)
        reason=_reason(projects,store,state,assessment) if assessment else 'assessment_missing'
        briefs=[b for b in state['briefings'] if b['candidate_id']==cid]
        brief=briefs[-1] if briefs else {}
        if not reason and (brief.get('id')!=selection['briefing_id']
                or brief.get('record_sha256')!=selection['briefing_sha256']
                or brief.get('assessment_id')!=selection['assessment_id']):reason='briefing_superseded_or_invalid'
        fingerprint=state['items'].get(cid,{}).get('content_sha256')
        owner=next((key for key,item in state['items'].items() if item.get('content_sha256')==fingerprint),None)
        if not reason and owner!=cid:reason='duplicate_evidence'
        if not reason and fingerprint in seen:reason='duplicate_evidence'
        if not reason:
            seen.add(fingerprint); selected.append(copy.deepcopy(selection))
        status[selection['id']]={'current':reason is None,'exclusion_reason':reason}
    return {'selected_opportunities':selected,'opportunity_selection_status':status}


def record_invalidations(projects,store,state):
    """Append exclusion events alongside causal writes, never during GET."""
    if not state.get('opportunity_selections'):return
    status=present(projects,store,state)['opportunity_selection_status']
    for selection in state['opportunity_selections']:
        current=status.get(selection['id'])
        if not current or current['current']:continue
        latest=next((e for e in reversed(state.get('opportunity_exclusions',[]))
                     if e.get('selection_id')==selection['id']),None)
        if latest and latest['reason']==current['exclusion_reason']:continue
        _append(state,'opportunity_exclusions',selection['candidate_id'],selection_id=selection['id'],
                reason=current['exclusion_reason'])


def _authorize(projects,body):
    workflow.require(body.get('authorize_external_request') is True
        and body.get('authorize_opportunity_assessments') is True,
        'Explicit authorization of bounded opportunity assessments is required.')
    workflow.require(callable(projects.assessor) and 'assess' in projects.external_limits,
                     'Assessment transport/limits are disabled.')


def _receipt(store,state,attempt,status,code=None):
    receipt={'attempt_id':attempt['id'],'status':status,'failure_code':code}
    path=store.directory/'runs'/attempt['id']/'assessment-output.json'
    if path.is_file():
        receipt['output_reference']={'path':str(path.relative_to(store.directory)).replace('\\','/'),
                                     'sha256':workflow.discovery.sha(path.read_bytes())}
    state.setdefault('opportunity_assessment_receipts',[]).append(receipt)


def _recover(store,state,job,reason='interrupted',code=None):
    for attempt in job['attempts']:
        if state['operations'][attempt['id']]['status']=='started':
            state['operations'][attempt['id']]['status']='failed'
            attempt['status']=reason
            _receipt(store,state,attempt,reason,code)
            _append(state,'opportunity_exclusions',attempt['candidate_id'],reason=reason,
                    run_id=job['id'],assessment_attempt_id=attempt['id'])
    state['operations'][job['id']]['status']='failed'
    job['status']=reason
    _save(store,state)


def _select(projects,store,state,record,job):
    cid=record['candidate_id']
    reason=_reason(projects,store,state,record)
    if reason:
        _append(state,'opportunity_exclusions',cid,reason=reason,run_id=job['id'],assessment_id=record['id'])
        return
    brief=next((b for b in reversed(state['briefings']) if b['candidate_id']==cid),None)
    if not brief or brief['assessment_id']!=record['id']:
        bid=str(uuid.uuid4())
        projects._brief(store,state,{'assessment_id':record['id']},bid)
        state['operations'][bid]={'action':'brief','fingerprint':workflow.semantic.digest({'assessment_id':record['id']}),
                                  'status':'completed'}
        brief=state['briefings'][-1]
        _save(store,state)
    previous=next((s for s in reversed(state.get('opportunity_selections',[])) if s['candidate_id']==cid),None)
    if previous and previous['assessment_id']==record['id'] and previous['briefing_id']==brief['id']:
        return
    _append(state,'opportunity_selections',cid,run_id=job['id'],assessment_id=record['id'],
        briefing_id=brief['id'],briefing_sha256=brief['record_sha256'],
        opportunity_details=copy.deepcopy(record['opportunity_details']),
        project_need=record['assessment']['project_need'],potential_value=record['assessment']['application_hypothesis'],
        supporting_evidence=copy.deepcopy(record['assessment']['evidence']),
        uncertainty=record['assessment']['limitations']+record['assessment']['missing_information'],
        next_step=record['assessment']['next_step'],benefit_status='unverified_hypothesis',
        evidence_quality='publisher_claims_only')


def run(projects,project_id,body):
    """Projects action assess_opportunities; reads saved evidence, never searches.

    Requires both explicit authorization flags and configured assessment limits.
    candidate_ids is optional; max_assessments is bounded to four per request.
    Every child inference consumes the existing permanent assessment ceiling.
    """
    require=workflow.require; rid=workflow.request_id(body); store=projects.store(project_id)
    with store.exclusive():
        state=projects._read(store,project_id)
        fingerprint=workflow.semantic.digest({'action':'assess_opportunities','body':body})
        previous=state['operations'].get(rid)
        if previous:
            require(previous['fingerprint']==fingerprint,'Request ID belongs to another action.')
            job=state['opportunity_assessment_runs'][rid]
            if previous['status']=='started':_recover(store,state,job)
            elif previous['status']!='completed':raise workflow.WorkflowError('Prior opportunity attempt failed; no redispatch.')
            return projects.read(project_id)
        require(type(body.get('expected_version')) is int and body['expected_version']==state['version'],
                'Project changed; reopen its latest version.')
        _authorize(projects,body)
        candidates=body.get('candidate_ids',sorted(state['items']))
        require(isinstance(candidates,list) and all(isinstance(c,str) and c in state['items'] for c in candidates)
                and len(set(candidates))==len(candidates),'Choose distinct saved candidates.')
        limit=body.get('max_assessments',min(4,projects.external_limits['assess']))
        require(type(limit) is int and 1<=limit<=4,'Choose an assessment allowance between one and four.')
        job={'id':rid,'candidate_ids':list(candidates),'max_assessments':limit,'attempts':[],
             'status':'running','authorization':{'authorize_external_request':True,'authorize_opportunity_assessments':True}}
        state.setdefault('opportunity_assessment_runs',{})[rid]=job
        state['operations'][rid]={'action':'assess_opportunities','fingerprint':fingerprint,'status':'started'}
        _save(store,state)
        seen={}; budget_exhausted=False
        try:
            for cid in candidates:
                item=state['items'][cid]
                reason=None
                if planning._blocked(state,cid):reason='human_reject_or_defer'
                elif item.get('source')!='tavily-page' or item.get('kind')!='saved_page':reason='ineligible_saved_source'
                digest=item.get('content_sha256')
                owner=next((key for key,source in state['items'].items() if source.get('content_sha256')==digest),None)
                if not reason and owner!=cid:reason='duplicate_evidence'
                if not reason and digest in seen:reason='duplicate_evidence'
                if not reason:
                    for selected in present(projects,store,state)['selected_opportunities']:
                        other=state['items'][selected['candidate_id']]
                        if other['content_sha256']==digest and other['id']!=cid:reason='duplicate_evidence'
                if reason:
                    _append(state,'opportunity_exclusions',cid,reason=reason,run_id=rid)
                    _save(store,state); continue
                seen[digest]=cid
                current=next((a for a in reversed(state['assessments']) if a['candidate_id']==cid),None)
                if current:
                    reason=_reason(projects,store,state,current)
                    if reason and reason!='historical_contract_missing_opportunity_details':
                        _append(state,'opportunity_exclusions',cid,reason=reason,run_id=rid,assessment_id=current['id'])
                        _save(store,state); continue
                    if current.get('opportunity_contract')==contract.VERSION:
                        _select(projects,store,state,current,job); _save(store,state); continue
                try:
                    request=projects.prepare_assessment(store,state,item,[])
                except (ValueError,OSError,KeyError):
                    _append(state,'opportunity_exclusions',cid,reason='evidence_validation_failed',run_id=rid)
                    _save(store,state); continue
                request['opportunity_contract']=contract.VERSION
                input_hash=workflow.semantic.digest(request)
                attempted=[a for j in state['opportunity_assessment_runs'].values() for a in j['attempts']]
                if any(a['candidate_id']==cid and a['input_sha256']==input_hash for a in attempted):
                    _append(state,'opportunity_exclusions',cid,reason='prior_reserved_assessment_input',run_id=rid)
                    _save(store,state); continue
                used=sum(o['action']=='assess' for o in state['operations'].values())
                if used>=projects.external_limits['assess'] or len(job['attempts'])>=limit:
                    budget_exhausted=True
                    _append(state,'opportunity_exclusions',cid,reason='assessment_budget_exhausted',run_id=rid)
                    _save(store,state); continue
                _authorize(projects,body)
                aid=str(uuid.uuid4())
                attempt={'id':aid,'candidate_id':cid,'input_sha256':input_hash,'status':'reserved'}
                job['attempts'].append(attempt)
                state['operations'][aid]={'action':'assess','fingerprint':input_hash,'status':'started'}
                _save(store,state)
                _authorize(projects,body)
                require(sum(o['action']=='assess' for o in state['operations'].values())<=projects.external_limits['assess'],
                        'Project cumulative assessment limit reached.')
                projects._assess(store,state,{'candidate_id':cid,'opportunity_contract':contract.VERSION},aid)
                attempt['status']='validated'; state['operations'][aid]['status']='completed'
                _receipt(store,state,attempt,'validated')
                _save(store,state)
                _select(projects,store,state,state['assessments'][-1],job)
                _save(store,state)
            job['status']='budget_exhausted' if budget_exhausted else 'completed'
            state['operations'][rid]['status']='completed'
            _save(store,state)
            return projects.read(project_id)
        except Exception as error:
            state=projects._read(store,project_id)
            job=state['opportunity_assessment_runs'][rid]
            code=error.diagnostic['code'] if isinstance(error,workflow.semantic.AssessmentError) else 'transport_or_persistence_failed'
            _recover(store,state,job,reason='validation_or_transport_failed',code=code)
            raise workflow.WorkflowError('Opportunity assessment stopped; inspect persisted exclusions and attempt receipts.') from None
