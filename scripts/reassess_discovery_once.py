"""One separately authorized two-candidate reassessment; no retries or source retrieval."""
import argparse
import csv
import getpass
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import uuid
import warnings

import semantic_discovery as semantic
import update_discovery as discovery

AUTHORIZATION='semantic-reassessment-20261026-two-candidates-v1'
CANDIDATES=('9428cc2bc3c996d8505a0fdf','856d845adf1f95fea166c443')
MAX_REQUESTS=1
MAX_TOKENS=4000
OUT=discovery.ROOT/'reports/update_discovery/controlled_reassessment'


def protected_directory(path):
    path.mkdir(parents=True,exist_ok=True)
    if os.name=='nt':
        identity=subprocess.run(['whoami','/user','/fo','csv','/nh'],capture_output=True,text=True,check=True)
        sid=list(csv.reader(io.StringIO(identity.stdout)))[0][-1]
        if not sid.startswith('S-1-'):raise RuntimeError('Cannot establish current-user storage protection.')
        acl=subprocess.run(['icacls',str(path),'/inheritance:r','/grant:r','*'+sid+':(OI)(CI)F',
            '*S-1-5-18:(OI)(CI)F'],capture_output=True)
        if acl.returncode:raise RuntimeError('Cannot protect retained-response directory; no model request sent.')
    else:path.chmod(0o700)


def write_new(path,value):
    with path.open('x',encoding='utf-8') as handle:
        json.dump(value,handle,ensure_ascii=False,indent=2)
        handle.flush();os.fsync(handle.fileno())
    if os.name!='nt':path.chmod(0o600)


def directory(store,authorization=AUTHORIZATION):
    return store.directory/'controlled-reassessments'/authorization


def already_reserved(state,folder,authorization=AUTHORIZATION):
    return (folder/'reservation.json').exists() or any(
        r.get('authorization')==authorization for r in state.get('semantic_requests',[])) or any(
        r.get('authorization')==authorization for r in state.get('semantic_cache',{}).values())


def preparation(store,context,candidate_ids=CANDIDATES):
    state=store.read()
    if len(candidate_ids)!=2 or len(set(candidate_ids))!=2:raise ValueError('Exactly two distinct authorized candidates are required.')
    batch=[semantic.prepare(store,state['items'][cid],context) for cid in candidate_ids]
    prompt=semantic.messages(batch,context)
    if sum(len(m['content']) for m in prompt)>100_000:raise ValueError('Prompt exceeds the existing input bound.')
    return {'prepared_inputs':batch,'messages':prompt,'context_sha256':semantic.digest(context),
        'contract_version':semantic.CONTRACT_VERSION,'validator_version':semantic.VALIDATOR_VERSION,
        'output_contract':semantic.output_contract(batch),'max_output_tokens':MAX_TOKENS,
        'max_response_bytes':semantic.MAX_RESPONSE_BYTES,'timeout_seconds':semantic.analyzer.TIMEOUT_SECONDS}


def evaluate(artifact):
    """Pure offline replay. Candidate errors are independent after batch identity passes."""
    batch=artifact['prepared_inputs'];result={}
    try:
        if artifact.get('transport_failure'):
            raise semantic.AssessmentError('transport','response','The one transport attempt failed; no retry.')
        if 'nemotron' not in artifact['model'].get('returned_model','').lower():
            raise semantic.AssessmentError('returned_model','model','Nemotron routing was not confirmed.')
        content=artifact['content']
        if not isinstance(content,str) or len(content.encode('utf-8'))>semantic.MAX_RESPONSE_BYTES:
            raise semantic.AssessmentError('response_size','response','Missing or oversized model content.')
        if discovery.sha(content)!=artifact['content_sha256']:
            raise semantic.AssessmentError('response_hash','response','Retained content hash mismatch.')
        parsed=semantic.parse_batch(content,batch)
    except semantic.AssessmentError as exc:
        return {p['source']['candidate_id']:{'status':'failed','assessment':None,
            'error':str(exc),'validation_failure':exc.diagnostic} for p in batch}
    for p in batch:
        cid=p['source']['candidate_id']
        try:
            value=semantic.validate(parsed[cid],p)
            result[cid]={'status':'validated','assessment':value,'error':None,'validation_failure':None}
        except semantic.AssessmentError as exc:
            result[cid]={'status':'failed','assessment':None,'error':str(exc),'validation_failure':exc.diagnostic}
    return result


