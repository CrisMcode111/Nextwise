"""Read-only checks of original artifacts, CSV snapshots, manifests and human choices."""
import hashlib
import json
from pathlib import Path
import export_zetaris as exporter
import integrate_zetaris as integration
import investigation_memory as memory

ROOT=Path(__file__).resolve().parents[1]
def digest(raw):return hashlib.sha256(raw).hexdigest()

def main():
    manifest=json.loads((integration.SNAPSHOT/'manifest.json').read_text(encoding='utf-8'))
    inputs=[{'path':v['path'],'matches':digest((ROOT/v['path']).read_bytes())==v['sha256']} for v in manifest['inputs']]
    csvs=[]
    for table,spec in manifest['tables'].items():
        raw=(integration.SNAPSHOT/(table+'.csv')).read_bytes()
        # Export manifest's exact CSV hash; do not query or rewrite registrations.
        csvs.append({'table':table,'matches':digest(raw)==spec['sha256']})
    state=json.loads((memory.DEFAULT_MEMORY_ROOT/'nemotron-lightning-requirements-extraction/state.json').read_text(encoding='utf-8'))
    imported=[];decisions=[];old_manifests=[]
    for record in state['records']:
        try:value=json.loads(record['content'])
        except (ValueError,TypeError):continue
        if value.get('schema')=='nextwise.hmem.artifact.v1':
            imported.append({'kind':value['kind'],'sha256':value['sha256'],'matches':digest((ROOT/value['path']).read_bytes())==value['sha256']})
        if value.get('schema')=='nextwise.hmem.manifest.v1':
            old_manifests.append({'memory_id':record['id'],'content_sha256':digest(record['content'].encode()),'artifact_hashes':value['artifact_hashes']})
        if value.get('schema')=='nextwise.human-decision-envelope.v1':
            d=value['decision']
            canonical=json.dumps(d,sort_keys=True,separators=(',',':'),ensure_ascii=False)
            decisions.append({'version':d['version'],'choice':d['choice'],'hash_matches':digest(canonical.encode())==value['sha256']})
    for manifest in old_manifests:
        manifest['artifact_hashes_match']=all(any(i['kind']==k and i['sha256']==v and i['matches'] for i in imported) for k,v in manifest.pop('artifact_hashes').items())
    result={'original_inputs':inputs,'csv_snapshots':csvs,'original_hmem_artifacts':imported,
            'old_manifests':old_manifests,'human_decision_metadata_only':decisions,
            'genuine_defer_version_1_preserved':any(d['version']==1 and d['choice']=='Defer' and d['hash_matches'] for d in decisions),
            'registrations':'No registration/upload/write workflow invoked; live authenticated SQL not available for this milestone check.'}
    path=ROOT/'reports/update_discovery/preservation.json'
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(result,indent=2),encoding='utf-8')
    assert all(i['matches'] for i in inputs+csvs+imported)
    assert result['genuine_defer_version_1_preserved'] and all(d['hash_matches'] for d in decisions)
    assert all(m['artifact_hashes_match'] for m in old_manifests)
    print('Original artifact/CSV hashes, old H-MEM artifact identities and genuine Defer Version 1 verified; no original writes.')

if __name__=='__main__':main()
