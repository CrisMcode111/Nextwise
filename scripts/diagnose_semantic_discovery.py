"""Read-only local semantic diagnosis/revalidation. No transport or source fetches."""
import copy
import base64
import json
from pathlib import Path

import assess_discovery
import semantic_discovery as semantic
import update_discovery as discovery

OUT=assess_discovery.OUT/'offline_diagnosis'


def archived_context(store):
    """Read original immutable envelopes without H-MEM's audited retrieval touches.

    This is an offline diagnostic reader, never a product persistence adapter.
    The complete reconstructed context must match every cached input hash.
    """
    raw=json.loads((store.root/semantic.INVESTIGATION/'state.json').read_text(encoding='utf-8'))
    records={r['id']:r for r in raw['records']}
    manifests=[r for r in records.values() if json.loads(r['content']).get('schema')=='nextwise.hmem.manifest.v1']
    record=max(manifests,key=lambda r:(r['timestamp'],int(r['id'][4:])))
    manifest=json.loads(record['content']);artifacts={}
    for kind,mid in manifest['artifact_ids'].items():
        envelope=json.loads(records[mid]['content'])
        data=base64.b64decode(envelope['bytes_base64'],validate=True)
        assert envelope['schema']=='nextwise.hmem.artifact.v1' and envelope['kind']==kind
        assert envelope['investigation_id']==semantic.INVESTIGATION
        assert discovery.sha(data)==envelope['sha256']==manifest['artifact_hashes'][kind]
        original=(discovery.ROOT/envelope['path']).resolve()
        assert original.is_relative_to(discovery.ROOT.resolve()) and discovery.sha(original.read_bytes())==envelope['sha256']
        artifacts[kind]=json.loads(data)
    decisions=[]
    for r in records.values():
        envelope=json.loads(r['content'])
        if envelope.get('schema')!='nextwise.human-decision-envelope.v1':continue
        d=envelope['decision']
        assert semantic.digest(d)==envelope['sha256']
        assert r['provenance']['origin']=='manual' and 'sha256:'+envelope['sha256'] in r['provenance']['refs']
        assert discovery.sha(records[d['manifest_id']]['content'])==d['manifest_sha256']
        for ref in d['evidence_references']:
            assert manifest['artifact_ids'][ref['kind']]==ref['memory_id']
            assert manifest['artifact_hashes'][ref['kind']]==ref['sha256']
        decisions.append({**d,'record_sha256':envelope['sha256'],'needs_review':False})
    context=semantic.context_from_verified_memory({'artifacts':artifacts,'manifest_id':record['id'],
        'artifact_hashes':manifest['artifact_hashes']},{'history':decisions})
    state=store.read()
    assert all(r['context_sha256']==semantic.digest(context) for r in state['semantic_cache'].values())
    return context


def replay(content,batch,metadata):
    """Record a separate validator outcome without updating the original cache."""
    try:
        if 'nemotron' not in metadata.get('returned_model','').lower():
            raise semantic.AssessmentError('returned_model','model','Nemotron routing was not confirmed.')
        parsed=semantic.parse_batch(content,batch)
    except semantic.AssessmentError as exc:
        return {p['source']['candidate_id']:{'status':'rejected','diagnostic':exc.diagnostic} for p in batch}
    result={}
    for p in batch:
        candidate=p['source']['candidate_id']
        try:
            semantic.validate(parsed[candidate],p)
            result[candidate]={'status':'validated'}
        except semantic.AssessmentError as exc:
            result[candidate]={'status':'rejected','diagnostic':exc.diagnostic}
    return result


def memory_hashes(root):
    return {str(p.relative_to(root)):discovery.sha(p.read_bytes()) for p in root.rglob('*') if p.is_file()}


