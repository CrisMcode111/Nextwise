"""Separately authorized ONE saved Nemotron candidate, ONE attempt, no retries.

Failure is retained privately, never promoted into the discovery assessment cache.
No source retrieval, human decision writes or original-investigation writes.
"""
import argparse
import copy
import getpass
import json
from pathlib import Path
import re
import socket
import sys
import uuid
import warnings

import opportunity_workflow as workflow
import reassess_discovery_once as retained
import semantic_discovery as semantic
import update_discovery as discovery

AUTHORIZATION = 'opportunity-e2e-nemotron-20261026-v1'
CANDIDATE = '9428cc2bc3c996d8505a0fdf'
EXPECTED_MODEL = 'nvidia/nemotron-3.5-lightning-30b-a3b'
EXPECTED_PROVIDER = 'nvidia'
MAX_TOKENS = 4000


def directory(store):
    return store.directory / 'controlled-reassessments' / AUTHORIZATION


def used(state, folder):
    return ((folder / 'reservation.json').exists()
            or any(r.get('authorization') == AUTHORIZATION for r in state.get('semantic_requests', []))
            or any(r.get('authorization') == AUTHORIZATION for r in state.get('semantic_cache', {}).values()))


def preparation(store, state, context, *, staged=False):
    item = state['items'][CANDIDATE]
    prepared = semantic.prepare(store, item, context)
    if not prepared['source']['existing_investigation']:
        raise ValueError('Registered existing-investigation source identity was not confirmed.')
    messages = semantic.messages([prepared], context)
    stage_plan = None
    if staged:
        import staged_opportunity as stages
        stage_plan = stages.extract(prepared, context)
        messages = stages.messages(prepared, context, stage_plan)
    if sum(len(m['content']) for m in messages) > 100_000:
        raise ValueError('Prompt exceeds the approved input bound.')
    return {**({'staged_plan': stage_plan} if staged else {}),
        'prepared_inputs': [prepared], 'messages': messages, 'context_sha256': semantic.digest(context),
        'contract_version': semantic.CONTRACT_VERSION, 'validator_version': semantic.VALIDATOR_VERSION,
        'output_contract': semantic.output_contract([prepared]), 'max_output_tokens': MAX_TOKENS,
        'max_response_bytes': semantic.MAX_RESPONSE_BYTES, 'timeout_seconds': semantic.analyzer.TIMEOUT_SECONDS}


def evaluate(artifact):
    data = artifact.get('data') or {}
    receipt = data.get('meterless') if isinstance(data.get('meterless'), dict) else {}
    route = receipt.get('winning_route') if isinstance(receipt.get('winning_route'), dict) else {}
    failure = None
    if artifact.get('transport_failure') or artifact['model'].get('http_status') != 200:
        failure = 'transport'
    elif (data.get('model') != EXPECTED_MODEL or route.get('model') != EXPECTED_MODEL
          or route.get('provider') != EXPECTED_PROVIDER):
        failure = 'model_route'
    elif receipt.get('from_cache') is not False:
        failure = 'cache_status'
    elif artifact.get('finish_reason') != 'stop':
        failure = 'finish_reason'
    if failure:
        return {'status': 'failed', 'assessment': None, 'error': 'Controlled request failed acceptance checks.',
            'validation_failure': {'validator_version': semantic.VALIDATOR_VERSION, 'code': failure}}
    outcome = retained.evaluate(artifact)[CANDIDATE]
    if outcome['status'] == 'validated' and 'staged_plan' in artifact:
        import staged_opportunity as stages
        try:
            context = json.loads(artifact['messages'][1]['content'])['approved_project_context']
            stages.validate(outcome['assessment'], artifact['prepared_inputs'][0], context, artifact['staged_plan'])
        except semantic.AssessmentError as error:
            return {'status': 'failed', 'assessment': None, 'error': str(error), 'validation_failure': error.diagnostic}
        except (ValueError, KeyError, TypeError):
            return {'status': 'failed', 'assessment': None, 'error': 'Staged input identity could not be verified.',
                'validation_failure': {'validator_version': semantic.VALIDATOR_VERSION, 'code': 'staged_inputs'}}
    return outcome


def replay(folder):
    """No store access or writes. Revalidate the exact captured inputs and response."""
    inputs = json.loads((folder / 'inputs.json').read_text(encoding='utf-8'))
    reservation = json.loads((folder / 'reservation.json').read_text(encoding='utf-8'))
    artifact = json.loads((folder / 'response.json').read_text(encoding='utf-8'))
    if (semantic.digest(inputs) != reservation['input_sha256'] or artifact['request_id'] != reservation['id']
            or artifact['authorization'] != AUTHORIZATION or any(artifact.get(k) != v for k, v in inputs.items())):
        raise ValueError('Retained request/response identity failed integrity checks.')
    return evaluate(artifact)


