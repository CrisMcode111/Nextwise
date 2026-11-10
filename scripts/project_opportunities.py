"""Pure discovery planning, feedback and evidence comparison; never execute.

Callers supply an already retrieved, integrity-checked Projects state. No memory
reads, credentials, provider calls, selection decisions or persistence occur here.
Lexical rules propose search coverage only; they do not assess opportunity fit.
"""
import copy
from datetime import datetime
import difflib
import hashlib
import json
import re
import uuid

import html_extract
import tavily_discovery as tavily


POLICY = 'project-discovery-planning-v1'
DOMAINS = {
    'technology': (r'\b(?:software|api|llm|python|integration|model|structured output|architecture|application|prototype)\b',
                   'capabilities compatibility integration', ['official_documentation', 'release_notes']),
    'product': (r'\b(?:features?|onboarding|retention|customer feedback|user needs|product roadmap|recipes?|meal plans?)\b',
                'product capabilities user needs', ['product_documentation', 'published_case_study']),
    'UX': (r'\b(?:usability|accessibility|interface|user experience|ux|visual|navigation|checkout)\b',
           'usability accessibility guidance', ['accessibility_standard', 'usability_research']),
    'productivity': (r'\b(?:manual|repetitive|automate|automation|time.consuming|administration|reporting)\b',
                     'workflow automation capabilities', ['official_documentation', 'published_case_study']),
    'financial': (r'\b(?:costs?|cash flow|margins?|invoices?|budget|pricing|expenses?|funding)\b',
                  'cost pricing eligibility terms', ['official_pricing', 'official_program_terms']),
    'commercial': (r'\b(?:sales|lead generation|conversion|new clients|contracts|revenue|customer acquisition)\b',
                   'sales distribution capabilities', ['product_documentation', 'published_case_study']),
    'marketing': (r'\b(?:marketing|seo|campaigns?|brand awareness|advertising|social media|content strategy)\b',
                  'marketing channel guidance', ['official_platform_guidance', 'published_case_study']),
    'operations': (r'\b(?:inventory|stock|supply chain|scheduling|repairs?|booking|delivery|procurement|warehouse|orders|fulfilment)\b',
                   'operations workflow capabilities', ['product_documentation', 'official_documentation']),
}
STOP = set('a an and are as at be by can could do for from have help i in is it its my need needs of on or our project should that the their this to use using want we with'.split())


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False).encode()).hexdigest()