def capture(result,token,inputs,request_id):
    data=result.get('data') if isinstance(result.get('data'),dict) else {}
    usage=data.get('usage') if isinstance(data.get('usage'),dict) else {}
    metadata={'returned_model':semantic.analyzer.sanitize_server_text(str(data.get('model','unknown')),token,[]),
        'http_status':result.get('http_status'),'duration_seconds':result.get('duration_seconds'),
        'usage':{k:v for k,v in usage.items() if k in ('prompt_tokens','completion_tokens','total_tokens') and type(v) is int and v>=0}}
    # Examine the complete bounded envelope for credential echoes, not just message.content.
    echo=bool(token and token in json.dumps(data,ensure_ascii=False))
    content=semantic.analyzer.message_content(data) if not echo else None
    choices=data.get('choices',[])
    finish=next((c.get('finish_reason') for c in choices if isinstance(c,dict) and
        c.get('finish_reason') in ('stop','length','content_filter','tool_calls')),None) if isinstance(choices,list) else None
    return {**inputs,'request_id':request_id,'authorization':AUTHORIZATION,'captured_at':semantic.now(),
        'data':data if not echo else None,'credential_echo_rejected':echo,
        'transport_failure':not result.get('ok') or echo,
        'model':metadata,'content':content,'content_sha256':discovery.sha(content) if isinstance(content,str) else None,
        'finish_reason':finish}


def audit_response(artifact):
    """Additional independent evidence facts; never fill fields or accept claims."""
    try:parsed=semantic.parse_batch(artifact['content'],artifact['prepared_inputs'])
    except semantic.AssessmentError as exc:return {'batch_failure':exc.diagnostic}
    result={}
    for p in artifact['prepared_inputs']:
        source=p['source'];value=parsed[source['candidate_id']]
        passages={s['passage_id']:s['text'] for s in source['passages']};quotes=[]
        evidence=value.get('evidence')
        for e in evidence if isinstance(evidence,list) else []:
            if not isinstance(e,dict):continue
            passage=passages.get(e.get('passage_id')) if isinstance(e.get('passage_id'),str) else None
            quote=e.get('exact_quote')
            quotes.append({'source_id_valid':e.get('source_id')==source['source_id'],
                'passage_id_valid':passage is not None,'exact_quote':isinstance(quote,str) and passage is not None and quote in passage})
        result[source['candidate_id']]={'missing_fields':sorted(semantic.FIELDS-set(value)),
            'existing_investigation':source['existing_investigation'],
            'existing_findings_connection_is_null':value.get('existing_findings_connection') is None,
            'quote_checks':quotes,'changes_outcome':False}
    return result


def replay_saved(store):
    folder=directory(store)
    inputs=json.loads((folder/'inputs.json').read_text(encoding='utf-8'))
    reservation=json.loads((folder/'reservation.json').read_text(encoding='utf-8'))
    if semantic.digest(inputs)!=reservation['input_sha256']:raise ValueError('Retained input hash mismatch.')
    artifact=json.loads((folder/'response.json').read_text(encoding='utf-8'))
    if artifact['request_id']!=reservation['id']:raise ValueError('Retained request identity mismatch.')
    if any(artifact.get(k)!=v for k,v in inputs.items()):raise ValueError('Response preparation differs from reserved inputs.')
    state=store.read()
    # Check immutable snapshots independently of current product context. A replay
    # validates the exact originally supplied paragraphs, not newly selected text.
    for p in inputs['prepared_inputs']:
        source=p['source'];path=(store.directory/source['snapshot_path']).resolve()
        if not path.is_relative_to((store.directory/'runs').resolve()):raise ValueError('Invalid retained snapshot path.')
        if discovery.sha(path.read_bytes())!=source['raw_sha256']:raise ValueError('Retained source hash mismatch.')
        record=next((r for r in state.get('semantic_cache',{}).values() if r.get('request_id')==artifact['request_id']
            and r.get('provenance',{}).get('candidate_id')==source['candidate_id']),None)
        if record and record['provenance']!=source:raise ValueError('Retained provenance differs from persisted assessment.')
    return evaluate(artifact)


