"""Read-only preservation/allowance/replay audit of the one completed reassessment."""
import copy
import json

import diagnose_semantic_discovery as archived
import reassess_discovery_once as once
import semantic_discovery as semantic
import update_discovery as discovery


def main():
    store=discovery.Store();before=archived.memory_hashes(store.root)
    state=store.read();context=archived.archived_context(store)
    baseline=json.loads((once.OUT/'baseline.json').read_text(encoding='utf-8'))
    assert semantic.digest(state['runs'])==baseline['runs_sha256']
    assert semantic.digest(state['baselines'])==baseline['baselines_sha256']
    for cid,item in state['items'].items():
        assert semantic.digest({k:item.get(k) for k in baseline['source_fields']})==baseline['source_fields_sha256'][cid]
        semantic.prepare(store,item,context)  # Verify original raw hashes and available passages.
    for key,value in baseline['semantic_cache_sha256'].items():assert semantic.digest(state['semantic_cache'][key])==value
    for rid,value in baseline['semantic_requests_sha256'].items():
        assert semantic.digest(next(r for r in state['semantic_requests'] if r['id']==rid))==value
    for pid,value in baseline['proposal_sha256'].items():
        assert semantic.digest(next(p for p in state['proposals'] if p['id']==pid))==value
    assert semantic.request_accounting(state)['requests_used']==3
    controlled=semantic.request_accounting(state,once.AUTHORIZATION)
    assert controlled['requests_used']==1 and controlled['confirmed_response_requests']==1
    outcomes=once.replay_saved(store)
    for cid,result in outcomes.items():
        current=state['items'][cid]['semantic_assessment']
        assert current['authorization']==once.AUTHORIZATION
        assert current['status']==result['status']
        assert current['validation_failure']==result['validation_failure']
        original=state['semantic_cache'][current['base_cache_key']]
        assert original in state['items'][cid]['semantic_history'] and original['status']=='failed'
    refreshed=copy.deepcopy(state)
    assert semantic.refresh(store,refreshed,context) is False and refreshed==state
    assert before==archived.memory_hashes(store.root)
    result={'authorization':once.AUTHORIZATION,'new_model_requests_sent_by_audit':0,
        'controlled':controlled,'original_milestone':semantic.request_accounting(state),
        'accepted':sum(o['status']=='validated' for o in outcomes.values()),
        'rejected':sum(o['status']=='failed' for o in outcomes.values()),
        'original_cache_request_proposal_hashes_preserved':True,'sources_baselines_publication_dates_and_events_unchanged':True,
        'genuine_defer_version_1':context['human_decision']['choice']=='Defer' and context['human_decision']['version']==1,
        'genuine_defer_record_sha256':context['human_decision']['record_sha256'],
        'read_only_audit_all_memory_files_unchanged':True,'unchanged_cache_refresh_no_reclassification':True,
        'validator_version':semantic.VALIDATOR_VERSION}
    (once.OUT/'preservation_and_replay_audit.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':main()