def _text(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return '\n'.join(value)
    if isinstance(value, dict) and all(isinstance(k, str) and isinstance(v, (str, int, float))
                                      and not isinstance(v, bool) for k, v in value.items()):
        return '\n'.join(f'{k}: {v}' for k, v in sorted(value.items()))
    raise ValueError('Context fields must be text, a text list, or a scalar resource map.')


def _heads(state):
    heads = {}
    for record in state.get('decisions', []):
        subject = record.get('candidate_id')
        version = record.get('version')
        if (not isinstance(subject, str) or type(version) is not int or version < 1
                or record.get('choice') not in ('Adopt', 'Test', 'Defer', 'Reject')
                or record.get('project_id', state['project']['id']) != state['project']['id']):
            raise ValueError('Invalid project decision history.')
        previous = heads.get(subject)
        if previous and previous['version'] == version and previous != record:
            raise ValueError('Ambiguous decision head.')
        if previous is None or previous['version'] < version:
            heads[subject] = record
    return [heads[key] for key in sorted(heads)]


def _terms(text, name):
    # Do not copy complete private briefs, contact details, URLs or numeric
    # resource values into suggested public queries. Human review is still required.
    text = re.sub(re.escape(name), ' ', text, flags=re.I) if name else text
    text = re.sub(r'https?://\S+|\S+@\S+|\b\S*\d\S*\b', ' ', text)
    return list(dict.fromkeys(w for w in re.findall(r'[a-z][a-z-]{2,}', text.lower())
                              if w not in STOP))[:12]


def _language_context(state, language):
    declared = language or state['project'].get('language')
    if declared:
        if not isinstance(declared, str):
            raise ValueError('Language must be a language tag.')
        return {'language':declared, 'english_rules_available':declared.lower().split('-')[0] == 'en',
                'basis':'caller_declared', 'semantic_interpretation':'not_provided'}
    brief = state['project']['brief']
    english = set(re.findall(r'\b(?:the|our|with|and|for|improve|goal|needs|project|constraints|to|do|not|pursue|or)\b', brief.lower()))
    # A conservative applicability check, not language detection/translation.
    foreign = re.search(r'[^\x00-\x7f]|\b(?:je|nous|notre|pour|quiero|nuestro|para|ich|wir|unser)\b', brief, re.I)
    usable = len(english) >= 2 and not foreign
    return {'language':'und', 'english_rules_available':usable,
            'basis':'limited_English_rule_applicability_check', 'semantic_interpretation':'not_provided'}


def _reviewed_topics(state, topics):
    result = []
    known_categories = {c for _, _, cats in DOMAINS.values() for c in cats}
    for topic in topics:
        field = topic.get('context_field', 'brief')
        excerpt = topic.get('context_excerpt')
        categories = topic.get('source_categories')
        if (field not in ('brief','goals','constraints','resources') or field not in state['project']
                or not isinstance(excerpt, str) or len(excerpt) < 10
                or excerpt not in _text(state['project'][field])
                or topic.get('reviewed') is not True or not topic.get('review_reference')
                or not isinstance(topic.get('query'), str) or not 10 <= len(topic['query']) <= 500
                or not isinstance(topic.get('direction'), str) or not 1 <= len(topic['direction']) <= 80
                or not isinstance(categories, list) or not 1 <= len(categories) <= 3
                or any(c not in known_categories for c in categories)):
            raise ValueError('Semantic topics require reviewed, quoted project context and supported source targets.')
        result.append({'domain':topic['direction'], 'topic':excerpt, 'query':topic['query'],
            'source_categories':list(categories), 'basis':[{'field':'project.'+field, 'text':excerpt,
            'review_reference':topic['review_reference']}], 'score':45, 'priority':'high',
            'decision_gap_references':[], 'interpretation':'caller_reviewed'})
    return result


def plan_discovery(state, *, max_queries=tavily.MAX_SEARCHES,
                   results_per_query=tavily.RESULTS_PER_SEARCH,
                   max_source_pages=tavily.MAX_SOURCE_PAGES, language=None, semantic_topics=()):
    """Return an inspectable suggestion, not authorization or remaining quota.

    Optional project goals/constraints/resources are accepted for future callers;
    today's Projects records supply them inside the reviewed brief. They are not
    inferred or written back. Unknown vocabulary yields an empty plan for review.
    """
    for value, ceiling in ((max_queries, tavily.MAX_SEARCHES),
                           (results_per_query, tavily.RESULTS_PER_SEARCH),
                           (max_source_pages, tavily.MAX_SOURCE_PAGES)):
        if type(value) is not int or not 1 <= value <= ceiling:
            raise ValueError('Plan limits must remain within existing Tavily bounds.')
    project = state['project']
    brief = project.get('brief')
    if not isinstance(brief, str) or not 10 <= len(brief.strip()) <= 12000:
        raise ValueError('A saved project brief is required.')
    heads = _heads(state)
    inputs = [(f'project.{field}', _text(project[field])) for field in
              ('brief', 'goals', 'constraints', 'resources') if field in project]
    language_context = _language_context(state, language)
    topics = _reviewed_topics(state, semantic_topics)
    rules = DOMAINS if language_context['english_rules_available'] else {}
    for domain, (pattern, suffix, categories) in rules.items():
        basis = []
        for field, text in inputs:
            for clause in re.split(r'[;\n]+|(?<=[.!?])\s+(?=[A-Z])', text):
                if re.search(r'\b(?:do not|not interested in|exclude|avoid)\b', clause, re.I):
                    continue  # Conservative: do not turn an explicit exclusion into a search.
                matches = sorted(set(m.group().lower() for m in re.finditer(pattern, clause, re.I)))
                if matches:
                    constraint = field.endswith(('constraints', 'resources')) or bool(
                        re.match(r'\s*(?:constraints?|resources?|budget|team size|environment)\s*:', clause, re.I))
                    goal = field.endswith('goals') or bool(re.match(r'\s*(?:goals?|objectives?)\s*:', clause, re.I))
                    basis.append({'field':field, 'text':clause.strip(), 'matched_terms':matches,
                                  'weight':1 if constraint else 4 if goal else 3})
        if not basis:
            continue
        seed = max(basis, key=lambda b: (b['weight'], len(b['matched_terms'])))
        words = _terms(seed['text'], project.get('name', ''))
        if not words:
            continue
        followups = [d['id'] for d in heads if d['choice'] == 'Defer'
                     and re.search(pattern, d.get('rationale', '') + ' ' + d.get('next_action', ''), re.I)]
        score = max(b['weight'] for b in basis) * 10 + min(5, len(basis)) + bool(followups)
        query = ' '.join(words) + ' ' + suffix
        # Tech implementation sources require an explicit development context.
        source_categories = list(categories)
        if domain == 'technology' and not re.search(r'\b(?:develop\w*|software|api|prototype|architecture|python)\b', brief, re.I):
            source_categories = ['product_documentation', 'official_documentation']
        topics.append({'domain':domain, 'topic':' '.join(words), 'query':query[:500],
                       'source_categories':source_categories, 'basis':basis, 'score':score,
                       'priority':'high' if score >= 30 else 'normal',
                       'decision_gap_references':followups})
    topics.sort(key=lambda t: (-t['score'], t['domain']))
    if semantic_topics:
        language_context['semantic_interpretation'] = 'caller_reviewed_topics'
    blocked = [d for d in heads if d['choice'] in ('Reject', 'Defer')]
    checks = [{'field':field, 'text':clause.strip()} for field, text in inputs
              for clause in re.split(r'[;\n]+|(?<=[.!?])\s+(?=[A-Z])', text)
              if clause.strip() and (field.endswith(('constraints', 'resources')) or re.match(
                  r'\s*(?:constraints?|resources?|budget|team size|environment)\s*:', clause, re.I))]
    return {'policy':POLICY, 'project_id':project['id'], 'project_version':state.get('version'),
        'basis_sha256':_digest({'inputs':inputs, 'decision_heads':heads}),
        'project_context':[{'field':field, 'text':text} for field, text in inputs],
        'constraints_and_resources_to_check':checks,
        'decision_context':[{'decision_id':d['id'], 'candidate_id':d['candidate_id'],
                             'choice':d['choice'], 'version':d['version']} for d in heads],
        'language_context':language_context,
        'queries':topics[:max_queries], 'queued_topics':topics[max_queries:],
        'limits':{'max_queries':max_queries, 'results_per_query':results_per_query,
                  'max_search_results':max_queries*results_per_query, 'max_source_pages':max_source_pages,
                  'max_retries':0},
        'tavily':{'topic':'general', 'search_depth':'basic', 'include_answer':False},
        'decision_constraints':[{'decision_id':d['id'], 'candidate_id':d['candidate_id'],
            'choice':d['choice'], 'rationale':d.get('rationale', ''),
            'policy':'Do not reopen this candidate or override the human decision.'} for d in blocked],
        'requires_query_review':True, 'execution_authorized':False,
        'status':('ready_for_review' if topics else 'needs_project_clarification'
                  if language_context['english_rules_available'] else 'needs_semantic_interpretation'),
        'limitations':['Topics and priorities are lexical planning suggestions, not evidence of relevance.',
            'Source categories are search targets, not verified publisher identities.',
            'No quotas, spending, external calls or reconsideration of saved decisions are authorized.',
            'Unstated objectives, resources and constraints remain unknown.']}


def _evidence(state):
    records = list(state.get('items', {}).values())
    for brief in state.get('briefings', []):
        if brief.get('evidence_references'):
            records.append(brief['evidence_references'])
        records.extend(brief.get('context_evidence_references', []))
    return records


def _url(record):
    try:
        return tavily.source_url(record.get('url'))
    except (ValueError, TypeError, AttributeError):
        return None


def _time(record):
    try:
        value = datetime.fromisoformat(record['retrieved_at'].replace('Z', '+00:00'))
        return value.timestamp() if value.tzinfo else None
    except (KeyError, ValueError, TypeError, AttributeError):
        return None


def _verified_text(record, raw):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 2_000_000:
        return None
    if hashlib.sha256(raw).hexdigest() != record.get('raw_sha256'):
        return None
    text = html_extract.extract_readable_text(raw.decode('utf-8', errors='replace'))
    if hashlib.sha256(text.encode()).hexdigest() != record.get('content_sha256'):
        return None
    return text


def compare_evidence(candidate, state, *, snapshot=None, previous_snapshots=None, history=()):
    """Compare supplied evidence only; never read snapshot paths or retrieve URLs.

    history accepts earlier verified project checkpoints to include superseded
    evidence. previous_snapshots maps saved snapshot_path to original bytes.
    Material update means a witnessed substantive textual change, not a verified
    release, novel claim, project benefit or reason to reopen a human decision.
    """
    url = _url(candidate)
    if not url:
        raise ValueError('A valid public source URL is required.')
    records = _evidence(state)
    for checkpoint in history:
        if checkpoint['project']['id'] != state['project']['id']:
            raise ValueError('Evidence history belongs to another project.')
        records.extend(_evidence(checkpoint))
    same_url = [r for r in records if _url(r) == url]
    fingerprint = candidate.get('content_sha256')
    if fingerprint is not None and not re.fullmatch(r'[0-9a-f]{64}', fingerprint):
        raise ValueError('Invalid readable-content digest.')
    text = _verified_text(candidate, snapshot) if snapshot is not None else None
    if snapshot is not None and text is None:
        raise ValueError('Candidate snapshot failed integrity checks.')
    matches = [r for r in records if fingerprint and r.get('content_sha256') == fingerprint]
    result = {'classification':'new', 'comparison_status':'source_identity_only',
        'reason':'A previously unseen source URL; novelty of its claims is unverified.',
        'compared_snapshot_paths':[], 'added_passages':[], 'removed_passages':[],
        'reconsideration_authorized':False, 'opportunity_selected':False}
    def finish(category, status, reason):
        result.update(classification=category, comparison_status=status, reason=reason)
        return result
    if matches and not same_url:
        return finish('duplicate', 'matching_content_digest', 'Readable content matches saved evidence at another URL.')
    if not same_url:
        return result
    # Do not invent chronology from list order or publication dates.
    dated = [r for r in same_url if _time(r) is not None]
    latest_time = max((_time(r) for r in dated), default=None)
    latest = [r for r in dated if _time(r) == latest_time]
    latest_hashes = {r.get('content_sha256') for r in latest}
    if fingerprint and latest_hashes == {fingerprint}:
        return finish('already_known', 'matching_content_digest', 'The current saved source has the same readable-content digest.')
    if matches:
        return finish('duplicate', 'matching_content_digest', 'This content already occurs in saved evidence/history; no new change is established.')
    result['classification'] = 'already_known'
    if not fingerprint or text is None or len(latest_hashes) != 1 or not latest:
        return finish('already_known', 'insufficient_comparison', 'Known URL, but comparable verified text or an unambiguous dated baseline is missing.')
    baseline = sorted(latest, key=lambda r: r.get('snapshot_path', ''))[0]
    old = _verified_text(baseline, (previous_snapshots or {}).get(baseline.get('snapshot_path')))
    if old is None or _time(candidate) is None or _time(candidate) <= latest_time:
        return finish('already_known', 'insufficient_comparison', 'A verified earlier snapshot and later retrieval are required to establish change.')
    result['compared_snapshot_paths'] = [baseline.get('snapshot_path'), candidate.get('snapshot_path')]
    paragraphs = lambda t: [p.strip() for p in t.split('\n\n') if p.strip()]
    normalize = lambda p: ' '.join(re.findall(r'\w+', p.casefold()))
    old_parts, new_parts = paragraphs(old), paragraphs(text)
    old_set, new_set = {normalize(p) for p in old_parts}, {normalize(p) for p in new_parts}
    removed = [p for p in old_parts if normalize(p) not in new_set]
    added = [p for p in new_parts if normalize(p) not in old_set]
    # Conservative content-level gate: substantive fact-bearing passages and
    # nontrivial changed tokens. Layout, dates and byte/hash changes alone fail.
    fact = r'\b(?:supports?|provides?|requires?|available|availability|pricing|price|fees?|eligibility|released|discontinued)\b'
    substantive = lambda p: 40 <= len(p) <= 1800 and bool(re.search(fact, p, re.I))
    # An unchanged factual sentence followed by new navigation/marketing text
    # must not turn that incidental addition into a material factual update.
    sentences = lambda t: re.split(r'(?<=[.!?])\s+|\n+', t)
    old_sentences, new_sentences = sentences(old), sentences(text)
    old_facts = {normalize(s) for s in old_sentences if substantive(s)}
    new_facts = {normalize(s) for s in new_sentences if substantive(s)}
    old_tokens, new_tokens = normalize(' '.join(removed)).split(), normalize(' '.join(added)).split()
    if len(old_tokens) + len(new_tokens) > 4096:
        return finish('already_known', 'insufficient_comparison', 'Text delta exceeds the bounded comparison window; manual review is required.')
    changed = sum(max(i2-i1, j2-j1) for op, i1, i2, j1, j2 in
                  difflib.SequenceMatcher(None, old_tokens, new_tokens, autojunk=False).get_opcodes() if op != 'equal')
    if changed >= 3 and old_facts != new_facts and any(substantive(p) for p in removed + added):
        result['added_passages'] = [p for p in added if substantive(p)]
        result['removed_passages'] = [p for p in removed if substantive(p)]
        return finish('materially_updated', 'verified_textual_delta',
                      'A later snapshot contains a substantive factual-text delta. Publisher truth, release timing and project impact remain unverified.')
    return finish('already_known', 'no_material_change_established',
                  'Comparable text does not establish a substantive update under this conservative textual policy.')


STRATEGY_POLICY = 'adaptive-search-strategy-v1'


def _scope(state):
    return _digest({k:state['project'][k] for k in
                    ('id','brief','goals','constraints','resources','language') if k in state['project']})


def _seal_strategy(strategy):
    result = copy.deepcopy(strategy)
    result.pop('strategy_sha256', None)
    result['strategy_sha256'] = _digest(result)
    return result


def _check_strategy(state, strategy):
    body = {k:v for k,v in strategy.items() if k != 'strategy_sha256'}
    if (strategy.get('policy') != STRATEGY_POLICY or strategy.get('strategy_sha256') != _digest(body)
            or strategy.get('context_sha256') != _scope(state)):
        raise ValueError('Strategy integrity or project context changed; do not reset cumulative accounting.')


def _remaining(strategy):
    feedback = {r['attempt_id']:r for r in strategy['feedback']}
    used = {'queries':len(strategy['reservations']), 'results':0, 'pages':0}
    for reservation in strategy['reservations']:
        report = feedback.get(reservation['attempt_id'])
        confirmed = report and report['accounting_confirmed']
        used['results'] += report['results_received'] if confirmed else reservation['result_limit']
        used['pages'] += report['pages_attempted'] if confirmed else reservation['page_limit']
    remaining = {k:strategy['allowance'][k]-used[k] for k in used}
    if min(remaining.values()) < 0:
        raise ValueError('Cumulative search allowance exceeded.')
    return remaining


def create_strategy(state, plan, *, allowance):
    """Create an offline strategy ledger under caller-supplied fixed ceilings.

    An allowance is planning input, NOT evidence of user authorization. A future
    executor must validate approval and atomically persist this complete ledger.
    Never create a fresh ledger to resume an existing authorized discovery run.
    """
    limits = plan['limits']
    if plan.get('project_id') != state['project']['id']:
        raise ValueError('Plan belongs to another project.')
    maximum = {'queries':limits['max_queries'], 'results':limits['max_search_results'],
               'pages':limits['max_source_pages']}
    if (set(allowance) != set(maximum) or any(type(allowance[k]) is not int
            or not 0 <= allowance[k] <= maximum[k] for k in maximum)
            or maximum['queries'] > tavily.MAX_SEARCHES
            or maximum['results'] > tavily.MAX_SEARCHES*tavily.RESULTS_PER_SEARCH
            or maximum['pages'] > tavily.MAX_SOURCE_PAGES
            or not 1 <= limits['results_per_query'] <= tavily.RESULTS_PER_SEARCH):
        raise ValueError('Allowance must fit the existing bounded plan.')
    expected = _digest({'inputs':[(i['field'],i['text']) for i in plan['project_context']],
                        'decision_heads':_heads(state)})
    actual_inputs = [(f'project.{k}',_text(state['project'][k])) for k in
                     ('brief','goals','constraints','resources') if k in state['project']]
    if expected != plan.get('basis_sha256') or actual_inputs != [
            (i['field'],i['text']) for i in plan['project_context']]:
        raise ValueError('Plan context or decision history is stale.')
    strategy = {'policy':STRATEGY_POLICY, 'project_id':state['project']['id'],
        'context_sha256':_scope(state), 'plan':copy.deepcopy(plan),
        'allowance':dict(allowance), 'reservations':[], 'feedback':[],
        'category_feedback':[], 'learned_directions':[], 'proposals':[],
        'execution_authorized':False}
    return adapt_strategy(state, _seal_strategy(strategy))


def _blocked(state, candidate_id):
    item = state.get('items', {}).get(candidate_id, {})
    for decision in _heads(state):
        if decision['choice'] not in ('Reject','Defer'):
            continue
        if decision['candidate_id'] == candidate_id:
            return decision['id']
        references = [state.get('items', {}).get(decision['candidate_id'], {})]
        references.extend(b.get('evidence_references', {}) for b in state.get('briefings', [])
                          if b['candidate_id'] == decision['candidate_id'])
        for ref in references:
            try:
                if tavily.product_key(ref.get('url')) == tavily.product_key(item.get('url')):
                    return decision['id']
            except (ValueError, TypeError, AttributeError):
                pass
    return None


def _relevance_signal(state, candidate_id):
    """Consume current validated API flags, never infer fit from text overlap."""
    records = [a for a in state.get('assessments', []) if a['candidate_id'] == candidate_id]
    if not records:
        return {'category':'unassessed', 'assessment_id':None}
    record = records[-1]
    briefs = [b for b in state.get('briefings', []) if b['candidate_id'] == candidate_id]
    brief = briefs[-1] if briefs else {}
    item = state.get('items', {}).get(candidate_id, {})
    refs = brief.get('evidence_references', {})
    current = (record.get('validation') == 'contract_and_source_quotes_checked'
        and brief.get('assessment_id') == record['id']
        and state.get('briefing_current', {}).get(brief.get('id')) is True
        and all(item.get(k) and item[k] == refs.get(k) for k in ('raw_sha256','content_sha256')))
    category = record['assessment'].get('category') if current else 'unconfirmed_or_stale'
    if category not in ('potential relevance','low relevance','uncertain relevance'):
        category = 'unconfirmed_or_stale'
    return {'category':category, 'assessment_id':record['id']}


def _evaluate_outcome(state, report, seen):
    counts = dict.fromkeys(('usable','novel','duplicates','blocked','saved_page_coverage',
                            'potential','low','uncertain','unassessed','unconfirmed_or_stale'), 0)
    signals = []
    for source in report['sources']:
        candidate = source.get('candidate_id')
        item = state.get('items', {}).get(candidate, {})
        usable = (source['usability'] == 'usable' and source['coverage'] == 'saved_page'
                  and _url(item) is not None
                  and all(re.fullmatch(r'[0-9a-f]{64}', str(item.get(k,'')))
                          for k in ('raw_sha256','content_sha256')))
        blocked = _blocked(state, candidate)
        signal = _relevance_signal(state, candidate)
        comparison = source.get('comparison', {})
        identity = item.get('content_sha256') or _url(item) or candidate
        duplicate = bool(identity and identity in seen) or comparison.get('classification') in ('duplicate','already_known')
        novel = (comparison.get('classification'), comparison.get('comparison_status')) in (
            ('new','source_identity_only'), ('materially_updated','verified_textual_delta'))
        if identity:
            seen.add(identity)
        counts['blocked'] += bool(blocked)
        counts['duplicates'] += duplicate
        counts['saved_page_coverage'] += bool(usable)
        if usable and not blocked:
            counts['usable'] += 1
            counts['novel'] += bool(novel and not duplicate)
            key = {'potential relevance':'potential','low relevance':'low',
                   'uncertain relevance':'uncertain'}.get(signal['category'], signal['category'])
            if not duplicate:
                counts[key] += 1
        signals.append({'source_key':source['source_key'], 'candidate_id':candidate,
            'usable_saved_page':bool(usable), 'duplicate':duplicate, 'novel_source_or_text':bool(novel and not duplicate),
            'human_decision_id':blocked, **signal})
    promising = any(s['usable_saved_page'] and not s['duplicate'] and not s['human_decision_id']
                     and s['novel_source_or_text'] and s['category']=='potential relevance' for s in signals)
    outcome = ('promising' if promising else 'needs_assessment' if counts['unassessed']
               else 'needs_evidence_review' if counts['uncertain'] or counts['unconfirmed_or_stale'] else 'weak')
    return {'attempt_id':report['attempt_id'], 'outcome':outcome, 'counts':counts, 'signals':signals,
            'selection_made':False, 'note':'Usability, novelty and coverage are not proof of project benefit.'}


def _query_respects_decisions(state, query):
    for decision in _heads(state):
        if decision['choice'] not in ('Reject','Defer'):
            continue
        refs = [state.get('items', {}).get(decision['candidate_id'], {})]
        refs.extend(b.get('evidence_references', {}) for b in state.get('briefings', [])
                    if b['candidate_id']==decision['candidate_id'])
        for ref in refs:
            title = ref.get('title','').strip()
            if len(title)>=4 and re.search(r'(?<!\w)'+re.escape(title)+r'(?!\w)',query,re.I):
                return False
    return True


def _validate_feedback(report, reservation):
    if (not isinstance(report.get('feedback_id'),str) or not report['feedback_id']
            or type(report.get('accounting_confirmed')) is not bool
            or report.get('status') not in ('completed','failed','interrupted')
            or not isinstance(report.get('sources'),list)):
        raise ValueError('Invalid search feedback.')
    for field, bound in (('results_received','result_limit'), ('pages_attempted','page_limit')):
        value = report.get(field)
        if report['accounting_confirmed']:
            if type(value) is not int or not 0 <= value <= reservation[bound]:
                raise ValueError('Feedback exceeds reserved results or pages.')
        elif value is not None:
            raise ValueError('Unconfirmed accounting must remain unknown, not zero.')
    if report['accounting_confirmed'] and (len(report['sources']) > report['results_received']
            or sum(s.get('coverage')=='saved_page' for s in report['sources']) > report['pages_attempted']):
        raise ValueError('Feedback sources exceed accounted results/pages.')
    keys = set()
    for source in report['sources']:
        key = source.get('source_key')
        if (not isinstance(key,str) or not key or key in keys
                or source.get('usability') not in ('usable','unavailable','unsafe','unreadable')
                or source.get('coverage') not in ('saved_page','excerpt','snippet','unknown')):
            raise ValueError('Invalid or repeated feedback source identity.')
        keys.add(key)


def _category_direction(state, proposal):
    """New source targets need both quoted project context and saved evidence."""
    field = proposal.get('context_field','brief')
    excerpt = proposal.get('context_excerpt')
    candidate = proposal.get('candidate_id')
    record = next((a for a in state.get('assessments', [])
                   if a['id'] == proposal.get('assessment_id') and a['candidate_id'] == candidate), None)
    quote = proposal.get('evidence_quote')
    if (field not in ('brief','goals','constraints','resources') or field not in state['project']
            or not isinstance(excerpt,str) or len(excerpt)<10 or excerpt not in _text(state['project'][field])
            or proposal.get('reviewed') is not True or not proposal.get('review_reference')
            or not record or _relevance_signal(state,candidate)['category'] != 'potential relevance'
            or _relevance_signal(state,candidate)['assessment_id'] != record['id']
            or _blocked(state,candidate)
            or not isinstance(quote,str) or len(quote)<20
            or quote not in [e['exact_quote'] for e in record['assessment'].get('evidence',[])]) :
        return None
    category, query = proposal.get('source_category'), proposal.get('query')
    if (not isinstance(category,str) or not 1<=len(category)<=80
            or not isinstance(query,str) or not 10<=len(query)<=500):
        return None
    return {'domain':proposal.get('direction',category), 'topic':excerpt, 'query':query,
        'source_categories':[category], 'score':46, 'priority':'high',
        'basis':[{'field':'project.'+field, 'text':excerpt, 'assessment_id':record['id'], 'evidence_quote':quote}],
        'review_reference':proposal['review_reference'],
        'candidate_id':candidate, 'interpretation':'evidence_supported_source_target'}


def adapt_strategy(state, strategy, *, feedback=(), category_proposals=()):
    """Append explicit feedback and replace unreserved proposals; never dispatch.

    Feedback/comparison flags must come from trusted caller accounting and the
    existing evidence pipeline. They are strategy inputs, not new validations.
    """
    _check_strategy(state,strategy)
    result = copy.deepcopy(strategy)
    reservations = {r['attempt_id']:r for r in result['reservations']}
    for report in feedback:
        if report.get('attempt_id') not in reservations:
            raise ValueError('Feedback has no reserved search attempt.')
        _validate_feedback(report,reservations[report['attempt_id']])
        prior = next((r for r in result['feedback'] if r['attempt_id']==report['attempt_id']
                      or r['feedback_id']==report['feedback_id']), None)
        if prior:
            if prior != report:
                raise ValueError('Feedback is immutable; conflicting or repeated IDs cannot reset accounting.')
        else:
            result['feedback'].append(copy.deepcopy(report))
    for proposal in category_proposals:
        direction = _category_direction(state,proposal)
        record = {'proposal_sha256':_digest(proposal), 'accepted':direction is not None,
                  'reason':'Quoted project context and current validated evidence support this search target.'
                  if direction else 'Missing current project/evidence support, or blocked by a human decision.'}
        if record not in result['category_feedback']:
            result['category_feedback'].append(record)
            if direction:
                result['learned_directions'].append(direction)
    seen = set()
    result['evaluations'] = [_evaluate_outcome(state,r,seen) for r in sorted(result['feedback'],
        key=lambda r:list(reservations).index(r['attempt_id']))]
    learning = {}
    for evaluation in result['evaluations']:
        domain = reservations[evaluation['attempt_id']]['direction']
        learning[domain] = learning.get(domain,0) + (2 if evaluation['outcome']=='promising' else
                                                   -2 if evaluation['outcome']=='weak' else 0)
    result['priority_feedback'] = [{'direction':k,'adjustment':v} for k,v in sorted(learning.items())]
    direction_coverage = {}
    for reservation in result['reservations']:
        entry = direction_coverage.setdefault(reservation['direction'],
            {'queries_reserved':0,'queries_reported':0,'usable_saved_pages':0,
             'novel_sources':0,'validated_potential_signals':0})
        entry['queries_reserved'] += 1
    for evaluation in result['evaluations']:
        entry = direction_coverage[reservations[evaluation['attempt_id']]['direction']]
        entry['queries_reported'] += 1
        for field, count in (('usable_saved_pages','usable'),('novel_sources','novel'),
                             ('validated_potential_signals','potential')):
            entry[field] += evaluation['counts'][count]
    planned = {t['domain'] for t in result['plan']['queries']+result['plan']['queued_topics']}
    planned.update(t['domain'] for t in result['learned_directions'])
    result['coverage_feedback'] = {'directions':direction_coverage,
        'not_yet_searched':sorted(planned-set(direction_coverage)),
        'note':'Reported search coverage only; no completeness or opportunity-fit claim.'}
    result['remaining'] = _remaining(result)
    result['decision_heads_sha256'] = _digest(_heads(state))
    result['proposals'] = []
    settled = {r['attempt_id'] for r in result['feedback']}
    if any(r['attempt_id'] not in settled for r in result['reservations']):
        result['status'] = 'awaiting_reserved_search_outcome'
    elif min(result['remaining'].values()) <= 0:
        result['status'] = 'budget_exhausted'
    elif any(not r['accounting_confirmed'] for r in result['feedback']):
        result['status'] = 'needs_accounting_review'
    elif result['evaluations'] and result['evaluations'][-1]['outcome'] != 'weak':
        result['status'] = result['evaluations'][-1]['outcome']
    else:
        base = result['plan']
        # Preserve native reviewed topics and re-rank English suggestions against
        # the latest human decisions without creating a new accounting scope.
        reviewed = [t for t in base['queries']+base['queued_topics'] if t.get('interpretation')=='caller_reviewed']
        if base['language_context']['english_rules_available']:
            fresh = plan_discovery(state, language='en', max_queries=base['limits']['max_queries'],
                results_per_query=base['limits']['results_per_query'],max_source_pages=base['limits']['max_source_pages'])
            topics = reviewed+fresh['queries']+fresh['queued_topics']
        else:
            topics = reviewed
        topics += [t for t in result['learned_directions'] if not _blocked(state,t['candidate_id'])
                   and _relevance_signal(state,t['candidate_id'])['category']=='potential relevance']
        tried = {r['query'].casefold() for r in result['reservations']}
        topics.sort(key=lambda t: (-t['score']-learning.get(t['domain'],0)
                                    -4*bool(t.get('decision_gap_references')),t['domain']))
        for topic in topics:
            alternatives = [(topic['query'],topic['source_categories'],'project_topic')]
            if base['language_context']['english_rules_available']:
                alternatives.extend((topic['query']+' '+category.replace('_',' '),[category],
                                     'alternative_source_category') for category in topic['source_categories'])
            for query,categories,reason in alternatives:
                if len(query)>500 or query.casefold() in tried or not _query_respects_decisions(state,query):
                    continue
                proposal = {'direction':topic['domain'],'query':query,'source_categories':categories,
                    'basis':topic['basis'],'reason':reason,'requires_query_review':True,
                    'execution_authorized':False}
                proposal['proposal_id'] = _digest(proposal)
                if not any(p['query'].casefold()==query.casefold() for p in result['proposals']):
                    result['proposals'].append(proposal)
                break
            if len(result['proposals']) >= result['remaining']['queries']:
                break
        result['status'] = ('proposed_for_review' if result['proposals'] else
                            'needs_semantic_interpretation' if not base['language_context']['english_rules_available']
                            else 'needs_project_clarification')
    return _seal_strategy(result)


def reserve_search(state, strategy, proposal_id, *, attempt_id):
    """Pure reservation model for a future executor, not a provider operation.

    Unknown/failed attempts retain their reservation. Only confirmed accounting
    releases unconsumed result/page capacity; consumed queries are never restored.
    """
    _check_strategy(state,strategy)
    try:
        if str(uuid.UUID(attempt_id)) != attempt_id:
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise ValueError('Supply a unique UUID search attempt ID.') from None
    prior = next((r for r in strategy['reservations'] if r['attempt_id']==attempt_id),None)
    if prior:
        if prior['proposal_id'] != proposal_id:
            raise ValueError('Attempt ID already belongs to another proposal.')
        return copy.deepcopy(strategy)
    if strategy['decision_heads_sha256'] != _digest(_heads(state)):
        raise ValueError('Human decisions changed; adapt the existing ledger before reserving.')
    proposal = next((p for p in strategy['proposals'] if p['proposal_id']==proposal_id),None)
    remaining = _remaining(strategy)
    if (strategy['status'] != 'proposed_for_review' or not proposal or min(remaining.values())<=0):
        raise ValueError('No bounded search proposal is available.')
    result = copy.deepcopy(strategy)
    result['reservations'].append({'attempt_id':attempt_id,'proposal_id':proposal_id,
        'direction':proposal['direction'],'query':proposal['query'],
        'source_categories':proposal['source_categories'],
        'result_limit':min(remaining['results'],strategy['plan']['limits']['results_per_query']),
        'page_limit':min(remaining['pages'],remaining['results'],strategy['plan']['limits']['results_per_query'])})
    return adapt_strategy(state,_seal_strategy(result))
