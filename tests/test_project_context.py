"""Context revisions on isolated, initially empty H-MEM project stores."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import uuid

from test_project_workflow import PAGE, URL, mocked_assessment, workflow
from project_context import FIELDS, resolve


class ContextRevisionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='nextwise-context-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / 'memory'
        self.network = patch('socket.socket', side_effect=AssertionError('No external calls'))
        self.network.start()
        self.addCleanup(self.network.stop)
        self.projects = workflow.Projects(self.root,
            searcher=lambda query: [{'title':'CycleHelp', 'url':URL}],
            fetcher=lambda url: {'raw':PAGE, 'error':None}, assessor=mocked_assessment)

    def create(self, name='Cycle repair'):
        return self.projects.create({'request_id':str(uuid.uuid4()), 'name':name,
            'brief':'I run a bicycle shop and need to answer customer questions about our published hours and repair policies.',
            'reviewed_sanitized':True})

    def act(self, state, action, **fields):
        return self.projects.act(state['project']['id'], action, {'request_id':str(uuid.uuid4()),
            'expected_version':state['version'], **fields})

    def test_confirmed_context_preserves_historical_assessment_and_reopens(self):
        state = self.create()
        state = self.act(state, 'discover', query='customer support public shop policies tools')
        state = self.act(state, 'assess', candidate_id=next(iter(state['items'])))
        state = self.act(state, 'brief', assessment_id=state['assessments'][-1]['id'])
        original, assessment = copy.deepcopy(state['project']), copy.deepcopy(state['assessments'][0])
        fields = dict.fromkeys(FIELDS, '')
        fields.update(capabilities='We already answer opening hours questions.',
            limitations='Repair policy coverage is incomplete.', priorities='Priority: marketing',
            constraints='Our marketing secret is violetmongoose.')
        state = self.act(state, 'update_context', fields=fields, confirmed=True)
        reopened = workflow.Projects(self.root).read(state['project']['id'])
        self.assertEqual(reopened['project'], original)
        self.assertEqual(reopened['assessments'][0], assessment)
        self.assertEqual(resolve(reopened)['fields'], fields)
        self.assertFalse(reopened['briefing_current'][reopened['briefings'][0]['id']])
        store = self.projects.store(state['project']['id'])
        self.assertEqual(self.projects._assessment(store, reopened, assessment['id'], current=False), assessment)
        with self.assertRaises(ValueError):
            self.projects._assessment(store, reopened, assessment['id'])
        plan = self.projects.act(state['project']['id'], 'research_plan', {'expected_version':reopened['version']})
        self.assertEqual(plan['research_focus'], 'marketing')
        self.assertTrue(any(f['text'] == fields['capabilities'] for f in plan['understanding']['confirmed_facts']))
        self.assertNotIn('violetmongoose', ' '.join(t['query'] for t in plan['queries'] + plan['queued_topics']))
        broken = copy.deepcopy(reopened)
        broken['context_revisions'][0]['fields']['capabilities'] = 'Changed'
        with self.assertRaises(ValueError): resolve(broken)

    def test_context_update_request_id_and_version(self):
        state = self.create('Community garden')
        fields = dict.fromkeys(FIELDS, '')
        fields['work_in_progress'] = 'Volunteers are planting a shared garden.'
        body = {'request_id':str(uuid.uuid4()), 'expected_version':state['version'],
                'fields':fields, 'confirmed':True}
        updated = self.projects.act(state['project']['id'], 'update_context', body)
        self.assertEqual(self.projects.act(state['project']['id'], 'update_context', body), updated)
        with self.assertRaises(ValueError):
            self.projects.act(state['project']['id'], 'update_context', {**body, 'request_id':str(uuid.uuid4())})
