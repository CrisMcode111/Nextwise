"""Bounded adaptive discovery over Projects' locked, versioned H-MEM store.

No model/selection stage, scheduler, background retry, new provider or store.
The existing Projects POST dispatcher exposes this as discover_adaptive.
"""
import copy
import uuid

import project_opportunities as planning
import project_workflow as workflow


def search_attempts(state):
    """Share the existing project search ceiling with legacy manual discovery."""
    manual = sum(o['action']=='discover' for o in state['operations'].values())
    return manual + sum(len(r['strategy']['reservations'])
                        for r in state.get('adaptive_discovery_runs', {}).values())


def _save(store, state):
    # Keep references stable while the existing save increments the version and
    # confirms a real H-MEM readback. Any failure stops before another dispatch.
    saved = store.save(state)
    workflow.require(saved == state, 'Discovery checkpoint could not be confirmed.')


def _gate(projects, state, body):
    workflow.require(body.get('authorize_external_request') is True
                     and body.get('authorize_adaptive_queries') is True,
                     'Explicit authorization of bounded adaptive public queries is required.')
    workflow.require(callable(projects.searcher) and callable(projects.fetcher)
                     and 'discover' in projects.external_limits, 'Search transports/limits are disabled.')
    workflow.require(search_attempts(state) <= projects.external_limits['discover'],
                     'Project cumulative search limit reached.')


def _feedback(attempt, *, unknown=False, status='completed'):
    return {'feedback_id':attempt['id'], 'attempt_id':attempt['id'], 'status':status,
        'accounting_confirmed':not unknown,
        'results_received':None if unknown else attempt['results_received'],
        'pages_attempted':None if unknown else len(attempt['pages']),
        'sources':copy.deepcopy(attempt['sources'])}


def _recover(projects, store, state, job):
    settled = {f['attempt_id'] for f in job['strategy']['feedback']}
    reports = []
    for reservation in job['strategy']['reservations']:
        aid = reservation['attempt_id']
        if aid not in settled:
            attempt = job['attempts'][aid]
            attempt['stage'] = 'interrupted_unconfirmed'
            reports.append(_feedback(attempt, unknown=True, status='interrupted'))
            state['operations'][aid]['status'] = 'failed'
    job['strategy'] = planning.adapt_strategy(projects.read(state['project']['id']),
                                              job['strategy'], feedback=reports)
    job['status'] = 'interrupted'
    job['note'] = 'No interrupted search/page was redispatched; unconfirmed reservations remain consumed.'
    for operation in state['operations'].values():
        if operation.get('adaptive_run_id') == job['id'] and operation['status']=='started':
            operation['status'] = 'failed'
    _save(store,state)


def _previous_snapshots(store, state, url):
    result = {}
    refs = planning._evidence(state) + state.get('discovery_evidence_history', [])
    for ref in refs:
        if planning._url(ref) != url or not isinstance(ref.get('snapshot_path'),str):
            continue
        path = (store.directory/ref['snapshot_path']).resolve()
        workflow.require(path.is_relative_to((store.directory/'runs').resolve()), 'Unsafe saved evidence path.')
        if path.is_file():
            result[ref['snapshot_path']] = path.read_bytes()
    return result


