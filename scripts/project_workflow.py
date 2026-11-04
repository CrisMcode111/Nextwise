"""Project-scoped workflow over the existing discovery, validators and H-MEM.

Transports are explicit dependencies. Constructing or reading this workflow never
loads credentials or calls search/models. Project namespaces never use pilot data.
"""
import copy
from pathlib import Path
import re
import uuid

import opportunity_workflow as opportunities
import semantic_discovery as semantic
import tavily_discovery as tavily
import update_discovery as discovery


class WorkflowError(ValueError):
    pass


def require(value, message):
    if not value:
        raise WorkflowError(message)


def request_id(body):
    try:
        return str(uuid.UUID(body['request_id']))
    except (KeyError, ValueError, TypeError, AttributeError):
        raise WorkflowError('Supply a UUID request_id.') from None


class Projects:
    def __init__(self, memory_root, *, searcher=None, fetcher=None, assessor=None):
        self.directory = Path(memory_root).resolve() / 'projects'
        self.searcher, self.fetcher, self.assessor = searcher, fetcher, assessor

    def store(self, project_id):
        require(isinstance(project_id, str) and re.fullmatch(r'project-[a-f0-9]{32}', project_id),
                'Invalid project ID.')
        target = (self.directory / project_id).resolve()
        require(target.parent == self.directory, 'Invalid project directory.')
        return discovery.Store(target)

    def _read(self, store, project_id):
        require((store.directory / 'state.json').is_file(), 'Project not found.')
        state = store.read()
        require(state.get('schema') == 'nextwise.project-workflow.v1'
                and state.get('project', {}).get('id') == project_id, 'Project identity mismatch.')
        project = state['project']
        context = semantic.business_context(project['brief'], name=project['name'],
                    input_kind=project['input_kind'], sanitized=True)
        require(semantic.digest(context) == project['context_sha256'], 'Project input failed integrity checks.')
        opportunities.verify(state['briefings'])
        opportunities.verify(state['decisions'])
        return state

    def list(self):
        if not self.directory.exists():
            return []
        return [self.read(p.name)['project'] for p in sorted(self.directory.iterdir())
                if re.fullmatch(r'project-[a-f0-9]{32}', p.name)
                and (p / 'update-discovery/state.json').is_file()]

    def read(self, project_id):
        store = self.store(project_id)
        state = self._read(store, project_id)
        # Validate links on every reopen; these are never regenerated from pilot files.
        briefs = {b['id']: b for b in state['briefings']}
        for decision in state['decisions']:
            brief = briefs.get(decision['briefing_id'])
            require(brief and decision['briefing_sha256'] == brief['record_sha256']
                    and decision['project_id'] == project_id
                    and decision['candidate_id'] == brief['candidate_id'], 'Decision linkage failed integrity checks.')
        state['briefing_current'] = {}
        for brief in state['briefings']:
            try:
                self._assessment(store, state, brief['assessment_id'])
                state['briefing_current'][brief['id']] = True
            except (ValueError, OSError, KeyError):
                state['briefing_current'][brief['id']] = False
        return copy.deepcopy(state)

    def create(self, body):
        rid = request_id(body)
        context = semantic.business_context(body.get('brief'), name=body.get('name'),
                    input_kind=body.get('input_kind', 'text'), sanitized=body.get('reviewed_sanitized'))
        project_id = 'project-' + uuid.UUID(rid).hex
        store = self.store(project_id)
        with store.exclusive():
            if (store.directory / 'state.json').exists():
                state = self._read(store, project_id)
                require(state['project']['context_sha256'] == semantic.digest(context),
                        'Creation request ID belongs to different project input.')
                return state
            state = {'schema': 'nextwise.project-workflow.v1', 'version': 0,
                'project': {'id': project_id, 'name': context['profile']['name'],
                    'brief': context['profile']['objective'], 'input_kind': context['provenance']['input_kind'],
                    'context_sha256': semantic.digest(context), 'created_at': semantic.now()},
                'items': {}, 'runs': [], 'assessments': [], 'briefings': [], 'decisions': [], 'operations': {}}
            return store.save(state)

    def _assessment(self, store, state, assessment_id):
        record = next((r for r in state['assessments'] if r['id'] == assessment_id), None)
        require(record is not None, 'Validated assessment not found.')
        latest = next(r for r in reversed(state['assessments']) if r['candidate_id'] == record['candidate_id'])
        require(latest['id'] == record['id'], 'A newer assessment exists; prepare a current briefing.')
        item = state['items'].get(record['candidate_id'])
        require(item is not None, 'Source not found.')
        p = state['project']
        request = semantic.prepare_business_assessment(store, item, p['brief'], name=p['name'],
                    input_kind=p['input_kind'], sanitized=True)
        require(record['input_sha256'] == semantic.digest(request), 'Assessment evidence or context changed.')
        semantic.evaluate_business_response(json_dumps({'assessments': [record['assessment']]}), request)
        return record

    def act(self, project_id, action, body):
        require(action in ('discover', 'assess', 'brief', 'decide'), 'Unknown project action.')
        rid = request_id(body)
        store = self.store(project_id)
        require((store.directory / 'state.json').is_file(), 'Project not found.')
        with store.exclusive():
            state = self._read(store, project_id)
            fingerprint = semantic.digest({'action': action, 'body': body})
            previous = state['operations'].get(rid)
            if previous:
                require(previous['fingerprint'] == fingerprint, 'Request ID belongs to a different action.')
                require(previous['status'] == 'completed', 'Prior attempt did not complete; review saved history before a new attempt.')
                return state
            require(type(body.get('expected_version')) is int and body['expected_version'] == state['version'],
                    'Project changed; reopen its latest version.')
            if action == 'discover':
                require(callable(self.searcher) and callable(self.fetcher), 'Search and page transports are not enabled.')
            if action == 'assess':
                require(callable(self.assessor), 'Assessment transport is not enabled.')
            # Reserve before an external attempt. Interrupted or failed requests never retry silently.
            state['operations'][rid] = {'action': action, 'fingerprint': fingerprint, 'status': 'started'}
            state = store.save(state)
            try:
                getattr(self, '_' + action)(store, state, body, rid)
                state['operations'][rid]['status'] = 'completed'
            except Exception:
                # Publish only the attempt journal on failure, not partial assessments or decisions.
                state = self._read(store, project_id)
                state['operations'][rid]['status'] = 'failed'
                store.save(state)
                raise WorkflowError('Project action failed validation or transport; no result was accepted. Review saved history.') from None
            return store.save(state)

    def _discover(self, store, state, body, rid):
        query = body.get('query')
        require(isinstance(query, str) and 10 <= len(query.strip()) <= 500,
                'Supply reviewed public search terms of 10 to 500 characters.')
        results = self.searcher(query.strip())
        require(isinstance(results, list), 'Invalid search response.')
        run = {'id': rid, 'query': query.strip(), 'created_at': semantic.now(),
               'candidate_ids': [], 'search_result_count': min(len(results), tavily.RESULTS_PER_SEARCH),
               'label': 'Search results are leads; only saved page text is assessment evidence.'}
        seen = set()
        pages = 0
        for lead in results[:tavily.RESULTS_PER_SEARCH]:
            if pages >= tavily.MAX_SOURCE_PAGES:
                break
            try:
                url = tavily.source_url(lead['url'])
            except (KeyError, TypeError, ValueError):
                continue
            if url in seen:
                continue
            seen.add(url)
            pages += 1
            response = self.fetcher(url)
            raw = response.get('raw') if isinstance(response, dict) and not response.get('error') else None
            if not isinstance(raw, bytes) or not 1 <= len(raw) <= discovery.MAX_BYTES:
                continue
            text = semantic.html_extract.extract_readable_text(raw.decode('utf-8', errors='replace'))
            if len(text.strip()) < semantic.QUOTE_MIN:
                continue
            candidate_id = discovery.collector.stable_source_id(url)
            relative = f'runs/{rid}/{candidate_id}.html'
            target = store.directory / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as stream:
                stream.write(raw)
            item = {'id': candidate_id, 'title': str(lead.get('title') or url)[:200], 'url': url,
                'publication_date': None, 'retrieved_at': run['created_at'], 'source': 'tavily-page',
                'snapshot_path': relative, 'raw_sha256': discovery.sha(raw),
                'content_sha256': discovery.sha(text), 'kind': 'saved_page'}
            p = state['project']
            # Reject pages which cannot supply whole evidence passages before publishing.
            semantic.prepare_business_assessment(store, item, p['brief'], name=p['name'],
                                                input_kind=p['input_kind'], sanitized=True)
            state['items'][candidate_id] = item
            run['candidate_ids'].append(candidate_id)
        state['runs'].append(run)

    def _assess(self, store, state, body, rid):
        item = state['items'].get(body.get('candidate_id'))
        require(item is not None, 'Choose a saved source.')
        p = state['project']
        request = semantic.prepare_business_assessment(store, item, p['brief'], name=p['name'],
                    input_kind=p['input_kind'], sanitized=True)
        content = self.assessor(copy.deepcopy(request))
        require(isinstance(content, str) and len(content.encode('utf-8')) <= semantic.MAX_RESPONSE_BYTES,
                'Invalid assessment response.')
        result = semantic.evaluate_business_response(content, request)
        state['assessments'].append({'id': rid, 'candidate_id': item['id'],
            'input_sha256': semantic.digest(request), 'assessment': result['assessment'],
            'created_at': semantic.now(), 'validation': 'contract_and_source_quotes_checked'})

    def _brief(self, store, state, body, rid):
        record = self._assessment(store, state, body.get('assessment_id'))
        value = record['assessment']
        candidate_id = record['candidate_id']
        previous = next((r for r in reversed(state['briefings']) if r['candidate_id'] == candidate_id), None)
        choice = {'potential relevance': 'Test', 'low relevance': 'Reject', 'uncertain relevance': 'Defer'}[value['category']]
        state['briefings'].append(opportunities.seal({'id': rid, 'candidate_id': candidate_id,
            'project_id': state['project']['id'], 'assessment_id': record['id'],
            'version': previous['version'] + 1 if previous else 1,
            'previous_record_sha256': previous['record_sha256'] if previous else None,
            'title': state['items'][candidate_id]['title'], 'what_changed': value['source_observation'],
            'why_it_matters': value['project_need'], 'potential_value': value['application_hypothesis'],
            'supporting_evidence': copy.deepcopy(value['evidence']), 'risks': value['limitations'],
            'uncertainty': value['missing_information'], 'next_action': value['next_step'],
            'recommended_choice': choice, 'created_at': semantic.now(),
            'evidence_references': copy.deepcopy(state['items'][candidate_id]),
            'label': 'Contract-validated provisional briefing; publisher claims and project benefits remain unverified. Human review required.'}))

    def _decide(self, store, state, body, rid):
        require(body.get('explicit_action') == 'record_project_decision' and body.get('choice') in opportunities.CHOICES
                and isinstance(body.get('rationale'), str) and 1 <= len(body['rationale'].strip()) <= 8000
                and isinstance(body.get('next_action', ''), str) and len(body.get('next_action', '')) <= 4000,
                'Choose a human decision and provide its rationale.')
        brief = next((r for r in state['briefings'] if r['id'] == body.get('briefing_id')), None)
        require(brief and brief['record_sha256'] == body.get('briefing_sha256'), 'Briefing is missing or changed.')
        latest = next(r for r in reversed(state['briefings']) if r['candidate_id'] == brief['candidate_id'])
        require(latest['id'] == brief['id'], 'Review the latest briefing before deciding.')
        self._assessment(store, state, brief['assessment_id'])
        head = next((r for r in reversed(state['decisions']) if r['candidate_id'] == brief['candidate_id']), None)
        require('expected_head' in body and body['expected_head'] == (head['id'] if head else None),
                'A newer decision exists; review history before amending.')
        state['decisions'].append(opportunities.seal({'id': rid, 'candidate_id': brief['candidate_id'],
            'project_id': state['project']['id'], 'briefing_id': brief['id'],
            'briefing_sha256': brief['record_sha256'], 'version': head['version'] + 1 if head else 1,
            'previous_record_sha256': head['record_sha256'] if head else None, 'created_at': semantic.now(),
            'choice': body['choice'], 'rationale': body['rationale'].strip(), 'next_action': body.get('next_action', ''),
            'actor': 'local_human_user', 'boundary': 'Recorded choice only; no research, spending, model call or deployment is authorized.'}))


def json_dumps(value):
    import json
    return json.dumps(value, ensure_ascii=False)
