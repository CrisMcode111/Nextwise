"""Read-only semantic grounding, cache, source and context provenance audit. No requests."""
import json
import semantic_discovery as semantic
import update_discovery as discovery
import assess_discovery

def main():
    store=discovery.Store();state=store.read();context=semantic.project_context(store.root)
    raw=json.loads((store.directory/'state.json').read_text(encoding='utf-8'))
    original=min((json.loads(r['content'])['value'] for r in raw['records'] if r['source']=='nextwise:discovery'),key=lambda v:v['version'])
    assert state['runs']==original['runs'] and state['baselines']==original['baselines']
    source_fields=('id','title','url','source','text','publication_date','retrieved_at','first_seen','snapshot_path','raw_sha256','content_sha256','guids','revisions')
    validated=[];failed=[]
    for key,item in state['items'].items():
        assert all(item.get(k)==original['items'][key].get(k) for k in source_fields)
        assert item['relevance_history'][0]['assessment']==original['items'][key]['relevance']
        prepared=semantic.prepare(store,item,context)
        current=item['semantic_assessment']
        assert current['cache_key']==prepared['cache_key']
        assert current['context_sha256']==semantic.digest(context)
        assert current==state['semantic_cache'][prepared['cache_key']]
        if current['status']=='validated':
            semantic.validate(current['assessment'],prepared);validated.append(key)
        else:
            assert current['category']=='uncertain relevance' and current.get('error')
            failed.append(key)
    agent=[p for p in state['proposals'] if p.get('origin')=='agent']
    assert len(agent)==len(validated)
    assert all(p['human_approval'] is None and p['assessment_cache_key'] in state['semantic_cache'] for p in agent)
    assert {r['id'] for r in state['semantic_requests']}=={r['request_id'] for r in state['semantic_cache'].values() if r.get('request_id')}
    assert len(state['semantic_requests'])<=3
    for request in state['semantic_requests']:
        records=[r for r in state['semantic_cache'].values() if r.get('request_id')==request['id']]
        assert all(r.get('model')==request['model'] for r in records)
    # A pure requester trap verifies unchanged successes AND failures cannot call a model.
    def forbidden(*args):raise AssertionError('Unexpected model request during cache verification')
    replay=semantic.run(store,'',context,requester=forbidden,progress=lambda message:None)
    assert replay==state and store.read()==state
    result={'policy':semantic.POLICY,'candidates':len(state['items']),'validated':len(validated),'failed_uncertain':len(failed),
        'automatic_agent_proposals':len(agent),'actual_requests':len(state['semantic_requests']),
        'returned_models':list(dict.fromkeys(r['model']['returned_model'] for r in state['semantic_requests'])),
        'usage':{k:sum(r['model']['usage'].get(k,0) for r in state['semantic_requests']) for k in ('prompt_tokens','completion_tokens','total_tokens')},
        'sources_baselines_events_first_seen_and_revisions_unchanged':True,'earlier_rule_assessments_preserved_exactly':True,
        'exact_source_and_quote_validation_passed':True,'unchanged_cache_no_model_call':True,
        'project_context_sha256':semantic.digest(context),'project_context_provenance':context['provenance'],
        'genuine_defer_version_1_context':context['human_decision']['choice']=='Defer' and context['human_decision']['version']==1,
        'real_human_selections':len(state.get('proposal_selections',[]))}
    assess_discovery.OUT.mkdir(parents=True,exist_ok=True)
    (assess_discovery.OUT/'preservation_and_cache_audit.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('project_context_provenance',)}))

if __name__=='__main__':main()
