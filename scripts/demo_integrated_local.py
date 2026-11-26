"""Offline integrated demo with deterministic transports and isolated H-MEM."""
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from test_project_selection import wire, PAGE
import nextwise_app

memory = Path(os.environ.get('NEXTWISE_DEMO_MEMORY', ROOT / 'reports' / 'integrated_demo' / 'memory')).resolve()
port = int(os.environ.get('NEXTWISE_DEMO_PORT', '8771'))
def search(query, *, max_results=5):
    return [{'title':'PolicyHelp', 'url':'https://example.com/policyhelp'}][:max_results]
def fetch(url):
    return {'raw': PAGE, 'error':None}
def assess(request):
    if request['context']['profile']['name'] == 'Clinic rejected':
        return '{}'
    return json.dumps({'assessments':[wire(request)]})

state = nextwise_app.State(memory, project_services={'searcher':search, 'fetcher':fetch,
    'assessor':assess, 'external_limits':{'discover':2, 'assess':2}})
state.project_only = True
server = nextwise_app.LocalHTTPServer(('127.0.0.1', port), nextwise_app.make_handler(state))
server.daemon_threads = True
print(f'Offline isolated demo: http://127.0.0.1:{port}/projects', flush=True)
server.serve_forever()