def diagnose(store,context):
    state=store.read()
    prepared={i['id']:semantic.prepare(store,i,context) for i in state['items'].values()}
    candidates=[];revalidations=[];retained=0
    for request in state['semantic_requests']:
        batch=[prepared[c] for c in request['candidate_ids']]
        path=store.directory/'model-responses'/(request['id']+'.json')
        replayed={}
        if path.is_file():
            if path.stat().st_size>2*semantic.MAX_RESPONSE_BYTES:raise ValueError('Retained response artifact exceeds offline bound.')
            artifact=json.loads(path.read_text(encoding='utf-8'))
            if artifact.get('request_id',request['id'])!=request['id']:raise ValueError('Retained request identity mismatch.')
            content=artifact['content']
            if not isinstance(content,str) or len(content.encode('utf-8'))>semantic.MAX_RESPONSE_BYTES:
                raise ValueError('Retained content exceeds offline bound or has invalid type.')
            if artifact.get('content_sha256',discovery.sha(content))!=discovery.sha(content):raise ValueError('Retained content hash mismatch.')
            if artifact.get('prepared_inputs',batch)!=batch:raise ValueError('Retained prepared inputs differ from reconstructed inputs.')
            if artifact.get('project_context_sha256',semantic.digest(context))!=semantic.digest(context):raise ValueError('Retained context mismatch.')
            replayed=replay(content,batch,artifact['model']);retained+=1
        for p in batch:
            cid=p['source']['candidate_id'];item=state['items'][cid];record=item['semantic_assessment']
            assert record['provenance']==p['source'] and record['cache_key']==p['cache_key']
            assert record['context_sha256']==p['context_sha256']
            row={'candidate_id':cid,'title':item['title'],'request_id':request['id'],
                'original_status':record['status'],'original_error':record.get('error'),
                'original_validator_version':record.get('validator_version'),
                'original_diagnostic':record.get('validation_failure'),
                'snapshot_and_prepared_input_verified':True,'coverage':p['source']['coverage'],
                'full_response_retained':bool(replayed)}
            if cid in replayed:
                outcome={**replayed[cid],'basis':'retained_full_response'}
            elif record.get('assessment') is not None:
                # Only accepted fragments survive from the original live run.
                try:
                    semantic.validate(record['assessment'],p)
                    outcome={'status':'validated','basis':'persisted_accepted_assessment_fragment'}
                except semantic.AssessmentError as exc:
                    outcome={'status':'rejected','basis':'persisted_accepted_assessment_fragment','diagnostic':exc.diagnostic}
            else:
                outcome={'status':'unrecoverable','basis':'no_response_or_rejected_assessment_retained'}
            row['revalidation']=outcome
            candidates.append(row)
            revalidations.append({'candidate_id':cid,'request_id':request['id'],'validator_version':semantic.VALIDATOR_VERSION,
                'original_assessment_sha256':semantic.digest(record['assessment']) if record.get('assessment') is not None else None,
                'assessment_cache_key':p['cache_key'],'project_context_sha256':p['context_sha256'],
                'original_status':record['status'],**outcome})
    refreshed=copy.deepcopy(state)
    assert semantic.refresh(store,refreshed,context) is False and refreshed==state
    return {'validator_version':semantic.VALIDATOR_VERSION,'inspected_at_utc':semantic.now(),'new_model_requests':0,
        'accounting':assess_discovery.summary(state,cache_replay=True),
        'retained_full_responses':retained,'candidates':candidates,'revalidations':revalidations,
        'recovered_assessments':sum(r['original_status']!='validated' and r['status']=='validated' for r in revalidations),
        'accepted_fragments_revalidated':sum(r['basis']=='persisted_accepted_assessment_fragment' and r['status']=='validated' for r in revalidations),
        'unchanged_cache_refresh':True,'historical_journal_entries':state.get('semantic_journal_history',[])}


def main():
    store=discovery.Store();before=memory_hashes(store.root)
    context=archived_context(store)
    result=diagnose(store,context)
    after=memory_hashes(store.root)
    assert before==after,'Read-only diagnosis changed memory files.'
    result['all_hmem_files_unchanged']=True
    result['genuine_defer_version_1']={'choice':context['human_decision']['choice'],
        'version':context['human_decision']['version'],'record_sha256':context['human_decision']['record_sha256']}
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'diagnosis.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('new_model_requests','accounting','retained_full_responses',
        'recovered_assessments','accepted_fragments_revalidated','unchanged_cache_refresh','all_hmem_files_unchanged')}))


if __name__=='__main__':main()