def _process_results(projects, store, state, job, attempt, reservation, leads, body):
    semantic, tavily, discovery = workflow.semantic, workflow.tavily, workflow.discovery
    # Never refetch a URL already attempted during this cumulative strategy.
    seen = {p['url'] for a in job['attempts'].values() for p in a['pages']}
    for index, lead in enumerate(leads):
        source = {'source_key':f"{attempt['id']}:{index}", 'usability':'unavailable', 'coverage':'unknown'}
        attempt['sources'].append(source)
        try:
            url = tavily.source_url(lead['url'])
        except (KeyError, TypeError, ValueError):
            source.update(usability='unsafe', reason='unsafe_or_missing_url')
            _save(store,state)
            continue
        cid = discovery.collector.stable_source_id(url)
        source['candidate_id'] = cid
        probe = {**state,'items':{**state['items'],cid:{'url':url}}}
        if planning._blocked(probe,cid):
            source['reason'] = 'saved_human_decision'
            _save(store,state)
            continue
        if url in seen:
            source.update(reason='already_attempted_in_strategy', comparison={
                'classification':'duplicate','comparison_status':'already_attempted_url'})
            _save(store,state)
            continue
        if len(attempt['pages']) >= reservation['page_limit']:
            source['reason'] = 'page_allowance_exhausted'
            _save(store,state)
            continue
        _gate(projects,state,body)
        page = {'url':url, 'stage':'reserved', 'created_at':semantic.now()}
        attempt['pages'].append(page)
        seen.add(url)
        _save(store,state)  # A page attempt is consumed even if transport dies.
        _gate(projects,state,body)
        try:
            response = projects.fetcher(url)
        except Exception:
            response = {'error':'page_transport_failed'}
        raw = response.get('raw') if isinstance(response,dict) and not response.get('error') else None
        if not isinstance(raw,bytes) or not 1 <= len(raw) <= discovery.MAX_BYTES:
            page['stage'] = 'unavailable'
            source['reason'] = 'page_unavailable_or_oversized'
            _save(store,state)
            continue
        text = semantic.html_extract.extract_readable_text(raw.decode('utf-8',errors='replace'))
        relative = f"runs/{attempt['id']}/{cid}.html"
        target = store.directory/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as stream:
            stream.write(raw)
        item = {'id':cid,'title':str(lead.get('title') or url)[:200],'url':url,
            'publication_date':None,'retrieved_at':semantic.now(),'source':'tavily-page',
            'snapshot_path':relative,'raw_sha256':discovery.sha(raw),
            'content_sha256':discovery.sha(text),'kind':'saved_page'}
        page['evidence'] = copy.deepcopy(item)
        try:
            p = state['project']
            semantic.prepare_business_assessment(store,item,p['brief'],name=p['name'],
                                                  input_kind=p['input_kind'],sanitized=True)
        except ValueError:
            page['stage'] = 'unusable_evidence'
            source.update(usability='unreadable',reason='no_valid_whole_evidence_passage')
            _save(store,state)
            continue
        historical = {'project':state['project'], 'items':{str(i):r for i,r in
                       enumerate(state.get('discovery_evidence_history',[]))}}
        source['comparison'] = planning.compare_evidence(item,state,snapshot=raw,
            previous_snapshots=_previous_snapshots(store,state,url),history=[historical])
        old = state['items'].get(cid)
        refs = state.setdefault('discovery_evidence_history',[])
        if old and old not in refs:
            refs.append(copy.deepcopy(old))
        refs.append(copy.deepcopy(item))
        # Identical readable evidence must not invalidate an existing briefing.
        if not old or old['content_sha256'] != item['content_sha256']:
            state['items'][cid] = item
        page['stage'] = 'saved'
        source.update(usability='usable',coverage='saved_page')
        _save(store,state)