def persist_outcomes(store,state,inputs,artifact,outcomes):
    request_id=artifact['request_id']
    attempt=next(r for r in state['semantic_requests'] if r['id']==request_id)
    for prepared in inputs['prepared_inputs']:
        cid=prepared['source']['candidate_id'];item=state['items'][cid]
        # Abort persistence of claims if the original evidence/context changed.
        source_now=semantic.prepare(store,item,inputs['_context'])
        if source_now!=prepared:raise ValueError('Source inputs changed; retained response remains available offline.')
        key=semantic.digest({'base_cache_key':prepared['cache_key'],'authorization':AUTHORIZATION,
            'contract_version':inputs['contract_version']})
        old=item.get('semantic_assessment')
        record={**outcomes[cid],'policy_version':semantic.POLICY,'validator_version':semantic.VALIDATOR_VERSION,
            'contract_version':inputs['contract_version'],'authorization':AUTHORIZATION,
            'cache_key':key,'base_cache_key':prepared['cache_key'],'context_sha256':prepared['context_sha256'],
            'content_sha256':item['content_sha256'],'request_id':request_id,'assessed_at':artifact['captured_at'],
            'model':artifact['model'],'provenance':prepared['source'],
            'project_context_provenance':inputs['_context'].get('provenance',{}),
            'category':outcomes[cid]['assessment']['category'] if outcomes[cid]['assessment'] else 'uncertain relevance',
            'label':'Nemotron semantic reassessment; provisional, exact quotations validated; suitability not verified.'
                if outcomes[cid]['status']=='validated' else 'Semantic reassessment failed validation; no project conclusion established.'}
        state.setdefault('semantic_cache',{})[key]=record
        state.setdefault('semantic_overrides',{})[prepared['cache_key']]=key
        if old:item.setdefault('semantic_history',[]).append(old)
        item['semantic_assessment']=record
        if record['status']=='validated':semantic.prepare_proposal(state,item,record)
    attempt.update(status='completed' if all(o['status']=='validated' for o in outcomes.values()) else 'failed_or_partial',
        finished_at=semantic.now(),model=artifact['model'],response_path=str((directory(store)/'response.json').relative_to(store.directory)),
        outcomes=[{'candidate_id':cid,'status':v['status'],'validation_failure':v['validation_failure']} for cid,v in outcomes.items()])
    state.setdefault('reassessments',[]).append({'policy_version':semantic.POLICY,'contract_version':semantic.CONTRACT_VERSION,
        'assessed_at':artifact['captured_at'],'authorization':AUTHORIZATION,'request_id':request_id,'candidate_count':len(outcomes),
        'reason':'Separately authorized semantic reassessment only; no new publication or source-content change.'})
    return store.save(state)


