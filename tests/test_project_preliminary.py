"""Focused offline preliminary-view checks; no inference or saved mutations."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from project_preliminary import previews
from project_workflow import Projects

PROJECT = 'project-9d95b23e5f28432595742ef0ece67607'
DIRECTORY = ROOT / 'data/memory/hmem/projects' / PROJECT / 'update-discovery'


class PreliminaryRuleTests(unittest.TestCase):
    def setUp(self):
        self.state = {'project': {'id': 'synthetic', 'name': 'Example Bookshop',
            'brief': 'Goal: improve our bookshop product for customer preferences and constraints.',
            'context_sha256': 'synthetic-context'}, 'items': {'saved': {'id': 'saved',
            'title': 'Bookshop API filtering', 'url': 'https://example.invalid/bookshop',
            'source': 'tavily-page', 'kind': 'saved_page'}}, 'assessments': [], 'decisions': []}
        self.claim = {'source_id': 'saved', 'passage_id': 'p1',
            'exact_quote': 'Bookshop API: filter by genre, language, and availability.', 'claim_kind': 'publisher_claim'}
        self.adapter = SimpleNamespace(prepare_assessment=lambda *args: {'staged_plan': {'claims': [self.claim]}})

    def test_reusable_other_industry_and_read_only_conditional_output(self):
        before = copy.deepcopy(self.state)
        result = previews(self.adapter, None, self.state)
        self.assertEqual(len(result), 1)
        self.assertIn('genre, language, and availability', result[0]['possible_improvement'])
        self.assertTrue(result[0]['possible_improvement'].startswith('If Example Bookshop does not already'))
        self.assertEqual(result[0]['publisher_evidence']['exact_quote'], self.claim['exact_quote'])
        self.assertIn(result[0]['project_basis']['exact_quote'], self.state['project']['brief'])
        self.assertEqual(self.state, before)

    def test_no_shared_subject_or_unresolved_language_means_no_preview(self):
        for brief in ('Goal: improve our clinic for patient requirements and constraints.',
                      'Objectif: adapter les recettes aux besoins des familles.'):
            with self.subTest(brief=brief):
                self.state['project']['brief'] = brief
                self.assertEqual(previews(self.adapter, None, self.state), [])

    def test_no_stated_constraint_goal_means_no_preview(self):
        self.state['project']['brief'] = 'Goal: improve our bookshop product for local customers.'
        self.assertEqual(previews(self.adapter, None, self.state), [])

    def test_human_decision_and_existing_assessment_are_not_overridden(self):
        for choice in ('Defer', 'Reject'):
            self.state['decisions'] = [{'id': 'decision', 'candidate_id': 'saved', 'version': 1, 'choice': choice}]
            self.assertEqual(previews(self.adapter, None, self.state), [])
        self.state['decisions'] = []
        self.state['assessments'] = [{'candidate_id': 'saved'}]
        self.assertEqual(previews(self.adapter, None, self.state), [])

    def test_failed_integrity_and_negated_or_missing_capabilities_abstain(self):
        with patch.object(self.adapter, 'prepare_assessment', side_effect=ValueError('hash mismatch')):
            self.assertEqual(previews(self.adapter, None, self.state), [])
        for quote in ('Bookshop API cannot filter by genre, language, and availability.',
                      'Bookshop posts are temporarily unavailable.',
                      'Bookshop API: if enabled, filter by genre and language.',
                      'Bookshop brochure: filter by genre and language.'):
            self.claim['exact_quote'] = quote
            self.assertEqual(previews(self.adapter, None, self.state), [])

    def test_frontend_renders_preview_separately_without_authorization_controls(self):
        preview = previews(self.adapter, None, self.state)[0]
        program = r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
class Element {constructor(){this.children=[];this.textContent='';} append(n){this.children.push(n);}
replaceChildren(){this.children=[];}setAttribute(){}}
const elements=new Map(),preview=JSON.parse(fs.readFileSync(0,'utf8'));
const context=vm.createContext({URL,crypto:{randomUUID:()=> 'unused'},
document:{createElement:()=>new Element(),querySelector:s=>{if(!elements.has(s))elements.set(s,new Element());return elements.get(s);}},
fetch:path=>{assert.equal(path,'/api/projects');return new Promise(()=>{});},preview});
vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),context);
vm.runInContext('project={preliminary_previews:[preview]};renderPreliminaryPreviews()',context);
const text=n=>n.textContent+' '+n.children.map(text).join(' ');
const root=elements.get('#preliminary-previews'), content=text(root);
assert.equal(root.children.length,1);assert.equal(elements.get('#preliminary-section').hidden,false);
for(const v of [preview.label,preview.source_url,preview.project_area,preview.why_relevant,
preview.possible_improvement,preview.next_action,preview.project_basis.exact_quote,preview.publisher_evidence.exact_quote])assert.ok(content.includes(v),v);
assert.equal(elements.has('#opportunities'),false);
assert.equal(elements.has('#briefings'),false);
'''
        result = subprocess.run(['node', '-e', program, str(ROOT / 'web/projects.js')],
                                input=json.dumps(preview), text=True, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)


@unittest.skipUnless((DIRECTORY / 'state.json').is_file(), 'Saved project required')
class SavedProjectPreviewTests(unittest.TestCase):
    def test_real_saved_source_is_visible_without_writes_or_provider_calls(self):
        before = {p: hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in DIRECTORY.rglob('*') if p.is_file()}
        with patch('socket.socket', side_effect=AssertionError('No external requests')), \
             patch('project_adapters.assess', side_effect=AssertionError('No inference')), \
             patch('tavily_discovery.search', side_effect=AssertionError('No search')):
            p = Projects(ROOT / 'data/memory/hmem')
            state = p.read(PROJECT)
            result = state['preliminary_previews']
            self.assertEqual(state['version'], 32)
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]['candidate_id'], 'recipe-api-com-1db17c9da495')
            self.assertEqual(result[0]['label'], 'Preliminary — not AI-validated')
            self.assertIn('macros, dietary tags, and ingredients', result[0]['possible_improvement'])
            self.assertIn(result[0]['project_basis']['exact_quote'], state['project']['brief'])
            self.assertEqual(state['selected_opportunities'], [])
            self.assertEqual(sum(o['action']=='assess' for o in state['operations'].values()), 5)
            self.assertEqual(state['decisions'][0]['choice'], 'Defer')
        self.assertEqual({p: hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in DIRECTORY.rglob('*') if p.is_file()}, before)


if __name__ == '__main__':
    unittest.main()
