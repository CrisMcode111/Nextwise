"""Synthetic-only one-request authorization, contract, independent validation and replay."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import reassess_discovery_once as once
import semantic_discovery as semantic
import test_semantic_discovery as fixtures
from semantic_fixture import assessment,context
from test_update_discovery import rss


class ControlledTests(unittest.TestCase):
    def test_observed_missing_observation_null_linkage_and_changed_ellipsis_remain_rejected(self):
        first={'candidate_id':'first','source_id':'source-first','existing_investigation':True,
            'passages':[{'passage_id':'p7','text':'A customizable language model supports specialized tasks and model routing.'}]}
        second={'candidate_id':'second','source_id':'source-second','existing_investigation':False,
            'passages':[{'passage_id':'p1','text':'An interactive entertainment service supports a new multiplayer mode […]'}]}
        values=[assessment(first),assessment(second)]
        for value in values:
            value.pop('source_observation')
            value.update(category='low relevance',priority='low',investigation_question=None,existing_findings_connection=None)
        values[1]['evidence'][0]['exact_quote']=second['passages'][0]['text'].replace('…','...')
        content=json.dumps({'assessments':values})
        artifact={'prepared_inputs':[{'source':first},{'source':second}],
            'model':{'returned_model':'nvidia/nemotron-fixture'},'content':content,'content_sha256':semantic.discovery.sha(content)}
        outcomes=once.evaluate(artifact)
        self.assertTrue(all(o['status']=='failed' for o in outcomes.values()))
        self.assertTrue(all(o['validation_failure']['missing_fields']==['source_observation'] for o in outcomes.values()))
        audit=once.audit_response(artifact)
        self.assertTrue(audit['first']['quote_checks'][0]['exact_quote'])
        self.assertTrue(audit['first']['existing_findings_connection_is_null'])
        self.assertFalse(audit['second']['quote_checks'][0]['exact_quote'])
        self.assertTrue(all('source_observation' not in value for value in values))

    def initialize(self,tmp):
        feed=rss([('test-feed','An unrelated interactive entertainment announcement')]).replace(
            b'Publisher summary',b'A multiplayer entertainment mode is available on supported devices. The excerpt ends here.')
        store,fixture,state=fixtures.SemanticTests().initialize(tmp,feed)
        fixture.page='<p>Opening introduction without a task capability.</p>'+''.join(
            f'<p>Section {i}: A language model supports structured outputs through a compatible API, preserving explicit user requirements.</p>'
            for i in range(1,13))
        with patch.object(semantic,'project_context',return_value=context()):state=store.run(fixture)
        page=next(i['id'] for i in state['items'].values() if i['source']!=semantic.discovery.FEED)
        feed=next(i['id'] for i in state['items'].values() if i['source']==semantic.discovery.FEED)
        return store,(page,feed)

    def transport(self,bad_quote=False):
        calls=[]
        def request(token,messages):
            calls.append(messages);sources=json.loads(messages[1]['content'])['untrusted_sources']
            first=assessment(sources[0],True)
            second=assessment(sources[1]);second.update(category='low relevance',investigation_question=None,priority='low')
            if bad_quote:second['evidence'][0]['exact_quote']='An unsupported quotation absent from this source.'
            return {'ok':True,'http_status':200,'data':{'model':'nvidia/nemotron-fixture',
                'usage':{'prompt_tokens':100,'completion_tokens':200,'total_tokens':300},
                'choices':[{'message':{'content':json.dumps({'assessments':[first,second]})},'finish_reason':'stop'}]}}
        return request,calls

    def test_contract_limits_match_validator_and_low_needs_no_proposal(self):
        source={'candidate_id':'candidate','source_id':'source','existing_investigation':False,
            'passages':[{'passage_id':'p1','text':'A source passage long enough for an exact supporting quotation.'}]}
        prepared={'source':source};contract=semantic.output_contract([prepared])
        fields=contract['properties']['assessments']['items']['properties']
        self.assertEqual(set(fields),semantic.FIELDS)
        self.assertEqual(fields['project_need']['maxLength'],semantic.TEXT_MAX)
        self.assertEqual(fields['evidence']['items']['properties']['exact_quote']['maxLength'],semantic.QUOTE_MAX)
        self.assertEqual(fields['category']['enum'],list(semantic.CATEGORIES))
        self.assertEqual(fields['limitations']['maxItems'],semantic.GAP_CAP)
        value=assessment(source);value.update(category='low relevance',priority='low',investigation_question=None)
        self.assertEqual(semantic.validate(value,prepared),value)
        state={'proposals':[]};semantic.prepare_proposal(state,{}, {'assessment':value})
        self.assertEqual(state['proposals'],[])
        value['application_hypothesis']='Guaranteed savings without supporting evidence.'
        with self.assertRaises(semantic.AssessmentError):semantic.validate(value,prepared)

    def test_one_request_retention_replay_history_continuation_and_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            store,ids=self.initialize(tmp);old=copy.deepcopy(store.read())
            inputs=once.preparation(store,context(),ids)
            paragraphs=inputs['prepared_inputs'][0]['source']['passages']
            self.assertTrue(any(int(p['passage_id'][1:])>3 for p in paragraphs))
            self.assertNotIn('Opening introduction', ' '.join(p['text'] for p in paragraphs))
            self.assertIn('not fetched',inputs['prepared_inputs'][1]['source']['coverage']['description'])
            request,calls=self.transport()
            state=once.run_once(store,'FIXTURE_PRIVATE_TOKEN',context(),request,ids)
            self.assertEqual(len(calls),1)
            self.assertEqual(semantic.request_accounting(state,once.AUTHORIZATION)['requests_used'],1)
            self.assertEqual(semantic.request_accounting(state)['requests_used'],0)
            self.assertEqual(len(state['proposals']),1)
            self.assertEqual(state['proposals'][0]['proposal_kind'],'existing_investigation_followup')
            self.assertIsNone(state['proposals'][0]['human_approval'])
            self.assertEqual(state['runs'],old['runs']);self.assertEqual(state['baselines'],old['baselines'])
            self.assertTrue(all(i['revisions']==old['items'][cid]['revisions'] for cid,i in state['items'].items()))
            replay=once.replay_saved(store)
            self.assertTrue(all(r['status']=='validated' for r in replay.values()))
            folder=once.directory(store)
            self.assertNotIn('FIXTURE_PRIVATE_TOKEN',''.join(p.read_text(encoding='utf-8') for p in folder.glob('*.json')))
            self.assertEqual(once.run_once(store,'',context(),request,ids),state)
            self.assertEqual(len(calls),1)
            cache_only={**state,'semantic_requests':[]}
            self.assertTrue(once.already_reserved(cache_only,Path(tmp)/'no-reservation-file'))
            with patch.object(semantic,'project_context',return_value=context()):
                reopened=store.reassess();self.assertEqual(reopened,state)
                page=state['items'][ids[0]]
                selected=store.select(ids[0],None,page['content_sha256'],page['semantic_assessment']['cache_key'])
                self.assertEqual(selected['proposal_selections'][0]['user_note'],None)

    def test_independent_rejection_and_original_failed_cache_preservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            store,ids=self.initialize(tmp)
            def failed(*args):return {'ok':False,'http_status':503}
            original=semantic.run(store,'FIXTURE_PRIVATE_TOKEN',context(),failed,lambda m:None)
            request,calls=self.transport(True)
            state=once.run_once(store,'FIXTURE_PRIVATE_TOKEN',context(),request,ids)
            self.assertEqual(len(calls),1)
            self.assertTrue(all(state['semantic_cache'][k]==v for k,v in original['semantic_cache'].items()))
            self.assertEqual(state['items'][ids[0]]['semantic_assessment']['status'],'validated')
            self.assertEqual(state['items'][ids[1]]['semantic_assessment']['validation_failure']['code'],'quote_not_exact')
            self.assertIn(original['items'][ids[0]]['semantic_assessment'],state['items'][ids[0]]['semantic_history'])
            replay=once.replay_saved(store)
            self.assertEqual(replay[ids[0]]['status'],'validated');self.assertEqual(replay[ids[1]]['status'],'failed')

    def test_interruption_and_transport_failure_cannot_retry(self):
        for interrupt in (False,True):
            with self.subTest(interrupt=interrupt),tempfile.TemporaryDirectory() as tmp:
                store,ids=self.initialize(tmp);calls=[]
                def failing(*args):
                    calls.append(1)
                    if interrupt:raise KeyboardInterrupt()
                    return {'ok':False,'http_status':503}
                if interrupt:
                    with self.assertRaises(KeyboardInterrupt):once.run_once(store,'FIXTURE',context(),failing,ids)
                else:once.run_once(store,'FIXTURE',context(),failing,ids)
                once.run_once(store,'FIXTURE',context(),failing,ids)
                self.assertEqual(len(calls),1)
                self.assertTrue(once.already_reserved(store.read(),once.directory(store)))


if __name__=='__main__':unittest.main()
