"""Offline project lifecycle: mocked providers, real H-MEM on temporary copies."""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import nextwise_app as app
import project_workflow as workflow
import runtime_config
import runtime_health
import project_adapters as adapters

PAGE = b'<html><title>CycleHelp</title><p>CycleHelp answers customer questions using a shop\'s published opening hours and repair policies.</p></html>'
URL = 'https://example.com/cyclehelp'


def hashes(folder):
    return {str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in folder.rglob('*') if p.is_file()}


def mocked_assessment(request):
    claim = request['staged_plan']['claims'][0]
    name = request['context']['profile']['name']
    return json.dumps({'assessments': [{
        'candidate_id': request['prepared']['source']['candidate_id'],
        'category': 'potential relevance', 'project_need_id': 'objective',
        'project_need': f'{name} needs to answer customer questions using its own public policies.',
        'source_observation': claim['exact_quote'],
        'evidence': [{k: claim[k] for k in ('source_id', 'passage_id', 'exact_quote')}],
        'application_hypothesis': 'Hypothesis: If suitable for the shop, this could help answer public policy questions; the benefit is unverified.',
        'limitations': ['Publisher claims only; suitability has not been evaluated.'],
        'missing_information': ['Pricing and accuracy on shop questions remain unknown.'],
        'priority': 'medium', 'priority_reason': 'Review a small invented question before considering adoption.',
        'investigation_question': 'Can it answer an invented opening-hours question from an approved policy?',
        'next_step': 'Review the public demonstration with invented questions before sharing business data.',
        'existing_findings_connection': None}]})


def dispatch(state, path, method='GET', body=None, authenticated=True, origin=True):
    class Connection:
        def __init__(self): self.output = bytearray()
        def makefile(self, *_):
            raw = json.dumps(body).encode() if body is not None else b''
            headers = [f'{method} {path} HTTP/1.1', 'Host: 127.0.0.1:8765',
                       'Content-Type: application/json', f'Content-Length: {len(raw)}', 'Connection: close']
            if authenticated: headers.append('Cookie: nextwise=' + state.cookie)
            if origin: headers.append('Origin: http://127.0.0.1:8765')
            return io.BytesIO(('\r\n'.join(headers) + '\r\n\r\n').encode() + raw)
        def sendall(self, data): self.output.extend(data)
    connection = Connection()
    app.make_handler(state)(connection, ('127.0.0.1', 0), SimpleNamespace(server_port=8765))
    headers, raw = bytes(connection.output).split(b'\r\n\r\n', 1)
    return int(headers.split()[1]), json.loads(raw)


class ProjectWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = ROOT / 'data/memory/hmem'
        cls.original_hashes = hashes(cls.original)

    @classmethod
    def tearDownClass(cls):
        if hashes(cls.original) != cls.original_hashes:
            raise AssertionError('Original H-MEM changed during project tests')

    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='nextwise-project-e2e-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / 'memory'
        # Start with an empty project namespace, retaining the pilot stores
        # for isolation checks. Private projects and one-off response envelopes
        # are not fixtures for the synthetic project lifecycle below.
        shutil.copytree(self.original, self.root,
                        ignore=shutil.ignore_patterns('projects', 'controlled-reassessments', 'final-controlled-assessment-*'))
        self.before_pilot = {name: hashes(self.root / name) for name in
                             ('nemotron-lightning-requirements-extraction', 'update-discovery')}
        self.addCleanup(self.assert_pilot_unchanged)
        self.addCleanup(patch.stopall)
        patch('socket.socket', side_effect=AssertionError('No network permitted')).start()
        patch.object(workflow.tavily, 'search', side_effect=AssertionError('No live search')).start()
        patch.object(workflow.tavily, 'public_page', side_effect=AssertionError('No live page fetch')).start()
        patch.object(workflow.semantic.analyzer, 'request_claims', side_effect=AssertionError('No live AI')).start()
        patch.object(workflow.semantic, 'project_context', side_effect=AssertionError('No pilot dependency')).start()
        actual_bridge = app.memory.call_bridge
        def copied_bridge(request):
            self.assertTrue(Path(request['memory_root']).resolve().is_relative_to(self.root.resolve()))
            return actual_bridge(request)
        patch.object(app.memory, 'call_bridge', side_effect=copied_bridge).start()
        self.search_calls = []
        self.model_calls = []
        def search(query):
            self.search_calls.append(query)
            return [{'title': 'CycleHelp', 'url': URL, 'content': 'UNTRUSTED SEARCH SNIPPET, NEVER ASSESSMENT EVIDENCE'}]
        def assess(request):
            self.model_calls.append(copy.deepcopy(request))
            return mocked_assessment(request)
        self.services = {'searcher': search, 'fetcher': lambda url: {'raw': PAGE, 'error': None}, 'assessor': assess}
        self.projects = workflow.Projects(self.root, **self.services)

    def assert_pilot_unchanged(self):
        for name, before in self.before_pilot.items():
            self.assertEqual(before, hashes(self.root / name))

    def create(self, name='Cycle repair'):
        return self.projects.create({'request_id': str(uuid.uuid4()), 'name': name,
            'brief': 'I run a bicycle shop and need to answer customer questions about our published hours and repair policies.',
            'reviewed_sanitized': True})

    def act(self, state, action, **fields):
        return self.projects.act(state['project']['id'], action, {'request_id': str(uuid.uuid4()),
                         'expected_version': state['version'], **fields})

    def briefing(self):
        state = self.create()
        state = self.act(state, 'discover', query='customer support public shop policies tools')
        candidate = next(iter(state['items']))
        state = self.act(state, 'assess', candidate_id=candidate)
        return self.act(state, 'brief', assessment_id=state['assessments'][-1]['id'])

    def decision_body(self, state, **fields):
        b = state['briefings'][-1]
        return {'request_id': str(uuid.uuid4()), 'expected_version': state['version'],
            'explicit_action': 'record_project_decision', 'briefing_id': b['id'],
            'briefing_sha256': b['record_sha256'], 'expected_head': None, 'choice': 'Test',
            'rationale': 'Review an invented question before deciding whether a trial is worthwhile.', **fields}

    def test_complete_lifecycle_api_and_reopen_without_pilot_or_network(self):
        state = app.State(self.root, project_services=self.services)
        state.project_only = True
        create = {'request_id': str(uuid.uuid4()), 'name': 'Cycle repair',
                  'brief': 'Our bicycle shop needs answers to customer questions about its public repair policies.',
                  'reviewed_sanitized': True}
        code, saved = dispatch(state, '/api/projects', 'POST', create)
        self.assertEqual(code, 200)
        project_id = saved['project']['id']
        for action in ('discover', 'assess', 'brief', 'decide'):
            fields = {'query': 'customer questions repair policies assistant'} if action == 'discover' else \
                     {'candidate_id': next(iter(saved['items']))} if action == 'assess' else \
                     {'assessment_id': saved['assessments'][-1]['id']} if action == 'brief' else self.decision_body(saved)
            fields = {'request_id': str(uuid.uuid4()), 'expected_version': saved['version'], **fields}
            code, saved = dispatch(state, f'/api/projects/{project_id}/{action}', 'POST', fields)
            self.assertEqual(code, 200, saved)
        restarted = app.State(self.root)
        code, reopened = dispatch(restarted, '/api/projects/' + project_id)
        self.assertEqual(code, 200)
        self.assertEqual(reopened['decisions'], saved['decisions'])
        self.assertEqual(reopened['decisions'][0]['version'], 1)
        self.assertTrue(reopened['briefing_current'][saved['briefings'][0]['id']])
        self.assertEqual(len(self.search_calls), 1)
        self.assertEqual(len(self.model_calls), 1)
        self.assertNotIn('UNTRUSTED SEARCH SNIPPET', json.dumps(self.model_calls))
        self.assertNotIn('Defer Version 1', self.model_calls[0]['messages'][0]['content'])
        self.assertNotIn('AI Raw Gourmet', json.dumps(reopened))
        persisted = json.loads((self.root/'projects'/project_id/'update-discovery/state.json').read_text())
        self.assertGreater(len(persisted['records']), 1)  # Real append-only H-MEM checkpoints.
        before = hashes(self.root)
        self.projects.read(project_id)
        self.assertEqual(before, hashes(self.root))

    def test_invalid_assessment_cannot_produce_briefing_or_decision(self):
        state = self.create()
        state = self.act(state, 'discover', query='customer policy assistant official information')
        def fabricated(request):
            content = json.loads(mocked_assessment(request))
            content['assessments'][0]['evidence'][0]['exact_quote'] = 'A fabricated claim about guaranteed business results.'
            return json.dumps(content)
        self.projects.assessor = fabricated
        with self.assertRaises(workflow.WorkflowError):
            self.act(state, 'assess', candidate_id=next(iter(state['items'])))
        reopened = self.projects.read(state['project']['id'])
        self.assertEqual(reopened['assessments'], [])
        self.assertEqual(reopened['briefings'], [])
        self.assertEqual(reopened['decisions'], [])
        self.assertEqual(list(reopened['operations'].values())[-1]['status'], 'failed')

    def test_configured_adapters_lifecycle_approval_limits_and_restart(self):
        env = {'NEXTWISE_PROJECT_PROVIDERS_ENABLED': 'true',
               'NEXTWISE_PROJECT_SEARCH_LIMIT': '1', 'NEXTWISE_PROJECT_ASSESSMENT_LIMIT': '2'}
        env = {**{k: v for k, v in os.environ.items() if not k.startswith(('NEXTWISE_', 'TAVILY_'))}, **env}
        def model(token, messages, **options):
            request = self.model_calls[-1]
            self.assertEqual(options['endpoint'], 'http://127.0.0.1:8088/v1/chat/completions')
            self.assertNotIn('Defer Version 1', json.dumps(options['response_schema']))
            self.assertNotIn('1/4', json.dumps(options['response_schema']))
            self.assertEqual(options['max_response_bytes'], workflow.semantic.MAX_RESPONSE_BYTES)
            # The transport returns generation claim IDs; the existing adapter
            # materializes exact quotations before workflow validation.
            generated = json.loads(mocked_assessment(request))
            value = generated['assessments'][0]
            del value['source_observation'], value['evidence']
            claim_id = request['staged_plan']['claims'][0]['passage_id']
            value.update(observation_claim_id=claim_id, evidence_claim_ids=[claim_id])
            value['missing_information'].extend(adapters.output.UNKNOWNS)
            return {'ok': True, 'http_status': 200, 'data': {'choices': [{'finish_reason': 'stop',
                'message': {'role': 'assistant', 'content': json.dumps(generated)}}]}}
        actual_assess = adapters.assess
        def capture(request):
            self.model_calls.append(copy.deepcopy(request))
            return actual_assess(request)
        with patch.dict(os.environ, env, clear=True), \
             patch.object(adapters.config, 'secret', return_value='synthetic-test-only') as secrets, \
             patch.object(adapters.tavily, 'search', return_value=[{'url': URL, 'title': 'CycleHelp'}]) as search, \
             patch.object(adapters.tavily, 'public_page', return_value={'raw': PAGE}) as fetch, \
             patch.object(adapters.analyzer, 'request_claims', side_effect=model) as model_call:
            backend = app.State(self.root)
            secrets.assert_not_called(); search.assert_not_called(); model_call.assert_not_called()
            self.projects = backend.projects
            self.projects.assessor = capture
            state = self.create()
            before = hashes(self.root)
            with self.assertRaises(workflow.WorkflowError):
                self.act(state, 'discover', query='public policy support tools')
            self.assertEqual(before, hashes(self.root)); secrets.assert_not_called()
            state = self.act(state, 'discover', query='public policy support tools', authorize_external_request=True)
            candidate = next(iter(state['items']))
            state = self.act(state, 'assess', candidate_id=candidate, authorize_external_request=True)
            state = self.act(state, 'brief', assessment_id=state['assessments'][-1]['id'])
            self.assertEqual(state['decisions'], [])  # A model result never approves itself.
            state = self.projects.act(state['project']['id'], 'decide', self.decision_body(state))
            self.assertEqual(search.call_count, 1); self.assertEqual(fetch.call_count, 1)
            self.assertEqual(model_call.call_count, 1)
            # Default startup wiring and persisted limits survive a backend restart.
            self.projects = app.State(self.root).projects
            self.assertEqual(self.projects.read(state['project']['id'])['decisions'], state['decisions'])
            with self.assertRaises(workflow.WorkflowError):
                self.act(state, 'discover', query='another public support query', authorize_external_request=True)
            self.assertEqual(search.call_count, 1)
            model_call.return_value = None
            model_call.side_effect = RuntimeError('synthetic-test-only')
            body = {'request_id': str(uuid.uuid4()), 'expected_version': state['version'],
                    'candidate_id': candidate, 'authorize_external_request': True}
            with self.assertRaises(workflow.WorkflowError) as error:
                self.projects.act(state['project']['id'], 'assess', body)
            self.assertNotIn('synthetic-test-only', str(error.exception))
            state = app.State(self.root).projects.read(state['project']['id'])
            with self.assertRaises(workflow.WorkflowError):
                self.act(state, 'assess', candidate_id=candidate, authorize_external_request=True)
            self.assertEqual(model_call.call_count, 2)  # Failed attempts consume the allowance too.
            self.assertEqual(len(state['assessments']), 1)
            for path in (self.root/'projects').rglob('*'):
                if path.is_file(): self.assertNotIn(b'synthetic-test-only', path.read_bytes())

    def test_snapshot_tampering_blocks_decision_and_marks_briefing_stale(self):
        state = self.briefing()
        item = next(iter(state['items'].values()))
        snapshot = self.projects.store(state['project']['id']).directory / item['snapshot_path']
        snapshot.write_bytes(b'<p>Different content with a sufficiently long paragraph.</p>')
        with self.assertRaises(workflow.WorkflowError):
            self.projects.act(state['project']['id'], 'decide', self.decision_body(state))
        reopened = self.projects.read(state['project']['id'])
        self.assertFalse(reopened['briefing_current'][state['briefings'][0]['id']])
        self.assertEqual(reopened['decisions'], [])

    def test_decisions_retry_amend_and_conflict_preserve_history(self):
        state = self.briefing()
        body = self.decision_body(state)
        first = self.projects.act(state['project']['id'], 'decide', body)
        retry = self.projects.act(state['project']['id'], 'decide', body)
        self.assertEqual(first, retry)
        with self.assertRaises(workflow.WorkflowError):
            self.projects.act(state['project']['id'], 'decide', {**body, 'choice': 'Adopt'})
        stale = self.decision_body(first, expected_head=None)
        with self.assertRaises(workflow.WorkflowError):
            self.projects.act(state['project']['id'], 'decide', stale)
        latest = self.projects.read(state['project']['id'])
        amended = self.projects.act(state['project']['id'], 'decide', self.decision_body(latest,
            expected_head=first['decisions'][0]['id'], choice='Defer'))
        self.assertEqual([d['version'] for d in amended['decisions']], [1, 2])
        self.assertEqual(amended['decisions'][1]['previous_record_sha256'], first['decisions'][0]['record_sha256'])

    def test_projects_are_isolated_and_input_requires_review(self):
        a = self.briefing()
        b = self.create('Another shop')
        self.assertEqual(self.projects.read(b['project']['id'])['items'], {})
        body = self.decision_body(a, expected_version=b['version'])
        with self.assertRaises(workflow.WorkflowError):
            self.projects.act(b['project']['id'], 'decide', body)
        self.assertEqual(self.projects.read(b['project']['id'])['decisions'], [])
        for project_id in ('../update-discovery', 'nemotron-lightning-requirements-extraction', 'project-'+'a'*32+'/..'):
            with self.assertRaises(workflow.WorkflowError): self.projects.read(project_id)
        with self.assertRaises(ValueError):
            self.projects.create({'request_id': str(uuid.uuid4()), 'name': 'Shop', 'brief': 'An unreviewed private brief.'})

    def test_disabled_transports_and_failed_requests_never_retry_automatically(self):
        state = self.create()
        disabled = workflow.Projects(self.root)
        body = {'request_id': str(uuid.uuid4()), 'expected_version': state['version'], 'query': 'public policies help'}
        before = hashes(self.root)
        with self.assertRaises(workflow.WorkflowError): disabled.act(state['project']['id'], 'discover', body)
        self.assertEqual(before, hashes(self.root))
        def fail(query):
            self.search_calls.append(query)
            raise RuntimeError('Synthetic provider failure; contents must not be returned')
        self.projects.searcher = fail
        for _ in range(2):
            with self.assertRaises(workflow.WorkflowError): self.projects.act(state['project']['id'], 'discover', body)
        self.assertEqual(len(self.search_calls), 1)

    def test_api_session_origin_and_project_mode_prevent_pilot_actions(self):
        state = app.State(self.root, project_services=self.services)
        state.project_only = True
        body = {'request_id': str(uuid.uuid4()), 'name': 'Shop', 'brief': 'Our shop needs policy support.', 'reviewed_sanitized': True}
        self.assertEqual(dispatch(state, '/api/projects', 'POST', body, authenticated=False)[0], 401)
        self.assertEqual(dispatch(state, '/api/projects', 'POST', body, origin=False)[0], 403)
        self.assertEqual(dispatch(state, '/api/load', 'POST', {})[0], 404)
        self.assertEqual(dispatch(state, '/api/discovery')[0], 404)
        self.assertFalse((self.root/'projects').exists())

    def test_project_startup_has_no_pilot_credential_or_memory_requirements(self):
        config = runtime_config.settings()
        with patch('runtime_health.subprocess.run', return_value=SimpleNamespace(stdout=b'v24.22.2\n')), \
             patch.object(app.integration, 'read_snapshot', side_effect=AssertionError('No pilot read')), \
             patch('runtime_health.secret', side_effect=AssertionError('No credential read')):
            result = runtime_health.check_dependencies(config, project_only=True)
        self.assertTrue(result['ready'])
        self.assertEqual([c['name'] for c in result['checks']], ['python', 'node_hmem_runtime', 'hmem_vendor'])
        with patch.object(runtime_health, 'check_dependencies', return_value={'ready': True}) as health, \
             patch.object(runtime_config, 'secret', side_effect=AssertionError('No credential read')), \
             patch.object(app, 'LocalHTTPServer') as server, patch.object(app.getpass, 'getpass') as prompt:
            server.return_value.serve_forever.side_effect = KeyboardInterrupt
            self.assertEqual(app.main(['--projects']), 0)
            self.assertTrue(health.call_args.kwargs['project_only'])
            prompt.assert_not_called()


