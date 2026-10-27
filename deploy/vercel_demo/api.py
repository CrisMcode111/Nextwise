"""Public-only Vercel handler. No local service clients, secrets or disk reads."""
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler
import json
from pathlib import Path
import sys
import time
from urllib.parse import parse_qs, urlsplit
from urllib.error import HTTPError
from urllib.request import Request, HTTPRedirectHandler, ProxyHandler, build_opener

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'lib'))
import discovery_public as discovery
import search_public

# Written specifically for the public demo, not exported from private records.
PROJECT = {
    'name':'AI Raw Gourmet — public example',
    'objective':'Generate and adapt recipes and meal plans to user constraints.',
    'task':'Extract explicit user requirements from free text while preserving missing information.',
    'constraints':['Keep integration effort manageable.', 'Check costs and accuracy before adoption.'],
}
SOURCES = [
    {'id':'instructor', 'name':'Instructor', 'publisher':'Instructor documentation',
     'url':'https://python.useinstructor.com/', 'need_id':'structured_extraction',
     'limitations':['Structured output alone does not establish correct extraction. Model use would need separate cost and accuracy review.']},
    {'id':'pydantic', 'name':'Pydantic', 'publisher':'Pydantic documentation',
     'url':'https://docs.pydantic.dev/latest/', 'need_id':'constraint_validation',
     'limitations':['A schema-validation technology, not an AI model. Types cannot establish dietary safety or recover omitted requirements.']},
    {'id':'promptfoo', 'name':'promptfoo', 'publisher':'promptfoo documentation',
     'url':'https://www.promptfoo.dev/docs/intro/', 'need_id':'extraction_evaluation',
     'limitations':['Evaluation requires task-specific cases and assertions. No test or model runs in this demo.']},
]
MAX_BYTES = 2_000_000
SOCKET_TIMEOUT = 3
READ_DEADLINE = 5
CSP = "default-src 'self'; script-src 'self'; worker-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs): return None


def fetch_public(url):
    """One fixed HTTPS page; zero redirects/retries, proxies or authorization."""
    if url not in {source['url'] for source in SOURCES}:
        return {'raw':b'', 'error':'Source is outside the public demo scope.'}
    try:
        request = Request(url, headers={'User-Agent':'NextwisePublicDemo/1.0', 'Accept-Encoding':'identity'})
        started = time.monotonic()
        with build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=SOCKET_TIMEOUT) as response:
            if response.status != 200 or 'html' not in response.headers.get('Content-Type','').lower(): raise ValueError()
            if int(response.headers.get('Content-Length','0')) > MAX_BYTES: raise ValueError()
            raw = bytearray()
            while True:
                if time.monotonic()-started > READ_DEADLINE: raise ValueError()
                chunk = response.read1(min(65536, MAX_BYTES+1-len(raw)))
                if not chunk: break
                raw.extend(chunk)
                if len(raw)>MAX_BYTES: raise ValueError()
        return {'raw':bytes(raw), 'error':None}
    except HTTPError as error:
        error.close()
        return {'raw':b'', 'error':'Public source unavailable or redirected; no retry made.'}
    except Exception:
        return {'raw':b'', 'error':'Public source unavailable, redirected or over the demo limit; no retry made.'}


def demo_data():
    return {'mode':'public_demo', 'project':PROJECT, 'needs':discovery.project_needs(PROJECT),
        'sources':[{'id':s['id'], 'name':s['name'], 'url':s['url']} for s in SOURCES],
        'notice':'Public example context only. No private records, saved founder decisions or measured project results are included.',
        'search_sources':[{'id':key,'need_id':value[0],'name':search_public.BUSINESS_NEEDS.get(value[0],{}).get('label',value[0].replace('_',' ')),
            'url':'https://github.com/search'} for key,value in search_public.QUERIES.items()],
        'tavily_enabled':False, 'decision_storage':'browser_only'}


def discover_source(source_id):
    selected = next((s for s in SOURCES if s['id']==source_id), None)
    if selected is None: raise ValueError('Unknown demo source')
    result = discovery.catalog_tool_preview([], project=PROJECT, sources=[selected], fetcher=fetch_public,
        decision_history=(), now=datetime.now(timezone.utc))
    result['mode']='public_demo'
    result['source_id']=source_id
    result['notice']='Live public-page check against example project needs. Source claims and project benefits are unvalidated. Tavily and private services are disabled.'
    for candidate in result['candidates']: candidate['demo_source_id']=source_id
    return result


class handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass

    def respond(self, status, value):
        raw = json.dumps(value, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        for key,value in {'Content-Type':'application/json; charset=utf-8', 'Cache-Control':'no-store',
            'Content-Length':str(len(raw)), 'X-Content-Type-Options':'nosniff',
            'Referrer-Policy':'no-referrer', 'Content-Security-Policy':CSP}.items(): self.send_header(key,value)
        self.end_headers(); self.wfile.write(raw)

    def do_GET(self):
        route = urlsplit(self.path)
        query = parse_qs(route.query, keep_blank_values=True)
        # Vercel may preserve the original path and append the rewrite query.
        action = {'/api/demo':'demo', '/api/discover':'discover'}.get(route.path)
        actions = query.pop('route', [])
        if route.path in ('/api/index','/api/index.py'):
            action = actions[0] if len(actions)==1 else None
        elif actions and actions != [action]:
            action = None
        if self.headers.get('Sec-Fetch-Site') == 'cross-site':
            self.respond(403, {'message':'Open the public Nextwise demo directly.'}); return
        if action=='demo' and not query:
            self.respond(200, demo_data()); return
        if action=='discover' and set(query)=={'source'} and len(query['source'])==1:
            if query['source'][0] not in {s['id'] for s in SOURCES}:
                self.respond(400, {'message':'Choose a configured public demo source.'}); return
            try: self.respond(200, discover_source(query['source'][0]))
            except Exception: self.respond(503, {'message':'This public source check could not complete. No private fallback or retry was used.'})
            return
        if action=='discover' and set(query)=={'need'} and len(query['need'])==1:
            if query['need'][0] not in search_public.QUERIES:
                self.respond(400, {'message':'Choose a supported project need.'}); return
            self.respond(200, search_public.discover(query['need'][0])); return
        self.respond(404, {'message':'This route is not available in the public demo.'})

    def do_POST(self): self.respond(405, {'message':'Public demo decisions stay in your browser. Server writes are disabled.'})
    do_PUT = do_POST
    do_PATCH = do_POST
    do_DELETE = do_POST


if __name__=='__main__':
    raise SystemExit('Use the generated Vercel bundle; this module never starts a local/private app.')
