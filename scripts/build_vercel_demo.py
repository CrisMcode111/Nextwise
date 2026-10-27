"""Build a standalone public-only upload folder. No network, secrets or private data reads."""
import argparse
import ast
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT=ROOT/'.nextwise-vercel-demo'
EXPECTED={'vercel.json','.vercelignore','.python-version','api/index.py',
    'lib/discovery_public.py','lib/collector_public.py','lib/identity_public.py','lib/search_public.py','lib/business_public.py',
    'public/index.html','public/app.js','public/style.css','public/demo.js','public/project.js',
    'public/pdfjs/pdf.mjs','public/pdfjs/pdf.worker.mjs','public/pdfjs/LICENSE','public/pdfjs/provenance.json'}


def python_parts(path, names):
    source=path.read_text(encoding='utf-8');tree=ast.parse(source);parts={}
    for node in tree.body:
        node_names=[node.name] if isinstance(node,(ast.FunctionDef,ast.ClassDef)) else (
            [target.id for target in node.targets if isinstance(target,ast.Name)] if isinstance(node,ast.Assign) else [])
        for name in node_names:
            if name in names:parts[name]=ast.get_source_segment(source,node)
    if set(parts)!=set(names):raise ValueError('Shared public discovery functions changed; review the build allowlist.')
    return '\n\n'.join(parts[name] for name in names)+'\n'


def js_between(source,start,end):
    if source.count(start)!=1 or source.count(end)!=1:raise ValueError('Shared UI boundaries changed; review the demo build.')
    return source[source.index(start):source.index(end)]


def build(output=DEFAULT_OUTPUT):
    output=Path(output).resolve()
    if output==ROOT or ROOT.is_relative_to(output):raise ValueError('Use a separate public-only output folder.')
    if output.exists():
        unexpected={str(p.relative_to(output)).replace('\\','/') for p in output.rglob('*') if p.is_file()
                    and '.vercel' not in p.relative_to(output).parts}-EXPECTED
        if unexpected:raise ValueError('Output contains unexpected files. Use an empty folder; nothing was removed.')
    js=(ROOT/'web/app.js').read_text(encoding='utf-8')
    shared="'use strict';\nconst $=selector=>document.querySelector(selector);\n"
    shared+=js_between(js,'function paintToolCandidates(', 'async function readDiscovery(')
    shared+=js_between(js,'function el(', 'function contextSentence(')
    # Do not ship the local app initialization, service endpoints or history renderers.
    index=(ROOT/'deploy/vercel_demo/index.html').read_text(encoding='utf-8')
    business=json.loads((ROOT/'deploy/vercel_demo/business_needs.json').read_text(encoding='utf-8'))
    guided=json.loads((ROOT/'deploy/vercel_demo/guided_opportunities.json').read_text(encoding='utf-8'))
    core='import hashlib\nimport re\nfrom datetime import datetime, timezone\nfrom urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode\nimport collector_public as collector\n\n'
    core+=python_parts(ROOT/'scripts/update_discovery.py', ['TOOL_LABEL','PROJECT_NEEDS','canonical','sha','tool_identity','project_needs','catalog_tool_preview'])
    collector='import re\nfrom html.parser import HTMLParser\n\n'+python_parts(ROOT/'scripts/collect_sources.py',['BLOCK_TAGS','SKIP_TAGS','PageExtractor','extract_page'])
    identity='import re\nimport ipaddress\nfrom urllib.parse import urlsplit\nimport discovery_public as d\n\n'+python_parts(ROOT/'scripts/tavily_discovery.py',['source_url','product_key'])
    csp="default-src 'self'; script-src 'self'; worker-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
    config={'version':2,'framework':None,'outputDirectory':'public',
        'functions':{'api/index.py':{'maxDuration':15,'includeFiles':'lib/**'}},
        'rewrites':[{'source':'/','destination':'/index.html'},
                    {'source':'/api/demo','destination':'/api/index?route=demo'},
                    {'source':'/api/discover','destination':'/api/index?route=discover'}],
        'headers':[{'source':'/(.*)','headers':[{'key':key,'value':value} for key,value in {
            'X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer',
            'Content-Security-Policy':csp,'X-Frame-Options':'DENY'}.items()]}]}
    files={'vercel.json':json.dumps(config,indent=2)+'\n', '.vercelignore':'.vercel\n**/__pycache__/**\n.env*\n',
        '.python-version':'3.12\n', 'api/index.py':(ROOT/'deploy/vercel_demo/api.py').read_text(encoding='utf-8'),
        'lib/discovery_public.py':core,'lib/collector_public.py':collector,'lib/identity_public.py':identity,
        'lib/search_public.py':(ROOT/'deploy/vercel_demo/search.py').read_text(encoding='utf-8'),
        'lib/business_public.py':'BUSINESS_NEEDS = '+repr(business)+'\n',
        'public/index.html':index,'public/app.js':shared,'public/style.css':(ROOT/'web/style.css').read_text(encoding='utf-8')+'\n'+(ROOT/'deploy/vercel_demo/style.css').read_text(encoding='utf-8'),
        'public/demo.js':'const GUIDED_SCENARIO='+json.dumps(guided,ensure_ascii=False)+';\n'+(ROOT/'deploy/vercel_demo/demo.js').read_text(encoding='utf-8'),
        'public/project.js':'const BUSINESS_NEEDS='+json.dumps(business,ensure_ascii=False)+';\n'+(ROOT/'deploy/vercel_demo/project.js').read_text(encoding='utf-8')}
    for name in ('pdf.mjs','pdf.worker.mjs','LICENSE','provenance.json'):
        files['public/pdfjs/'+name]=(ROOT/'deploy/vercel_demo/pdfjs'/name).read_text(encoding='utf-8')
    assert set(files)==EXPECTED
    for name,text in files.items():
        target=output/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(text.encode('utf-8'))
    return {'output':str(output),'files':sorted(files),'bytes':sum(len(text.encode('utf-8')) for text in files.values())}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=DEFAULT_OUTPUT)
    print(json.dumps(build(parser.parse_args().output),indent=2))
