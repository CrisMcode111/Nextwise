"""Real saved source/context; explicitly SYNTHETIC response; temporary H-MEM only.

No listeners, sockets, model calls, public fetches, production bridge calls or
human-decision writes. Exercise the actual API handler through in-memory streams.
"""
import contextlib
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import nextwise_app as app
import reassess_opportunity_once as once
import semantic_discovery as semantic
from test_nextwise_app import FixtureClient


def api_get(root):
    """Actual GET /api/discovery with a fixture session, without any socket."""
    state = app.State(root)
    class Connection:
        output = bytearray()
        def makefile(self, *args):
            return io.BytesIO((f'GET /api/discovery HTTP/1.1\r\nHost: 127.0.0.1:8765\r\n'
                f'Cookie: nextwise={state.cookie}\r\nConnection: close\r\n\r\n').encode())
        def sendall(self, data): self.output.extend(data)
    connection = Connection()
    app.make_handler(state)(connection, ('127.0.0.1', 0), SimpleNamespace(server_port=8765))
    headers, body = bytes(connection.output).split(b'\r\n\r\n', 1)
    if not headers.startswith(b'HTTP/1.1 200 '):
        raise AssertionError('Isolated API fixture did not return HTTP 200.')
    return json.loads(body)


def record_digests(directory):
    raw = json.loads((directory / 'state.json').read_text(encoding='utf-8'))
    return [semantic.discovery.sha(r['content']) for r in raw['records']]


