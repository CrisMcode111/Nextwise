"""Discovery briefings and human choices in the existing locked H-MEM checkpoints.

No transport or model calls. Semantic validation is reused, never repaired here.
"""
import copy
import uuid
from datetime import datetime, timezone

import semantic_discovery as semantic

POLICY = 'discovery-recommendation-v1'
CHOICES = ('Adopt', 'Test', 'Defer', 'Reject')
OBSERVATIONS = {
    'initial_inventory': 'Initial inventory; not a newly detected release.',
    'page_baseline': 'First monitored-page observation; no earlier version to compare.',
    'new_article': 'Newly discovered article; publication date is publisher-reported.',
    'monitored_page_changed': 'Readable content changed on a monitored page.',
    'article_summary_changed': 'Feed title or excerpt changed; the linked article was not fetched.',
}


def stamp():
    return datetime.now(timezone.utc).isoformat()


def seal(record):
    return {**record, 'record_sha256': semantic.digest(record)}


def verify(records):
    """Check append-only chains per candidate, including cross-recommendation decisions."""
    heads = {}
    ids = set()
    for record in records:
        body = {k: v for k, v in record.items() if k != 'record_sha256'}
        head = heads.get(record['candidate_id'])
        if (semantic.digest(body) != record.get('record_sha256') or record['id'] in ids
                or record['version'] != (head['version'] + 1 if head else 1)
                or record['previous_record_sha256'] != (head['record_sha256'] if head else None)):
            raise ValueError('Opportunity history failed integrity checks; no records were replaced.')
        ids.add(record['id'])
        heads[record['candidate_id']] = record
    return heads


def current(store, state, candidate_id, context):
    item = state['items'].get(candidate_id)
    if not item:
        raise ValueError('Candidate is unavailable; reopen saved discovery.')
    prepared = semantic.prepare(store, item, context)  # Rehash the original local snapshot.
    assessment = semantic.assessment_for_prepared(state, prepared)
    if (not assessment or assessment.get('status') != 'validated'
            or assessment != item.get('semantic_assessment')
            or assessment.get('context_sha256') != prepared['context_sha256']
            or assessment.get('content_sha256') != item['content_sha256']
            or assessment.get('provenance') != prepared['source']):
        raise ValueError('A current validated assessment is required; rejected or stale drafts cannot become recommendations.')
    semantic.validate(assessment['assessment'], prepared)
    if 'staged_plan' in assessment:
        import staged_opportunity as stages
        stages.validate(assessment['assessment'], prepared, context, assessment['staged_plan'])
    return item, assessment


def evidence_ok(store, state, recommendation):
    refs = recommendation['evidence_references']
    record = state.get('semantic_cache', {}).get(refs['assessment_cache_key'])
    if not record or semantic.digest(record) != refs['assessment_sha256']:
        return False
    path = (store.directory / refs['snapshot_path']).resolve()
    return (path.is_relative_to((store.directory / 'runs').resolve()) and path.is_file()
            and semantic.discovery.sha(path.read_bytes()) == refs['raw_sha256'])


def view(store, state):
    recommendations = state.get('opportunity_recommendations', [])
    decisions = state.get('opportunity_decisions', [])
    heads = verify(recommendations)
    verify(decisions)
    by_id = {r['id']: r for r in recommendations}
    for decision in decisions:
        r = by_id.get(decision['recommendation_id'])
        if (not r or r['candidate_id'] != decision['candidate_id']
                or decision['evidence_references'] != {'recommendation_sha256': r['record_sha256'], **r['evidence_references']}):
            raise ValueError('Decision evidence linkage failed integrity checks.')
    result = []
    for candidate_id, head in heads.items():
        item = state['items'].get(candidate_id, {})
        assessment = item.get('semantic_assessment', {})
        available = evidence_ok(store, state, head)
        fresh = (available and not state.get('semantic_context_error') and assessment.get('status') == 'validated'
                 and semantic.digest(assessment) == head['evidence_references']['assessment_sha256']
                 and item.get('content_sha256') == head['evidence_references']['content_sha256'])
        result.append({'recommendation': head, 'current': bool(fresh), 'evidence_available': available,
            'recommendation_history': [r for r in recommendations if r['candidate_id'] == candidate_id],
            'decisions': [d for d in decisions if d['candidate_id'] == candidate_id]})
    return copy.deepcopy(result)