def run_once(store,token,context,requester=None,candidate_ids=CANDIDATES):
    requester=requester or (lambda token,prompt:semantic.analyzer.request_claims(token,prompt,
        max_tokens=MAX_TOKENS,max_response_bytes=semantic.MAX_RESPONSE_BYTES))
    folder=directory(store)
    with store.exclusive():
        state=store.read()
        if already_reserved(state,folder):return state
        if tuple(candidate_ids)!=CANDIDATES and store.root==discovery.memory.DEFAULT_MEMORY_ROOT:
            raise ValueError('Candidates do not match the explicit authorization.')
        inputs=preparation(store,context,candidate_ids)
        protected_directory(folder)
        request_id=str(uuid.uuid4())
        attempt={'id':request_id,'authorization':AUTHORIZATION,'status':'reserved','started_at':semantic.now(),
            'candidate_ids':list(candidate_ids),'contract_version':semantic.CONTRACT_VERSION,
            'max_requests':MAX_REQUESTS,'max_tokens':MAX_TOKENS,'timeout_seconds':semantic.analyzer.TIMEOUT_SECONDS,
            'max_response_bytes':semantic.MAX_RESPONSE_BYTES,'cache_keys':[p['cache_key'] for p in inputs['prepared_inputs']]}
        # Both durable guards precede the sole transport invocation. Any interruption consumes it.
        write_new(folder/'reservation.json',{**attempt,'input_sha256':semantic.digest(inputs)})
        write_new(folder/'inputs.json',inputs)
        state.setdefault('semantic_authorizations',{})[AUTHORIZATION]={'max_requests':1,'candidate_ids':list(candidate_ids),
            'reason':'User explicitly authorized exactly one additional request, no retries.'}
        state.setdefault('semantic_requests',[]).append(attempt)
        state=store.save(state)
        print('Controlled reassessment: request 1/1; two candidates; no retries.',flush=True)
        try:result=requester(token,inputs['messages'])
        except Exception:
            result={'ok':False,'data':{},'http_status':None}
        artifact=capture(result,token,inputs,request_id)
        write_new(folder/'response.json',artifact)
        outcomes=evaluate(artifact)
        write_new(folder/'validation.json',{'validator_version':semantic.VALIDATOR_VERSION,'outcomes':outcomes})
        return persist_outcomes(store,state,{**inputs,'_context':context},artifact,outcomes)


def summary(state):
    return {'authorization':AUTHORIZATION,'max_requests':1,
        'controlled':semantic.request_accounting(state,AUTHORIZATION),
        'original_milestone':semantic.request_accounting(state),
        'outcomes':[{'candidate_id':cid,'status':state['items'][cid].get('semantic_assessment',{}).get('status'),
            'category':state['items'][cid].get('semantic_assessment',{}).get('category')}
            for cid in CANDIDATES if cid in state['items']]}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true');parser.add_argument('--replay',action='store_true')
    args=parser.parse_args()
    if args.live and args.replay:raise SystemExit('Choose live or offline replay, never both.')
    store=discovery.Store();folder=directory(store);state=store.read()
    if args.replay:
        outcomes=replay_saved(store)
        protected_directory(folder)
        path=folder/('revalidation-'+semantic.VALIDATOR_VERSION+'.json')
        if not path.exists():write_new(path,{'validator_version':semantic.VALIDATOR_VERSION,'outcomes':outcomes})
        audit_path=folder/'independent-evidence-audit-v1.json'
        if not audit_path.exists():
            artifact=json.loads((folder/'response.json').read_text(encoding='utf-8'))
            write_new(audit_path,audit_response(artifact))
        print(json.dumps({'offline_replay':True,'new_requests':0,'outcomes':{k:v['status'] for k,v in outcomes.items()}}));return
    if already_reserved(state,folder):
        print(json.dumps(summary(state)))
        print('The one-request allowance is already reserved/used. No token requested; no model request sent.');return
    context=semantic.project_context(store.root)
    inputs=preparation(store,context)
    if not args.live:
        print(json.dumps({'preview_only':True,'authorization':AUTHORIZATION,'requests_used':0,
            'candidates':[{'id':p['source']['candidate_id'],'paragraph_ids':[q['passage_id'] for q in p['source']['passages']],
                'coverage':p['source']['coverage']} for p in inputs['prepared_inputs']],
            'prompt_characters':sum(len(m['content']) for m in inputs['messages']),'contract_version':semantic.CONTRACT_VERSION}));return
    if not sys.stdin.isatty():raise SystemExit('Use an interactive PowerShell console for hidden token entry; no echoed fallback.')
    try:
        with socket.create_connection(('127.0.0.1',8088),timeout=3):pass
    except OSError:raise SystemExit('Meterless is not listening; no request sent.') from None
    with warnings.catch_warnings():
        warnings.simplefilter('error',getpass.GetPassWarning)
        token=getpass.getpass('Meterless Runtime token (hidden; exactly one request, no retries): ').strip()
    if not token:raise SystemExit('No token supplied; no request sent.')
    try:state=run_once(store,token,context)
    finally:token=None
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'summary.json').write_text(json.dumps(summary(state),indent=2),encoding='utf-8')
    print(json.dumps(summary(state)),flush=True)


if __name__=='__main__':main()
