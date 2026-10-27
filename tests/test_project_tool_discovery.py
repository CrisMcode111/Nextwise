"""Project-driven discovery with synthetic source pages and no external calls."""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from test_tool_discovery import d, app, dispatch, ROOT, NOW

SOURCES=d.project_tools()
PHRASES=json.loads((ROOT/'tests/fixtures/project_tools.json').read_text(encoding='utf-8'))


def source_fetch(url):
    source=next(source for source in SOURCES if source['url']==url)
    return {'raw':f"<html><title>{source['name']} docs</title><p>{PHRASES[source['name']]}</p></html>".encode(),'error':None}


class ProjectToolTests(unittest.TestCase):
    def setUp(self):
        guard=patch.dict('os.environ',{'TAVILY_API_KEY':''})
        guard.start();self.addCleanup(guard.stop)
        for name in ('socket.socket','update_discovery.memory.call_bridge'):
            guard=patch(name,side_effect=AssertionError('Network or memory forbidden'))
            guard.start();self.addCleanup(guard.stop)

    def preview(self, existing=(), **kwargs):
        return d.catalog_tool_preview(existing,fetcher=source_fetch,now=NOW,**kwargs)

    def test_project_needs_existing_products_and_source_grounding(self):
        result=self.preview()
        self.assertEqual(len(result['scope']['needs']),3)
        self.assertEqual(len(result['candidates']),3)
        self.assertEqual(result['scope']['mode'],'project')
        for item in result['candidates']:
            self.assertIsNone(item['publication_date'])
            self.assertEqual(item['description'],PHRASES[item['title']])
            self.assertEqual(item['supporting_phrases'],[item['description']])
            self.assertEqual(item['label'],d.TOOL_LABEL)
            self.assertTrue(item['limitations'])
            self.assertTrue(item['reasons'])
            self.assertNotIn('recommended_choice',item)
        unrelated={'objective':'Manage invoices','task':'Send reminders','constraints':[]}
        with patch.object(d,'fetch',side_effect=AssertionError('Unrelated project must not fetch')):
            self.assertEqual(d.tool_preview([],project=unrelated)['candidates'],[])

    def test_human_reject_defer_aliases_and_changed_page_stay_suppressed(self):
        decisions=[{'candidate_id':'old-instructor','version':1,'choice':'Defer','title':'Review Instructor extraction'},
                   {'candidate_id':'old-pydantic','version':1,'choice':'Reject','evidence_references':{'url':'https://docs.pydantic.dev/older-page'}}]
        original=copy.deepcopy(decisions)
        result=self.preview(decision_history=decisions)
        self.assertEqual([item['title'] for item in result['candidates']],['promptfoo'])
        self.assertEqual(decisions,original)
        decisions.append({'candidate_id':'old-instructor','version':2,'choice':'Test','title':'Instructor'})
        self.assertEqual([item['title'] for item in self.preview(decision_history=decisions)['candidates']],['Instructor','promptfoo'])
        self.assertEqual([item['title'] for item in self.preview([{'title':'Using Instructor for extraction','url':'https://example.invalid/old'}])['candidates']],['Pydantic','promptfoo'])
        with self.assertRaises(ValueError):self.preview(decision_history=[{'choice':'Reject'}])

    def test_failures_no_evidence_no_identity_and_dedup(self):
        calls=[]
        def fail(url):calls.append(url);return {'raw':b'','error':'Unavailable'}
        result=d.catalog_tool_preview([],fetcher=fail,now=NOW)
        self.assertEqual(calls,[source['url'] for source in SOURCES])
        self.assertEqual(result['candidates'],[])
        self.assertEqual(result['status'],'partial_failure')
        for raw in (b'<html><p>Generic AI news.</p></html>',
                    b'<title>Instructor</title><p>Company news and funding updates only.</p>',
                    b'<title>Instructor</title><p>This product does not support structured output extraction from LLMs.</p>'):
            result=d.tool_preview([],fetcher=lambda url:{'raw':raw,'error':None},sources=[SOURCES[0]],now=NOW)
            self.assertEqual(result['candidates'],[])
        result=self.preview(sources=[SOURCES[0],SOURCES[0]])
        self.assertEqual(len(result['candidates']),1)

    def test_api_uses_cached_decisions_and_never_reads_memory(self):
        import semantic_discovery as semantic
        with tempfile.TemporaryDirectory() as tmp, patch.object(semantic.analyzer,'request_claims',side_effect=AssertionError('Model forbidden')):
            state=app.State(tmp)
            state.tool_existing_items=[]
            state.tool_human_history=[]
            state.tool_opportunity_history=[{'candidate_id':'old','version':1,'choice':'Defer','title':'Instructor'}]
            original=d.tool_preview
            class Thread:
                def __init__(self,target,**kwargs):self.target=target
                def start(self):self.target()
            with patch.object(app.threading,'Thread',Thread), patch.object(d,'tool_preview',side_effect=lambda items,**kw:original(items,fetcher=source_fetch,now=NOW,**kw)):
                self.assertEqual(dispatch(state,'/api/discovery/check?scope=tools','POST')[0],202)
                code,result=dispatch(state,'/api/discovery?scope=tools')
                self.assertEqual(code,200)
                self.assertEqual([item['title'] for item in result['tool_preview']['candidates']],['Pydantic','promptfoo'])
            self.assertEqual(list(Path(tmp).iterdir()),[])

    def test_existing_history_response_mapping_and_ui(self):
        state=app.State()
        app.cache_tool_decisions(state,{'history':[{'investigation_id':app.INVESTIGATION,'choice':'Defer','version':1,'evidence_references':[]}]})
        self.assertIn('Nemotron',state.tool_human_history[0]['technology'])
        self.assertEqual(len(self.preview(decision_history=state.tool_human_history)['candidates']),3)
        saved={'items':{},'opportunity_recommendations':[{'id':'r','title':'Instructor'}],
               'opportunity_decisions':[{'recommendation_id':'r','candidate_id':'old','choice':'Reject','version':1}]}
        before=copy.deepcopy(saved)
        app.cache_tool_discovery(state,saved)
        self.assertEqual(state.tool_opportunity_history[0]['title'],'Instructor')
        self.assertEqual(saved,before)
        with patch.object(Path,'read_text',side_effect=FileNotFoundError):
            app.cache_tool_decisions(state,{'history':[]})
        self.assertIsNone(state.tool_human_history)
        result=subprocess.run(['node',str(ROOT/'tests/tool_discovery_ui.cjs')],input=json.dumps(self.preview()),text=True,capture_output=True,cwd=ROOT)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)


if __name__=='__main__':unittest.main()
