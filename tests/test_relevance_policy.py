"""Context-aware deterministic triage and non-destructive persisted migration."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import update_discovery as d
import semantic_discovery as semantic
from semantic_fixture import context as semantic_context
from test_update_discovery import Fixture, NOW

class RelevancePolicyTests(unittest.TestCase):
    def assess(self,text):return d.relevance(text,d.context())

    def test_ambiguous_extraction_and_deployment_are_not_task_evidence(self):
        for text in ['Cloud deployment incoming. A new campaign brings high-stakes extraction mode to supported devices.',
                     'A mineral extraction plant reduces deployment costs.',
                     'Structured requirements for bridge deployment and memory upgrades.',
                     'Nemotron deployment cost and latency.',
                     'A language model is announced. Unrelated structured outputs appear in another context.']:
            result=self.assess(text)
            self.assertEqual(result['matches'],[],text)
            self.assertEqual(result['category'],'uncertain relevance',text)
            self.assertIn('Insufficient context',result['explanation'])

    def test_structured_output_and_requirements_phrases_have_explicit_support(self):
        for text in ['A language model supports structured outputs for extracting user requirements.',
                     'The tool extracts user constraints into JSON schema constrained outputs.']:
            r=self.assess(text)
            self.assertEqual(r['category'],'potential relevance')
            self.assertEqual(r['matches'][0]['rule'],'structured_requirement_capability')
            self.assertIn(r['matches'][0]['supporting_phrase'],text)
            self.assertEqual(r['policy_version'],d.RELEVANCE_POLICY)
            self.assertIn('Provisional',r['label'])

    def test_concrete_model_integration_not_generic_infrastructure(self):
        for text in ['This LLM exposes an OpenAI-compatible API with inference pricing.',
                     'The language model has documented RAM requirements for local use.']:
            r=self.assess(text)
            self.assertEqual(r['category'],'potential relevance')
            self.assertEqual(r['matches'][0]['rule'],'model_integration_need')
        for text in ['AI factories deploy models across infrastructure.',
                     'The language model does not support structured outputs.',
                     'An LLM '+('supports general applications '*30)+'has an OpenAI-compatible API.']:
            self.assertFalse(self.assess(text)['matches'])

    def test_constrained_recipe_capability_and_low_relevance(self):
        self.assertEqual(self.assess('The service generates recipes from dietary preferences.')['category'],'potential relevance')
        self.assertEqual(self.assess('Team wins championship.')['category'],'low relevance')
        self.assertFalse(self.assess('A recipe book launch.')['matches'])

    def test_policy_migration_preserves_sources_history_proposals_and_dedup(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=d.Store(tmp);fixture=Fixture();state=store.run(fixture,now=NOW)
            legacy={'label':'Provisional keyword/rule matches; no Nemotron reasoning or verified suitability',
                    'category':'potential relevance','matches':[{'connection':'Task: structured user-requirement extraction','terms':['extraction']}],
                    'explanation':'Review the matched terms in context.','project_context':d.context()}
            for item in state['items'].values():
                item['relevance']=copy.deepcopy(legacy);item.pop('relevance_history')
            store.save(state)
            chosen=next(iter(state['items'].values()))
            state=store.read()
            state['proposals'].append({'id':'ISOLATED_LEGACY','origin':'human','candidate_id':chosen['id'],'selection_reason':'Historical fixture selection'})
            state=store.save(state)
            before=copy.deepcopy(state)
            snapshots={str(p):d.sha(p.read_bytes()) for p in store.directory.rglob('*.raw')}
            with patch.object(semantic,'project_context',return_value=semantic_context()):migrated=store.reassess()
            self.assertEqual(migrated['runs'],before['runs']);self.assertEqual(migrated['baselines'],before['baselines'])
            self.assertEqual(migrated['proposals'],before['proposals'])
            for key,item in migrated['items'].items():
                self.assertEqual(item['revisions'],before['items'][key]['revisions'])
                self.assertEqual(item['first_seen'],before['items'][key]['first_seen'])
                self.assertEqual(item['relevance_history'][0]['assessment'],legacy)
                self.assertEqual(item['relevance_history'][0]['policy_version'],'legacy-keywords-v1')
                self.assertEqual(item['relevance'],legacy)
                self.assertEqual(item['semantic_assessment']['status'],'pending')
            self.assertEqual(snapshots,{str(p):d.sha(p.read_bytes()) for p in store.directory.rglob('*.raw')})
            with patch.object(semantic,'project_context',return_value=semantic_context()):self.assertEqual(d.Store(tmp).reassess(),migrated)
            self.assertEqual(d.Store(tmp).read()['proposals'],before['proposals'])
            unchanged=store.run(fixture,now=NOW)
            self.assertEqual(unchanged['runs'][-1]['events'],[])
            self.assertEqual(unchanged.get('reassessments'),migrated.get('reassessments'))
            fixture.page='Changed public page with meaningful text. '*12
            changed=store.run(fixture,now=NOW)
            page=next(i for i in changed['items'].values() if i['source']!=d.FEED)
            self.assertEqual(len(page['relevance_history']),1)
            self.assertEqual(page['relevance_history'][0]['assessment'],legacy)

if __name__=='__main__':unittest.main()
