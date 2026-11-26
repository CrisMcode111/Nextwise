"""Verified, append-only user-confirmed project context snapshots."""
import copy
import semantic_discovery as semantic

FIELDS = ('capabilities', 'work_in_progress', 'limitations', 'priorities', 'resources', 'constraints')


def resolve(state, revision_id=None, *, current=True):
    revisions = state.get('context_revisions', [])
    if not revisions:
        if not current and revision_id is not None:
            raise ValueError('Project context revision not found.')
        return None
    previous = state['project']['context_sha256']
    ids = set()
    for index, revision in enumerate(revisions, 1):
        body = {k: v for k, v in revision.items() if k != 'record_sha256'}
        if (revision.get('version') != index or revision.get('previous_sha256') != previous
                or revision.get('id') in ids or revision.get('project_id') != state['project']['id']
                or semantic.digest(body) != revision.get('record_sha256')
                or set(revision.get('fields', {})) != set(FIELDS)):
            raise ValueError('Project context history failed integrity checks.')
        ids.add(revision['id'])
        previous = revision['record_sha256']
    selected = (revisions[-1] if revisions else None) if current else next(
        (r for r in revisions if r['id'] == revision_id), None)
    if not current and revision_id is not None and selected is None:
        raise ValueError('Project context revision not found.')
    return copy.deepcopy(selected)


def assessment_brief(state, revision):
    brief = state['project']['brief']
    if revision:
        brief += '\n\nConfirmed project context:\n' + '\n'.join(
            label.replace('_', ' ') + ': ' + revision['fields'][label]
            for label in FIELDS if revision['fields'][label])
    return brief


def planning_state(state):
    revision = resolve(state)
    if not revision:
        return state
    result = copy.deepcopy(state)
    project = result['project']
    for field in FIELDS:
        if revision['fields'][field]:
            project[field] = revision['fields'][field]
    project['context_revision_id'] = revision['id']
    project['context_revision_sha256'] = revision['record_sha256']
    return result
