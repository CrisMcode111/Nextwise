"""Privately authorize the bounded semantic milestone: at most three requests, never retries."""
import argparse
import getpass
import json
import sys
import socket
import warnings
import semantic_discovery as semantic
import update_discovery as discovery

OUT=discovery.ROOT/'reports/update_discovery/semantic_assessment'

def report(state):
    OUT.mkdir(parents=True,exist_ok=True)
    value={'policy':semantic.POLICY,'authorization':semantic.AUTHORIZATION,'max_requests':semantic.MAX_REQUESTS,
        'requests':state.get('semantic_requests',[]),'candidate_count':len(state['items']),
        'outcomes':[{'candidate_id':i['id'],'status':i.get('semantic_assessment',{}).get('status'),
            'category':i.get('semantic_assessment',{}).get('category'),
            'existing_investigation':i.get('semantic_assessment',{}).get('provenance',{}).get('existing_investigation')}
            for i in state['items'].values()],
        'agent_proposals':sum(p.get('origin')=='agent' for p in state['proposals'])}
    (OUT/'requests.json').write_text(json.dumps(value,indent=2),encoding='utf-8')
    print(json.dumps({'requests_used':len(value['requests']),'agent_proposals':value['agent_proposals'],
        'validated':sum(o['status']=='validated' for o in value['outcomes'])}),flush=True)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--live',action='store_true');args=parser.parse_args()
    store=discovery.Store();context=semantic.project_context(store.root);state=store.read()
    prepared=[semantic.prepare(store,item,context) for item in state['items'].values()]
    if not args.live:
        print(json.dumps({'preview_only':True,'candidates':len(prepared),'batches':(len(prepared)+semantic.BATCH_SIZE-1)//semantic.BATCH_SIZE,
            'existing_investigation_sources':sum(p['source']['existing_investigation'] for p in prepared),
            'selected_paragraph_characters':[p['source']['coverage']['selected_characters'] for p in prepared],
            'maximum_requests':semantic.MAX_REQUESTS,'max_output_tokens_per_request':semantic.MAX_OUTPUT_TOKENS,
            'context_sha256':semantic.digest(context)}));return
    if all(p['cache_key'] in state.get('semantic_cache',{}) for p in prepared):
        report(state)
        print('All inputs are cached (including visible failures). No token requested and no model request sent.',flush=True)
        return
    spent={r['id'] for r in state.get('semantic_requests',[])} | {r['request_id'] for r in state.get('semantic_cache',{}).values() if r.get('request_id')}
    if len(spent)>=semantic.MAX_REQUESTS:
        report(state)
        print('Three-request authorization exhausted. No token requested and no model request sent.',flush=True)
        return
    if not sys.stdin.isatty():raise SystemExit('Use an interactive PowerShell console for private runtime-token entry; no echoed fallback.')
    try:
        with socket.create_connection(('127.0.0.1',8088),timeout=3):pass
    except OSError:raise SystemExit('Existing Meterless runtime is not listening on port 8088. No model request was sent.') from None
    with warnings.catch_warnings():
        warnings.simplefilter('error',getpass.GetPassWarning)
        token=getpass.getpass('Meterless Runtime token (hidden; at most 3 requests, no retries): ').strip()
    if not token:raise SystemExit('No token entered. No model request was sent.')
    try:
        state=semantic.run(store,token,context=context)
        report(state)
    finally:token=None

if __name__=='__main__':main()
