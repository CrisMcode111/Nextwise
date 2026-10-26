"""Audit existing discovery checkpoints and replay saved public bytes in isolation."""
from datetime import datetime
import json
from pathlib import Path
import shutil
import tempfile
import update_discovery as d

def main():
    store=d.Store();current=store.read()
    disk=json.loads((store.directory/'state.json').read_text(encoding='utf-8'))
    checkpoints=[json.loads(r['content'])['value'] for r in disk['records'] if r['source']=='nextwise:discovery']
    original=min(checkpoints,key=lambda s:s['version'])
    assert original['runs']==current['runs'] and original['baselines']==current['baselines']
    assert original['proposals']==current['proposals']
    for key,item in original['items'].items():
        updated=current['items'][key]
        assert item['relevance']==updated['relevance_history'][0]['assessment']
        assert {k:v for k,v in item.items() if k!='relevance'}=={k:v for k,v in updated.items() if k not in ('relevance','relevance_history')}
    assert all(d.sha((store.directory/s['snapshot_path']).read_bytes())==s['raw_sha256'] for r in current['runs'] for s in r['sources'])
    with tempfile.TemporaryDirectory(prefix='nextwise-saved-source-replay-') as tmp:
        copied=d.Store(tmp)
        shutil.copytree(store.directory,copied.directory)
        run=current['runs'][-1]
        sources={s['requested_url']:s for s in run['sources']}
        def fetch(url):
            source=sources[url]
            return {'raw':(copied.directory/source['snapshot_path']).read_bytes(),'final_url':source['final_url'],
                    'http_status':source['http_status'],'error':source['error']}
        replay=copied.run(fetcher=fetch,now=datetime.fromisoformat(run['retrieved_at']))
        assert not replay['runs'][-1]['events']
        assert replay['proposals']==current['proposals']
        assert replay['reassessments']==current['reassessments']
        assert all(replay['items'][k]['relevance_history']==v['relevance_history'] for k,v in current['items'].items())
    assert store.read()==current
    categories={c:sum(i['relevance']['category']==c for i in current['items'].values()) for c in {i['relevance']['category'] for i in current['items'].values()}}
    report={'policy_version':d.RELEVANCE_POLICY,'reassessed_candidates':len(current['items']),
        'categories':categories,'source_snapshots_hashes_preserved':True,'source_fields_revisions_and_first_seen_preserved':True,
        'baselines_runs_events_and_proposals_preserved':True,'earlier_assessments_preserved_exactly':True,
        'saved_source_replay':'Isolated copy of actual saved source bytes at original retrieval time; no public fetches',
        'unchanged_source_events':len(replay['runs'][-1]['events']),'reassessment_idempotent':store.reassess()==current,
        'live_proposal_count':len(current['proposals'])}
    out=d.ROOT/'reports/update_discovery/blocker_fixes';out.mkdir(parents=True,exist_ok=True)
    (out/'migration_audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))

if __name__=='__main__':main()