class ProjectPageTests(unittest.TestCase):
    def test_provider_confirmation_is_required_before_post(self):
        program = r'''
const fs=require('fs'), vm=require('vm'), assert=require('node:assert/strict');
const calls=[], notices=[];
let approved=false;
const context=vm.createContext({crypto:{randomUUID:()=>'test-request'},
  document:{querySelector:()=>({replaceChildren(){},setAttribute(){}})},
  window:{confirm:message=>{notices.push(message);return approved;}},
  fetch:async(path, options)=>{
    calls.push({path,options});
    return {ok:true,json:async()=>({projects:[],transports:{},project:{id:'project'}})};
  }});
vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),context);
(async()=>{
  await new Promise(resolve=>setImmediate(resolve)); calls.length=0;
  await vm.runInContext(`(async()=>{
    project={project:{id:'project'},version:0}; render=()=>{};
    await mutate('discover',{query:'public query'});
    await mutate('assess',{candidate_id:'source'});
  })()`,context);
  assert.equal(calls.length,0); assert.equal(notices.length,2);
  approved=true;
  await vm.runInContext(`mutate('assess',{candidate_id:'source'})`,context);
  const posts=calls.filter(call=>call.options?.method==='POST');
  assert.equal(posts.length,1);
  assert.equal(JSON.parse(posts[0].options.body).authorize_external_request,true);
  assert.match(notices.at(-1),/project brief and saved public evidence/);
})().catch(error=>{console.error(error);process.exitCode=1;});
'''
        result = subprocess.run(['node', '-e', program, str(ROOT/'web/projects.js')],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_saved_decision_is_not_transferred_to_a_new_briefing(self):
        program = r'''
const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
class Element {
  constructor() { this.children = []; this.textContent = ''; }
  append(n) { this.children.push(n); }
  replaceChildren() { this.children = []; }
  setAttribute() {}
}
const elements = new Map();
const document = {createElement: () => new Element(), querySelector: selector => {
  if (!elements.has(selector)) elements.set(selector, new Element());
  return elements.get(selector);
}};
const context = vm.createContext({document, crypto:{randomUUID:()=>'test-request'},
  fetch:path=>{assert.equal(path,'/api/projects');return new Promise(()=>{});}});
vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), context);
vm.runInContext(`
const base = {candidate_id:'source', title:'Saved source', label:'Provisional', what_changed:'Publisher claim',
  why_it_matters:'Project need', recommended_choice:'Test', risks:[], uncertainty:[], supporting_evidence:[]};
project = {project:{id:'project',name:'Shop',brief:'Reviewed project'}, items:{}, assessments:[],
  briefings:[{...base,id:'old'},{...base,id:'new'}], briefing_current:{old:true,new:true}, operations:{},
  decisions:[{id:'decision',briefing_id:'old',candidate_id:'source',version:1,choice:'Defer',rationale:'Earlier reasoning'}]};
render();`, context);
const rows = elements.get('#briefings').children;
const text = row => row.textContent+' '+row.children.map(text).join(' ');
assert.match(text(rows[0]), /Human decision Version 1: Defer/);
assert.doesNotMatch(text(rows[1]), /Human decision Version 1: Defer/);
assert.match(text(rows[1]), /belongs to another briefing/);
assert.match(text(rows[1]), /awaiting your decision/);
'''
        result = subprocess.run(['node', '-e', program, str(ROOT/'web/projects.js')],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_backend_selection_is_authoritative_and_refreshed_after_actions(self):
        program = r'''
const fs=require('node:fs'), vm=require('node:vm'), assert=require('node:assert/strict');
class Element {
  constructor(){this.children=[];this.textContent='';}
  append(n){this.children.push(n);} replaceChildren(){this.children=[];} setAttribute(){}
}
const elements=new Map(), calls=[];
const context=vm.createContext({crypto:{randomUUID:()=>'request-test'},
  document:{createElement:()=>new Element(),querySelector:s=>{
    if(!elements.has(s))elements.set(s,new Element());return elements.get(s);
  }}, fetch:()=>new Promise(()=>{})});
vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),context);
vm.runInContext(`
project={project:{id:'project',name:'Policy project',brief:'Review public policy answers'},version:7,
  items:{},assessments:[],briefings:[],decisions:[],operations:{},
  opportunity_selections:[{id:'archived'}],selected_opportunities:[]};render();`,context);
assert.equal(elements.get('#opportunities').children.length,0);
vm.runInContext(`project.selected_opportunities=[{id:'current',title:'Saved title',project_need:'Saved need'}];render();`,context);
assert.equal(elements.get('#opportunities').children.length,1);
const text=n=>n.textContent+' '+n.children.map(text).join(' ');
assert.match(text(elements.get('#opportunities')),/Saved need/);
context.fetch=async(path,options={})=>{calls.push({path,options});return {ok:true,json:async()=>
  options.method==='POST'?{project:{id:'project'},selected_opportunities:[{id:'must-not-use-post'}]}:
  {project:{id:'project',name:'Policy project',brief:'Review public policy answers'},version:8,
   items:{},assessments:[],briefings:[],decisions:[],operations:{},selected_opportunities:[]}};};
(async()=>{
  await vm.runInContext("openProject('project')",context);
  assert.equal(elements.get('#opportunities').children.length,0);
  vm.runInContext("project.selected_opportunities=[{id:'current'}];render()",context);
  await vm.runInContext("mutate('brief',{assessment_id:'saved'})",context);
  assert.equal(elements.get('#opportunities').children.length,0);
  assert.deepEqual(calls.map(c=>c.options.method||'GET'),['GET','POST','GET']);
  const body=JSON.parse(calls[1].options.body);
  assert.equal(body.expected_version,8);assert.equal(body.request_id,'request-test');
})().catch(e=>{console.error(e);process.exitCode=1;});
'''
        result = subprocess.run(['node', '-e', program, str(ROOT/'web/projects.js')],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__': unittest.main()