def outcome_report(artifact, outcome, persisted=False, briefing=False, error=None):
    receipt = (artifact.get('data') or {}).get('meterless', {})
    route = receipt.get('winning_route', {}) if isinstance(receipt, dict) else {}
    def identifier(value):
        return value if isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:/-]{0,160}', value) else None
    return {**({'staged_policy': artifact['staged_plan']['policy']} if 'staged_plan' in artifact else {}),
        'authorization': AUTHORIZATION, 'request_id': artifact['request_id'], 'attempts_used': 1,
        'http_status': artifact['model'].get('http_status'), 'returned_model': identifier(artifact['model'].get('returned_model')),
        'provider': identifier(route.get('provider')) if isinstance(route, dict) else None,
        'receipt_id': identifier(receipt.get('receipt_id')) if isinstance(receipt, dict) else None,
        'from_cache': receipt.get('from_cache') if isinstance(receipt, dict) else None,
        'finish_reason': artifact.get('finish_reason'), 'usage': artifact['model'].get('usage'),
        'duration_seconds': artifact['model'].get('duration_seconds'), 'captured_at': artifact['captured_at'],
        'validation_status': outcome['status'], 'validation_failure': outcome.get('validation_failure'),
        'assessment_persisted': persisted, 'briefing_persisted': briefing, 'human_decision_written': False,
        'error_category': error}