def prepare(store, candidate_id, revision_sha256, assessment_cache_key):
    with store.exclusive():
        state = store.read()
        view(store, state)
        context = semantic.project_context(store.root)
        item, record = current(store, state, candidate_id, context)
        if item['content_sha256'] != revision_sha256 or record['cache_key'] != assessment_cache_key:
            raise ValueError('The candidate changed; reopen discovery and review its evidence.')
        records = state.setdefault('opportunity_recommendations', [])
        previous = next((r for r in reversed(records) if r['candidate_id'] == candidate_id), None)
        basis = semantic.digest({'policy': POLICY, 'assessment': record, 'observation_kind': item['kind']})
        if previous and previous['basis_sha256'] == basis:
            return state
        a = record['assessment']
        # Conservative policy over validated reasoning, not another relevance engine.
        # Existing investigations retain their Defer boundary until human reconsideration.
        choice = ('Defer' if record['provenance']['existing_investigation'] or a['category'] == 'uncertain relevance'
                  else 'Reject' if a['category'] == 'low relevance' else 'Test')
        reason = {'Defer': 'Resolve the stated evidence gaps before reconsidering. Existing human decisions remain unchanged.',
                  'Reject': 'Do not pursue this opportunity on the supplied task evidence; this is not a verdict on the whole technology.',
                  'Test': 'Consider only a bounded evaluation plan after reviewing the evidence and agreeing criteria and budget; no test is authorized.'}[choice]
        refs = {'assessment_cache_key': record['cache_key'], 'assessment_sha256': semantic.digest(record),
                'context_sha256': record['context_sha256'], 'project_context_provenance': record['project_context_provenance'],
                **{k: record['provenance'][k] for k in ('source_id', 'url', 'publication_date', 'retrieved_at',
                                                       'snapshot_path', 'raw_sha256', 'content_sha256')}}
        records.append(seal({'schema': 'nextwise.opportunity-recommendation.v1', 'policy_version': POLICY,
            'id': str(uuid.uuid4()), 'candidate_id': candidate_id, 'project_id': context['profile']['id'],
            'version': previous['version'] + 1 if previous else 1,
            'previous_record_sha256': previous['record_sha256'] if previous else None,
            'created_at': stamp(), 'basis_sha256': basis, 'title': item['title'],
            'what_changed': OBSERVATIONS.get(item['kind'], 'Saved source observation.') + ' ' + a['source_observation'],
            'why_it_matters': a['project_need'], 'potential_value': a['application_hypothesis'] or 'No practical benefit is established by the supplied material.',
            'supporting_evidence': copy.deepcopy(a['evidence']), 'risks': copy.deepcopy(a['limitations']),
            'uncertainty': copy.deepcopy(a['missing_information']), 'priority': a['priority'], 'priority_reason': a['priority_reason'],
            'recommended_choice': choice, 'recommendation_reason': reason, 'next_action': a['next_step'],
            'investigation_question': a['investigation_question'], 'existing_findings_connection': a['existing_findings_connection'],
            'existing_investigation_id': semantic.INVESTIGATION if record['provenance']['existing_investigation'] else None,
            'coverage': record['provenance']['coverage'], 'evidence_references': refs,
            'assessment_request_id': record['request_id'], 'assessment_model': record['model'],
            'label': 'Provisional briefing from validated semantic assessment; conservative recommendation policy, not a new model response or human approval.'}))
        return store.save(state)


def decide(store, body):
    if (not isinstance(body, dict) or body.get('explicit_action') != 'record_opportunity_decision'
            or body.get('choice') not in CHOICES or not isinstance(body.get('rationale'), str)
            or not 0 < len(body['rationale'].strip()) <= 8000
            or not isinstance(body.get('next_action', ''), str) or len(body.get('next_action', '')) > 4000
            or 'expected_head' not in body):
        raise ValueError('Choose Adopt, Test, Defer or Reject and write a rationale within the form limits.')
    try:
        uuid.UUID(body.get('request_id', ''))
    except (ValueError, TypeError, AttributeError):
        raise ValueError('A valid decision request ID is required.') from None
    with store.exclusive():
        state = store.read()
        view(store, state)
        fingerprint = semantic.digest(body)
        decisions = state.setdefault('opportunity_decisions', [])
        retry = next((d for d in decisions if d['request_id'] == body['request_id']), None)
        if retry:
            if retry['request_sha256'] != fingerprint:
                raise ValueError('This request ID belongs to different decision text.')
            return state
        r = next((r for r in state.get('opportunity_recommendations', []) if r['id'] == body.get('recommendation_id')), None)
        if not r or r['record_sha256'] != body.get('recommendation_sha256'):
            raise ValueError('Recommendation is missing or changed; reopen the opportunity briefing.')
        latest = next(r0 for r0 in reversed(state['opportunity_recommendations']) if r0['candidate_id'] == r['candidate_id'])
        context = semantic.project_context(store.root)
        item, record = current(store, state, r['candidate_id'], context)
        if (latest['id'] != r['id'] or semantic.digest(record) != r['evidence_references']['assessment_sha256']
                or item['content_sha256'] != r['evidence_references']['content_sha256'] or not evidence_ok(store, state, r)):
            raise ValueError('Evidence or project context changed; review a current recommendation before deciding.')
        head = next((d for d in reversed(decisions) if d['candidate_id'] == r['candidate_id']), None)
        if body['expected_head'] != (head['id'] if head else None):
            raise ValueError('A newer decision exists; review history before amending.')
        if head and all(head[k] == body.get(k, '') for k in ('recommendation_id', 'choice', 'rationale', 'next_action')):
            return state
        decisions.append(seal({'schema': 'nextwise.opportunity-decision.v1', 'id': str(uuid.uuid4()),
            'candidate_id': r['candidate_id'], 'project_id': r['project_id'], 'recommendation_id': r['id'],
            'version': head['version'] + 1 if head else 1, 'previous_record_sha256': head['record_sha256'] if head else None,
            'created_at': stamp(), 'actor': 'local_human_user', 'request_id': body['request_id'], 'request_sha256': fingerprint,
            'choice': body['choice'], 'rationale': body['rationale'], 'next_action': body.get('next_action', ''),
            'evidence_references': {'recommendation_sha256': r['record_sha256'], **copy.deepcopy(r['evidence_references'])},
            'boundary': 'Human choice only; does not authorize model calls, research, trials, spending or deployment. Original investigation history is unchanged.'}))
        return store.save(state)
