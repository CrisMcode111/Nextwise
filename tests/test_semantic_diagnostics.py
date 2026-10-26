"""Offline regressions for lost diagnostics, request accounting and strict replay."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import assess_discovery
import diagnose_semantic_discovery as offline
import semantic_discovery as semantic
import test_semantic_discovery as fixtures
from semantic_fixture import assessment,context
from test_update_discovery import rss


class DiagnosticTests(unittest.TestCase):
    def prepared(self):
        return {'source':{'candidate_id':'candidate-1','source_id':'source-1',
            'passages':[{'passage_id':'p1','text':'An API can return structured outputs for requirements extraction.'}],
            'existing_investigation':False}}

    def assert_code(self,call,code,field=None):
        with self.assertRaises(semantic.AssessmentError) as caught:call()
        diagnostic=caught.exception.diagnostic
        self.assertEqual(diagnostic['code'],code)
        self.assertEqual(diagnostic['validator_version'],semantic.VALIDATOR_VERSION)
        if field:self.assertEqual(diagnostic['field'],field)
        return diagnostic

    def test_batch_errors_are_distinct_no_json_repair_or_identity_inference(self):
        p=self.prepared();good=assessment(p['source'],True)
        serialized=json.dumps({'assessments':[good]})
        self.assertEqual(semantic.parse_batch('```json\n'+serialized+'\n```',[p]),{'candidate-1':good})
        self.assertEqual(semantic.parse_batch('<think>untrusted reasoning</think>'+serialized,[p]),{'candidate-1':good})
        self.assert_code(lambda:semantic.parse_batch(serialized[:-4],[p]),'invalid_json')
        self.assert_code(lambda:semantic.parse_batch(json.dumps({'results':[good]}),[p]),'batch_schema')
        self.assert_code(lambda:semantic.parse_batch('{"assessments":[],"assessments":[]}',[p]),'duplicate_json_key')
        duplicate=self.assert_code(lambda:semantic.parse_batch(json.dumps({'assessments':[good,good]}),[p]),'batch_identity')
        self.assertEqual(duplicate['duplicate_count'],1)
        for candidate_id in ([],None,13):
            bad={**good,'candidate_id':candidate_id}
            self.assert_code(lambda:semantic.parse_batch(json.dumps({'assessments':[bad]}),[p]),'candidate_id_type')
        bad={**good,'candidate_id':'unknown'}
        self.assert_code(lambda:semantic.parse_batch(json.dumps({'assessments':[bad]}),[p]),'batch_identity')
        replay=offline.replay(serialized,[p],{'returned_model':'different-model'})
        self.assertEqual(replay['candidate-1']['diagnostic']['code'],'returned_model')

    def test_grounding_rejections_have_safe_exact_field_paths(self):
        p=self.prepared();good=assessment(p['source'],True)
        for key,bad,code in [('source_id','untrusted text','source_identity'),('passage_id',[],'passage_identity'),
                              ('exact_quote','The output guarantees perfect task accuracy.','quote_not_exact')]:
            value=copy.deepcopy(good);value['evidence'][0][key]=bad
            diagnostic=self.assert_code(lambda:semantic.validate(value,p),code,'evidence[0].'+key)
            self.assertNotIn('untrusted text',json.dumps(diagnostic))
        value=copy.deepcopy(good);value.pop('limitations');value['untrusted extra field']='do not echo'
        diagnostic=self.assert_code(lambda:semantic.validate(value,p),'assessment_schema')
        self.assertEqual(diagnostic['missing_fields'],['limitations'])
        self.assertEqual(diagnostic['unexpected_field_count'],1)
        self.assertNotIn('untrusted extra field',json.dumps(diagnostic))
        value=copy.deepcopy(good);value['category']='uncertain relevance'
        self.assert_code(lambda:semantic.validate(value,p),'unsupported_hypothesis')
        p['source']['existing_investigation']=True
        self.assert_code(lambda:semantic.validate(good,p),'existing_findings')

    def test_accounting_counts_failed_batches_once_and_survives_stale_journal(self):
        state={'items':{},'proposals':[],'semantic_requests':[],'semantic_cache':{}}
        for n in range(3):
            model={'returned_model':'nvidia/nemotron-fixture','http_status':200,
                'usage':{'prompt_tokens':100+n,'completion_tokens':10+n,'total_tokens':110+2*n}}
            state['semantic_requests'].append({'id':str(n),'authorization':semantic.AUTHORIZATION,'model':model})
            for c in range(5 if n<2 else 3):
                state['semantic_cache'][f'{n}-{c}']={'status':'failed','request_id':str(n),'model':copy.deepcopy(model)}
        state['semantic_requests']=state['semantic_requests'][:1]
        before=copy.deepcopy(state)
        result=assess_discovery.summary(state,cache_replay=True)
        self.assertEqual(result['requests_used'],3)
        self.assertEqual(result['confirmed_response_requests'],3)
        self.assertEqual(result['usage'],{'prompt_tokens':303,'completion_tokens':33,'total_tokens':336})
        self.assertEqual(result['new_requests_sent'],0)
        self.assertEqual(state,before)
        state['semantic_cache']['2-1']['model']['usage']['total_tokens']=999
        self.assertEqual(semantic.request_accounting(state)['usage_conflict_request_ids'],['2'])
        self.assertFalse(semantic.request_accounting(state)['usage_complete'])
        state['semantic_requests'].append({'id':'interrupted','authorization':semantic.AUTHORIZATION,'status':'started'})
        self.assertTrue(semantic.reconcile_request_journal(state))
        self.assertIn('interrupted',semantic.request_accounting(state)['request_ids'])
        self.assertEqual(semantic.request_accounting(state)['requests_used'],4)

    def test_three_failed_or_partial_batches_retained_replay_and_cache_are_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            feed=rss([(str(i),'Public capabilities') for i in range(10)]).replace(
                b'Publisher summary',b'Publisher summary about a capability with insufficient task-specific evidence.')
            store,_,_=fixtures.SemanticTests().initialize(tmp,feed)
            calls=[]
            def transport(token,messages):
                sources=json.loads(messages[1]['content'])['untrusted_sources'];calls.append(sources)
                values=[assessment(s) for s in sources]
                if len(calls)==1:content='{"assessments":['
                elif len(calls)==2:content=json.dumps({'assessments':[values[0]]*5})
                else:
                    values[-1]['evidence'][0]['exact_quote']='Unsupported quotation fabricated by a synthetic fixture.'
                    content=json.dumps({'assessments':values})
                return {'ok':True,'http_status':200,'data':{'model':'nvidia/nemotron-fixture',
                    'usage':{'prompt_tokens':100,'completion_tokens':200,'total_tokens':300},
                    'choices':[{'message':{'content':content},'finish_reason':'stop'}]}}
            state=semantic.run(store,'FIXTURE_SECRET_ONLY',context(),transport,lambda m:None)
            self.assertEqual(len(calls),3)
            self.assertEqual(assess_discovery.summary(state)['requests_used'],3)
            self.assertEqual(assess_discovery.summary(state)['validated'],2)
            codes=[i['semantic_assessment'].get('validation_failure',{}).get('code')
                for i in state['items'].values() if i['semantic_assessment'].get('validation_failure')]
            self.assertEqual(codes.count('invalid_json'),5)
            self.assertEqual(codes.count('batch_identity'),5)
            self.assertEqual(codes.count('quote_not_exact'),1)
            files=list((store.directory/'model-responses').glob('*.json'))
            self.assertEqual(len(files),3)
            self.assertTrue(all('FIXTURE_SECRET_ONLY' not in p.read_text(encoding='utf-8') for p in files))
            before=offline.memory_hashes(store.root)
            report=offline.diagnose(store,context())
            self.assertEqual(report['retained_full_responses'],3)
            self.assertEqual(sum(r['status']=='rejected' for r in report['revalidations']),11)
            self.assertEqual(report['recovered_assessments'],0)
            self.assertEqual(before,offline.memory_hashes(store.root))
            for p in files:p.unlink()  # Isolated fixtures only: exercise the original missing-data case.
            report=offline.diagnose(store,context())
            self.assertEqual(report['accepted_fragments_revalidated'],2)
            self.assertEqual(sum(r['status']=='unrecoverable' for r in report['revalidations']),11)
            with patch.object(semantic.analyzer,'request_claims',side_effect=AssertionError('No model allowed')):
                replay=semantic.run(store,'',context(),progress=lambda m:None)
            self.assertEqual(replay,state)

    def test_credential_echo_never_retained(self):
        with tempfile.TemporaryDirectory() as tmp:
            store,_,_=fixtures.SemanticTests().initialize(tmp)
            def transport(token,messages):
                return {'ok':True,'http_status':200,'data':{'model':'nvidia/nemotron-fixture',
                    'choices':[{'message':{'content':token}}]}}
            state=semantic.run(store,'FIXTURE_SECRET_ONLY',context(),transport,lambda m:None)
            self.assertTrue(all(i['semantic_assessment']['validation_failure']['code']=='credential_echo' for i in state['items'].values()))
            self.assertFalse((store.directory/'model-responses').exists())
            self.assertNotIn('FIXTURE_SECRET_ONLY',json.dumps(state))


if __name__=='__main__':unittest.main()