def build(root, invalid=False, *, staged=False):
    root = Path(root).resolve()
    if not root.is_relative_to(Path(tempfile.gettempdir()).resolve()):
        raise AssertionError('This fixture requires an OS temporary memory root.')
    production = semantic.memory.DEFAULT_MEMORY_ROOT.resolve()
    if root == production or root.is_relative_to(production):
        raise AssertionError('Production memory cannot be a fixture target.')
    preserved = {name: record_digests(production / name)
        for name in (semantic.INVESTIGATION, 'update-discovery')}
    for name in preserved:
        target = root / name
        target.mkdir(parents=True, exist_ok=False)
        for file in ('state.json', 'ledger.jsonl'):
            shutil.copyfile(production / name / file, target / file)
    # Only approved public snapshots; never copy private response directories.
    shutil.copytree(production / 'update-discovery/runs', root / 'update-discovery/runs')
    store = semantic.discovery.Store(root)
    context = semantic.project_context(root)  # Official verification on the COPY.
    before = store.read()
    original_records = record_digests(root / semantic.INVESTIGATION)
    calls = []

    def synthetic_request(token, messages):
        calls.append(messages)
        source = json.loads(messages[1]['content'])['untrusted_sources'][0]
        # A fixture expectation, NOT a live finding or a repaired rejected output.
        passage = next(p for p in source['passages'] if 'targeted tasks' in p['text'])
        value = {'candidate_id': source['candidate_id'], 'category': 'potential relevance',
            'project_need_id': 'decision_followup',
            'project_need': 'AI Raw Gourmet needs reliable extraction of explicit user requirements. A targeted model role is a possible architecture to examine, not evidence of extraction correctness.',
            'source_observation': 'The supplied NVIDIA passage describes smaller specialized models performing targeted tasks in a system of models; it does not report AI Raw Gourmet results.',
            'evidence': [{'source_id': source['source_id'], 'passage_id': passage['passage_id'], 'exact_quote': passage['text']}],
            'application_hypothesis': 'Hypothesis: a specialized model could handle the requirements-extraction step if it preserves explicit constraints and unknowns under agreed acceptance criteria. No benefit has been measured for this project.',
            'limitations': ['Publisher examples of targeted tasks do not establish requirements-extraction accuracy, integration compatibility, cost or speed for AI Raw Gourmet.'],
            'missing_information': ['The saved evaluator representation mismatch and omitted requirements need review; task acceptance criteria and a spending limit remain necessary.'],
            'priority': 'defer', 'priority_reason': 'The saved pilot exposed unresolved correctness and evaluation gaps, so review existing evidence before considering a new evaluation.',
            'investigation_question': 'Which saved omissions and evaluator ambiguities must be resolved before reconsidering the existing requirements-extraction investigation?',
            'next_step': 'Review the existing failed-case evidence and evaluation rules, specify acceptance criteria and a spending limit, and retain Defer; do not rerun the pilot.',
            'existing_findings_connection': 'The saved 1/4 pilot is synthetic and its evaluator has representation limitations. Genuine Defer Version 1 remains unchanged; this is an evidence-review continuation, not a duplicate investigation.'}
        if staged:
            plan = json.loads(messages[1]['content'])['extracted_publisher_claims']
            claim = next((c for c in plan['claims'] if 'targeted tasks' in c['exact_quote']), plan['claims'][0])
            value.update(source_observation=claim['exact_quote'],
                evidence=[{k: claim[k] for k in ('source_id', 'passage_id', 'exact_quote')}],
                project_need='AI Raw Gourmet needs reliable requirements extraction into structured data. The source describes model-workflow capabilities to examine in the existing investigation, not project-specific correctness.',
                application_hypothesis='Hypothesis: If task-specific evidence later supports compatibility and correctness, a requirements-extraction role could be considered within the described model workflow. Any project benefit is unverified.')
        if invalid: value['evidence'][0]['exact_quote'] = 'ISOLATED deliberately fabricated quotation, absent from the saved source.'
        return {'ok': True, 'http_status': 200, 'duration_seconds': 0,
            'data': {'fixture_only': True, 'model': once.EXPECTED_MODEL,
                'usage': {'prompt_tokens': 100, 'completion_tokens': 200, 'total_tokens': 300},
                'meterless': {'from_cache': False, 'receipt_id': 'ISOLATED-NOT-A-LIVE-RECEIPT',
                    'winning_route': {'provider': once.EXPECTED_PROVIDER, 'model': once.EXPECTED_MODEL}},
                'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps({'assessments': [value]})}}]}}

    # This separate ID exists only inside the temporary copy and patched module.
    # Every production reservation and prior allowance remains untouched.
    with patch.object(once, 'AUTHORIZATION', 'ISOLATED-OFFLINE-E2E-FIXTURE'), contextlib.redirect_stdout(io.StringIO()):
        report = once.run_once(store, 'ISOLATED-UNUSED-SECRET', context, synthetic_request, staged=staged)
        replay = once.replay(once.directory(store))
        folder = once.directory(store)
        retained = json.loads((folder / 'response.json').read_text(encoding='utf-8'))
        guarded = once.run_once(store, '', context, synthetic_request, staged=staged)
    reopened = store.read()
    api = api_get(root)
    snapshot = app.retrieve_memory(root)
    data = app.load_investigation(FixtureClient(snapshot), lambda: snapshot)
    history = semantic.memory.call_bridge({'operation': 'decision_history', 'investigation_id': semantic.INVESTIGATION,
        'memory_root': str(root)})
    assert len(calls) == 1 and guarded['new_requests_sent'] == 0
    assert record_digests(root / semantic.INVESTIGATION) == original_records
    assert all(record_digests(production / name) == hashes for name, hashes in preserved.items())
    assert all(reopened['semantic_cache'][key] == value for key, value in before['semantic_cache'].items())
    assert reopened['semantic_requests'][:-1] == before['semantic_requests']
    assert reopened['runs'] == before['runs'] and reopened['baselines'] == before['baselines']
    assert not reopened.get('opportunity_decisions')
    assert context['human_decision']['choice'] == 'Defer' and context['human_decision']['version'] == 1
    assert retained['data']['fixture_only'] is True
    return {'data': data, 'history': history, 'discovery': api,
        'report': report, 'replay': replay, 'before': before, 'reopened': reopened,
        'context': context, 'retained': retained}
