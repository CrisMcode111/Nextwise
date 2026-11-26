"""Read-only, bounded relevance hints over existing verified saved inputs.

Not an assessment or selection: no model, transport, reservation or persistence.
The initial offline rule covers an explicitly stated constraint goal and a saved
publisher filtering claim in the same understood subject. Other cases abstain.
"""
import re

from project_opportunities import _blocked
from project_understanding import understand


def previews(projects, store, state):
    understanding = understand(state)
    subject = understanding['subject']
    if not subject or not understanding['language_context']['english_rules_available']:
        return []
    facts = [f for f in understanding['confirmed_facts']
             if f['field'] in ('project.brief', 'project.priorities') and set(f['kinds']) & {'goals', 'needs', 'problems', 'priorities'}
             and re.search(r'\b(?:constraints?|preferences?|requirements?|restrictions?)\b', f['text'], re.I)
             and not re.search(r'\b(?:do not|avoid|exclude)\b', f['text'], re.I)]
    if not facts:
        return []
    subject_words = set(re.findall(r'[a-z]{4,}', subject['value'].lower()))
    assessed = {a['candidate_id'] for a in state['assessments']}
    result = []
    for cid, item in state['items'].items():
        if (cid in assessed or _blocked(state, cid) or item.get('source') != 'tavily-page'
                or item.get('kind') != 'saved_page'):
            continue
        try:
            # Existing hash verification, extraction and context attribution only.
            request = projects.prepare_assessment(store, state, item, [])
        except (ValueError, OSError, KeyError):
            continue
        for claim in request['staged_plan']['claims']:
            quote = claim['exact_quote']
            if not re.search(r'\bAPI\b', quote, re.I):
                continue
            if len(subject_words & set(re.findall(r'[a-z]{4,}', quote.lower()))) < min(2, len(subject_words)):
                continue
            match = re.search(r'\bfilter by\s+([^.;:\n]{5,160}?)(?=,\s*then\b|[.;:\n]|$)', quote, re.I)
            # Abstain on negated, conditional or instruction-shaped claims.
            clause = re.split(r'[.;\n]', quote[:match.start()])[-1] + match[0] if match else ''
            if not match or re.search(r'\b(?:not|no|cannot|without|if|ignore|instructions?)\b|n\x27t\b', clause, re.I):
                continue
            filters = match[1].strip()
            name = state['project']['name']
            result.append({'candidate_id': cid, 'label': 'Preliminary — not AI-validated',
                'source_title': item['title'], 'source_url': item['url'],
                'project_area': 'Product — constraint-based filtering',
                'why_relevant': f'{name} has a saved goal involving user constraints. The publisher describes '
                    f'filtering by {filters}. This may be relevant to constraint coverage; it does not establish a capability gap.',
                'possible_improvement': f'If {name} does not already support equivalent filtering, adding filtering '
                    f'by {filters} could be a product improvement to investigate.',
                'next_action': f'Check the current project\'s documented constraint coverage against filtering by {filters}, '
                    'using a synthetic example. Record any real gap before considering an API integration.',
                'unverified': ['Whether equivalent filtering already exists or is needed.',
                    'Publisher claims have not been independently tested.',
                    'API compatibility, integration effort, pricing, licensing and privacy implications.',
                    'No performance or user benefit has been established.'],
                'project_basis': {'field': facts[0]['field'], 'exact_quote': facts[0]['text'],
                                  'context_sha256': facts[0].get('context_revision_sha256', state['project']['context_sha256']),
                                  'context_revision_id': facts[0].get('context_revision_id')},
                'publisher_evidence': {k: claim[k] for k in ('source_id', 'passage_id', 'exact_quote')},
                'source_provenance': {k: item.get(k) for k in
                    ('snapshot_path', 'raw_sha256', 'content_sha256', 'retrieved_at')},
                'basis': 'Offline rule interpretation of saved user statements and publisher claims; no AI validation.'})
            break
        if len(result) == 3:
            break
    return result
