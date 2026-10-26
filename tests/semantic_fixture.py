"""Explicit synthetic model transport; never sends HTTP or uses real credentials."""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import semantic_discovery as semantic
import update_discovery as discovery

def context():
    profile={**discovery.context(), 'id':'ai-raw-gourmet'}
    return {'profile':profile,'use_case':{'investigated_task':{'description':profile['task']}},
        'existing_investigation':{'id':semantic.INVESTIGATION,'question':'Bounded requirement extraction trial?'},
        'registered_sources':[{'id':discovery.collector.stable_source_id(url),'requested_url':url} for url in discovery.config()['pages']],
        'pilot_findings':{'quality_pass_cases':1,'attempted_cases':4,'limitations':['Synthetic lexical scorer, not production accuracy.']},
        'human_decision':{'choice':'Defer','version':1,'rationale':'ISOLATED TEST ONLY: resolve unknown acceptance criteria.'},
        'provenance':{'manifest_id':'ISOLATED_FIXTURE','decision_record_sha256':'f'*64}}

def assessment(source,positive=False):
    text=source['passages'][0]['text']
    return {'candidate_id':source['candidate_id'],'category':'potential relevance' if positive else 'uncertain relevance',
        'project_need_id':'extraction_task' if positive else 'uncertain',
        'project_need':'Preserve explicit user constraints in structured requirements.' if positive else 'Insufficient task-specific evidence to establish a project need.',
        'source_observation':'The supplied passage describes '+text[:100],
        'evidence':[{'source_id':source['source_id'],'passage_id':source['passages'][0]['passage_id'],'exact_quote':text[:min(180,len(text))]}] if len(text)>=20 else [],
        'application_hypothesis':'Hypothesis: test structured requirement extraction in isolation against defined criteria.' if positive else None,
        'limitations':['Publisher descriptions do not verify project suitability or accuracy.'],
        'missing_information':['Task acceptance criteria, integration effort and verified pricing remain unknown.'],
        'priority':'medium' if positive else 'defer','priority_reason':'Resolve task evidence and Defer conditions before considering further work.',
        'investigation_question':'What evidence would establish compatibility and task-specific correctness?',
        'next_step':'Review existing gaps and specify an evidence-only follow-up; do not rerun the pilot.',
        'existing_findings_connection':'The existing 1/4 saved pilot has lexical limitations; genuine Defer Version 1 remains in force.' if source['existing_investigation'] else None}

class Transport:
    def __init__(self,fail=False):self.calls=[];self.fail=fail
    def __call__(self,token,messages):
        self.calls.append(messages)
        if self.fail:return {'ok':False,'http_status':503}
        sources=json.loads(messages[1]['content'])['untrusted_sources']
        values=[assessment(s,positive='structured outputs' in ' '.join(p['text'] for p in s['passages']).lower()) for s in sources]
        return {'ok':True,'http_status':200,'duration_seconds':.01,'data':{'model':'nvidia/nemotron-fixture-only',
            'usage':{'prompt_tokens':100,'completion_tokens':200,'total_tokens':300},
            'choices':[{'message':{'content':json.dumps({'assessments':values})}}]}}