def run_once(store, token, context, requester=None, *, staged=False):
    folder = directory(store)
    with store.exclusive():
        state = store.read()
        if used(state, folder):
            return {'authorization': AUTHORIZATION, 'already_reserved': True, 'new_requests_sent': 0}
        inputs = preparation(store, state, context, staged=staged)
        retained.protected_directory(folder)
        request_id = str(uuid.uuid4())
        attempt = {'id': request_id, 'authorization': AUTHORIZATION, 'status': 'reserved', 'started_at': semantic.now(),
            'candidate_ids': [CANDIDATE], 'max_requests': 1, 'max_tokens': MAX_TOKENS,
            'contract_version': semantic.CONTRACT_VERSION, 'cache_keys': [inputs['prepared_inputs'][0]['cache_key']]}
        if staged:
            attempt['staged_policy'] = inputs['staged_plan']['policy']
        # Independent local and official-store guards precede the sole transport call.
        retained.write_new(folder / 'reservation.json', {**attempt, 'input_sha256': semantic.digest(inputs)})
        retained.write_new(folder / 'inputs.json', inputs)
        state.setdefault('semantic_authorizations', {})[AUTHORIZATION] = {'max_requests': 1, 'candidate_ids': [CANDIDATE],
            'reason': 'Explicit user authorization: one opportunity end-to-end attempt, no retries.'}
        state.setdefault('semantic_requests', []).append(attempt)
        state = store.save(state)
        retained.write_new(folder / 'transport-started.json', {'request_id': request_id, 'started_at': semantic.now()})
        print('Authorized opportunity request 1/1: one saved Nemotron candidate; no retries.', flush=True)
        requester = requester or (lambda token, messages: semantic.analyzer.request_claims(token, messages,
            max_tokens=MAX_TOKENS, max_response_bytes=semantic.MAX_RESPONSE_BYTES))
        try:
            result = requester(token, inputs['messages'])
        except Exception:
            result = {'ok': False, 'data': {}, 'http_status': None}
        try:
            artifact = retained.capture(result, token, inputs, request_id)
        except (TypeError, AttributeError, IndexError, KeyError):
            # Keep even malformed envelopes, without discarding the raw response or
            # introducing an echoed credential via a parsing fallback.
            original = result.get('data') if isinstance(result.get('data'), dict) else {}
            echo = bool(token and token in json.dumps(original, ensure_ascii=False))
            safe_result = {**result, 'data': {**original, 'choices': []}}
            artifact = retained.capture(safe_result, token, inputs, request_id)
            artifact.update(data=None if echo else original, credential_echo_rejected=echo,
                            transport_failure=True, capture_failure='response_envelope')
        artifact['authorization'] = AUTHORIZATION
        retained.write_new(folder / 'response.json', artifact)
        outcome = evaluate(artifact)
        retained.write_new(folder / 'validation.json', {'validator_version': semantic.VALIDATOR_VERSION, 'outcome': outcome})
        persisted = False
        error = None
        if outcome['status'] == 'validated':
            try:
                fresh = semantic.project_context(store.root)
                if semantic.digest(fresh) != inputs['context_sha256']:
                    raise ValueError('Context changed after request.')
                prepared = inputs['prepared_inputs'][0]
                item = state['items'][CANDIDATE]
                if semantic.prepare(store, item, fresh) != prepared:
                    raise ValueError('Source changed after request.')
                staged_state = copy.deepcopy(state)
                item = staged_state['items'][CANDIDATE]
                key = semantic.digest({'base_cache_key': prepared['cache_key'], 'authorization': AUTHORIZATION,
                    'contract_version': inputs['contract_version'],
                    **({'staged_plan_sha256': semantic.digest(inputs['staged_plan'])} if staged else {})})
                record = {**outcome, 'policy_version': semantic.POLICY, 'validator_version': semantic.VALIDATOR_VERSION,
                    'contract_version': inputs['contract_version'], 'authorization': AUTHORIZATION, 'cache_key': key,
                    'base_cache_key': prepared['cache_key'], 'context_sha256': prepared['context_sha256'],
                    'content_sha256': item['content_sha256'], 'request_id': request_id, 'assessed_at': artifact['captured_at'],
                    'model': artifact['model'], 'provenance': prepared['source'], 'project_context_provenance': fresh['provenance'],
                    'category': outcome['assessment']['category'],
                    'label': 'Provisional Nemotron assessment; exact quotations validated, suitability not verified.'}
                if staged:
                    record['staged_plan'] = copy.deepcopy(inputs['staged_plan'])
                    record['label'] += ' Opt-in staged publisher-claim extraction and connection checks; benefits remain unverified.'
                if item.get('semantic_assessment'):
                    item.setdefault('semantic_history', []).append(copy.deepcopy(item['semantic_assessment']))
                staged_state.setdefault('semantic_cache', {})[key] = record
                staged_state.setdefault('semantic_overrides', {})[prepared['cache_key']] = key
                item['semantic_assessment'] = record
                semantic.prepare_proposal(staged_state, item, record)
                state = staged_state
                persisted = True
            except (ValueError, OSError, RuntimeError):
                error = 'post_request_evidence_check'
        attempt = next(r for r in state['semantic_requests'] if r['id'] == request_id)
        attempt.update(status='validated' if persisted else 'failed', finished_at=semantic.now(),
            model=artifact['model'], validation_failure=outcome.get('validation_failure'), error_category=error,
            response_path=str((folder / 'response.json').relative_to(store.directory)))
        try:
            state = store.save(state)
        except Exception:
            report = outcome_report(artifact, outcome, error='assessment_persistence_unconfirmed')
            retained.write_new(folder / 'outcome.json', report)
            return report
    briefing = False
    if persisted:
        try:
            state = workflow.prepare(store, CANDIDATE, record['content_sha256'], record['cache_key'])
            briefing = any(r['evidence_references']['assessment_cache_key'] == record['cache_key']
                           for r in state.get('opportunity_recommendations', []))
        except Exception:
            error = 'briefing_persistence_unconfirmed'
    report = outcome_report(artifact, outcome, persisted, briefing, error)
    retained.write_new(folder / 'outcome.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--replay', action='store_true')
    parser.add_argument('--staged', action='store_true', help='Opt in to extracted publisher claims and stricter connection checks; does not grant or reset any live allowance.')
    args = parser.parse_args()
    if args.live and args.replay:
        raise SystemExit('Choose live or replay, never both.')
    store = discovery.Store()
    folder = directory(store)
    if args.replay:
        outcome = replay(folder)
        print(json.dumps({'offline_replay': True, 'new_requests_sent': 0, 'validation_status': outcome['status'],
                          'validation_failure': outcome.get('validation_failure')}))
        return
    state = store.read()
    if used(state, folder):
        print('This authorization is reserved/used. No token requested; no model request sent.')
        return
    context = semantic.project_context(store.root)
    inputs = preparation(store, state, context, staged=args.staged)
    if not args.live:
        print(json.dumps({'preview_only': True, 'candidate_id': CANDIDATE, 'authorization': AUTHORIZATION,
            'max_requests': 1, 'input_characters': sum(len(m['content']) for m in inputs['messages']),
            'contract_version': semantic.CONTRACT_VERSION, 'context_sha256': inputs['context_sha256']}))
        return
    if not sys.stdin.isatty():
        raise SystemExit('Use interactive PowerShell for hidden runtime-token entry; no echoed fallback.')
    try:
        with socket.create_connection(('127.0.0.1', 8088), timeout=3): pass
    except OSError:
        raise SystemExit('Nightshift is not listening. No model request sent.') from None
    with warnings.catch_warnings():
        warnings.simplefilter('error', getpass.GetPassWarning)
        token = getpass.getpass('Meterless Runtime token (hidden; ONE attempt, no retries): ').strip()
    if not token:
        raise SystemExit('No token supplied; no model request sent.')
    try:
        print(json.dumps(run_once(store, token, context, staged=args.staged)), flush=True)
    except Exception:
        raise SystemExit('Controlled runner stopped. Inspect protected artifacts before any further action; DO NOT rerun.') from None
    finally:
        token = None


if __name__ == '__main__': main()
