"""Build the isolated online MVP bundle from the existing public demo assets."""
import json
from pathlib import Path
import tempfile
import build_vercel_demo as base

ROOT=Path(__file__).resolve().parents[1]
EXPECTED=base.EXPECTED | {'lib/online.py','lib/github_ingestion.py'}


def build(output=ROOT/'.nextwise-online-mvp'):
    output=Path(output).resolve()
    if output==ROOT or ROOT.is_relative_to(output): raise ValueError('Use a separate output folder.')
    if output.exists():
        existing={str(p.relative_to(output)).replace('\\','/') for p in output.rglob('*')
                  if p.is_file() and '.vercel' not in p.relative_to(output).parts}
        if existing-EXPECTED: raise ValueError('Output contains unexpected files; nothing was removed.')
    with tempfile.TemporaryDirectory(prefix='nextwise-public-build-') as temp:
        staging=Path(temp)/'bundle'; base.build(staging)
        files={str(p.relative_to(staging)).replace('\\','/'):p.read_bytes()
               for p in staging.rglob('*') if p.is_file()}
    config=json.loads(files['vercel.json'])
    config['functions']['api/index.py']['maxDuration']=60
    config['rewrites']=[{'source':'/','destination':'/index.html'},
                        {'source':'/api/discover','destination':'/api/index?route=discover'},
                        {'source':'/api/github','destination':'/api/index?route=github'}]
    files.update({'vercel.json':(json.dumps(config,indent=2)+'\n').encode(),
        'api/index.py':(ROOT/'deploy/vercel_demo/online_api.py').read_bytes(),
        'lib/online.py':(ROOT/'deploy/vercel_demo/online.py').read_bytes(),
        'lib/github_ingestion.py':(ROOT/'deploy/vercel_demo/github_ingestion.py').read_bytes(),
        'public/index.html':(ROOT/'deploy/vercel_demo/online.html').read_bytes(),
        'public/demo.js':(ROOT/'deploy/vercel_demo/online.js').read_bytes()})
    assert set(files)==EXPECTED
    for name,content in files.items():
        target=output/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(content)
    return {'output':str(output),'files':sorted(files)}


if __name__=='__main__':
    print(json.dumps(build(),indent=2))