def run(projects, project_id, body):
    """POST action discover_adaptive. Resume requires a NEW explicit request.

    New: request_id, expected_version, authorize_external_request=true,
    authorize_adaptive_queries=true, optional limits (the Phase 2A limit names).
    Continue an existing cumulative ledger: also supply run_id; ceilings cannot
    be replaced. Repeating a request never dispatches, regardless of its outcome.
    """
    require = workflow.require
    rid = workflow.request_id(body)
    store = projects.store(project_id)
    with store.exclusive():
        state = projects._read(store,project_id)
        fingerprint = workflow.semantic.digest({'action':'discover_adaptive','body':body})
        jobs = state.get('adaptive_discovery_runs',{})
        prior = state['operations'].get(rid)
        if prior:
            require(prior['fingerprint']==fingerprint,'Request ID belongs to another action.')
            if prior['status']=='completed':
                return copy.deepcopy(state)
            job = jobs[prior['adaptive_run_id']]
            if prior['status']=='started':
                _recover(projects,store,state,job)
                return copy.deepcopy(state)
            raise workflow.WorkflowError('Prior adaptive attempt failed; inspect its persisted ledger.')
        require(type(body.get('expected_version')) is int and body['expected_version']==state['version'],
                'Project changed; reopen its latest version.')
        _gate(projects,state,body)
        run_id = body.get('run_id')
        if run_id is not None:
            require(run_id in jobs,'Adaptive run not found.')
            require('limits' not in body,'Resuming cannot replace the original cumulative ceilings.')
            job = jobs[run_id]
            settled = {r['attempt_id'] for r in job['strategy']['feedback']}
            if any(r['attempt_id'] not in settled for r in job['strategy']['reservations']):
                _recover(projects,store,state,job)
                return copy.deepcopy(state)  # Recovery never dispatches in the same request.
            # A process may stop after confirmed feedback but before reserving
            # its next query. Only a new authorized request continues that gap.
            for operation in state['operations'].values():
                if (operation.get('adaptive_run_id')==job['id']
                        and operation['action']=='discover_adaptive' and operation['status']=='started'):
                    operation['status'] = 'failed'
            job['strategy'] = planning.adapt_strategy(projects.read(project_id),job['strategy'])
            require(job['strategy']['status']=='proposed_for_review','No remaining bounded search proposal.')
        else:
            require(not jobs,'Continue the existing cumulative adaptive run; do not reset its ledger.')
            remaining = projects.external_limits['discover']-search_attempts(state)
            require(remaining>0,'Project cumulative search limit reached.')
            limits = body.get('limits',{})
            require(isinstance(limits,dict) and set(limits)<=
                    {'max_queries','results_per_query','max_source_pages'},'Invalid discovery limits.')
            limits = {'max_queries':min(planning.tavily.MAX_SEARCHES,remaining),**limits}
            require(type(limits['max_queries']) is int and limits['max_queries']<=remaining,
                    'Requested search allowance exceeds the project remainder.')
            plan = planning.plan_discovery(state,**limits)
            strategy = planning.create_strategy(projects.read(project_id),plan,allowance={
                'queries':plan['limits']['max_queries'],'results':plan['limits']['max_search_results'],
                'pages':plan['limits']['max_source_pages']})
            job = {'id':rid,'created_at':workflow.semantic.now(),'strategy':strategy,'attempts':{},
                   'authorizations':[], 'status':'running'}
            state.setdefault('adaptive_discovery_runs',{})[rid] = job
        job['authorizations'].append({'request_id':rid,'authorize_external_request':True,
            'authorize_adaptive_queries':True,'allowance':copy.deepcopy(job['strategy']['allowance'])})
        state['operations'][rid] = {'action':'discover_adaptive','fingerprint':fingerprint,
                                   'status':'started','adaptive_run_id':job['id']}
        job['status'] = 'running'
        _save(store,state)
        try:
            while job['strategy']['status']=='proposed_for_review':
                _gate(projects,state,body)
                require(search_attempts(state)<projects.external_limits['discover'],
                        'Project cumulative search limit reached.')
                proposal = job['strategy']['proposals'][0]
                aid = str(uuid.uuid4())
                job['strategy'] = planning.reserve_search(projects.read(project_id),job['strategy'],
                                                          proposal['proposal_id'],attempt_id=aid)
                reservation = job['strategy']['reservations'][-1]
                attempt = {'id':aid,'authorization_request_id':rid,'stage':'search_reserved',
                           'results_received':0,'sources':[],'pages':[]}
                job['attempts'][aid] = attempt
                state['operations'][aid] = {'action':'adaptive_search','fingerprint':workflow.semantic.digest(reservation),
                    'status':'started','adaptive_run_id':job['id']}
                _save(store,state)
                _gate(projects,state,body)
                leads = projects.searcher(reservation['query'],max_results=reservation['result_limit'])
                require(isinstance(leads,list) and len(leads)<=reservation['result_limit'],
                        'Search returned an invalid or over-limit result list.')
                attempt.update(stage='search_returned',results_received=len(leads))
                _save(store,state)
                _process_results(projects,store,state,job,attempt,reservation,leads,body)
                attempt['stage'] = 'completed'
                job['strategy'] = planning.adapt_strategy(projects.read(project_id),job['strategy'],
                                                          feedback=[_feedback(attempt)])
                state['operations'][aid]['status'] = 'completed'
                _save(store,state)
            job['status'] = 'completed'
            job['outcome'] = job['strategy']['status']
            state['operations'][rid]['status'] = 'completed'
            if state.get('opportunity_selections'):
                from project_selection import record_invalidations
                record_invalidations(projects,store,state)
            _save(store,state)
            return copy.deepcopy(state)
        except Exception:
            # Reload the last confirmed checkpoint: never publish optimistic
            # in-memory accounting after a failed persistence/transport operation.
            state = projects._read(store,project_id)
            job = state['adaptive_discovery_runs'][job['id']]
            _recover(projects,store,state,job)
            job['status'] = 'failed'
            job['note'] = 'Discovery failed or persistence is unconfirmed; no independent retry was made.'
            _save(store,state)
            raise workflow.WorkflowError('Adaptive discovery stopped; inspect saved progress and reservations.') from None
