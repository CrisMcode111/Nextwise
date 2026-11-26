"""Packaged online handler and frontend, with deterministic offline transports."""
import importlib.util
import base64
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import build_online_mvp

QUOTE='The synthetic AI scheduling service supports appointment reminders for clinics.'


class OnlineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='nextwise-online-test-'); cls.addClassCleanup(cls.temp.cleanup)
        cls.path=Path(cls.temp.name)/'bundle';build_online_mvp.build(cls.path)
        spec=importlib.util.spec_from_file_location('online_packaged_api',cls.path/'api/index.py')
        cls.api=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.api)

    def dispatch(self, access='x'*32, path='/api/index', data=None):
        payload=json.dumps(data or {'project':'A small clinic needs help with appointment scheduling.'}).encode()
        class Connection:
            def __init__(self): self.output=bytearray()
            def makefile(self,*a): return io.BytesIO((f'POST {path} HTTP/1.1\r\nHost: example.test\r\nContent-Type: application/json\r\nX-Nextwise-Access: {access}\r\nContent-Length: {len(payload)}\r\n\r\n').encode()+payload)
            def sendall(self,data): self.output.extend(data)
        conn=Connection();self.api.handler(conn,('127.0.0.1',0),SimpleNamespace(server_port=80))
        header,body=bytes(conn.output).split(b'\r\n\r\n',1)
        return int(header.split()[1]),json.loads(body)

    def test_bundle_is_allowlisted_and_contains_no_demo_recommendations(self):
        files={str(p.relative_to(self.path)).replace('\\','/') for p in self.path.rglob('*')
               if p.is_file() and '__pycache__' not in p.parts}
        self.assertEqual(files,build_online_mvp.EXPECTED)
        html=(self.path/'public/index.html').read_text(encoding='utf-8')
        js=(self.path/'public/demo.js').read_text(encoding='utf-8')
        self.assertIn('Discover AI opportunities',html)
        self.assertNotIn('GUIDED_SCENARIO',js)
        self.assertNotIn('data/memory',html+js)

    def test_packaged_handler_pipeline_and_frontend(self):
        calls=[]
        def provider(url,token,body,timeout):
            if 'tavily.com' in url:
                calls.append('search');self.assertEqual(body['search_depth'],'basic')
                return {'results':[{'url':'https://example.com/source','title':'Synthetic source','content':QUOTE}]}
            calls.append('model')
            schema=body['text']['format']['schema']
            if schema is self.api.online.PLAN:
                value={'understanding':'Clinic needs better appointment scheduling.','clarifications':[],
                       'queries':['recent AI appointment scheduling for clinics']}
            else:
                value={'recommendations':[{'innovation':'Synthetic scheduling innovation','project_area':'Bookings',
                'improvement':'Review appointment reminders','relevance':'Could support clinic booking',
                'feasibility':'Unknown','cost':'Unknown','effort':'Unknown','uncertainty':'Not tested',
                'next_action':'Review an example','source_id':'1','source_quote':QUOTE}]}
            return {'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(value)}]}]}
        with patch.dict('os.environ',{'NEXTWISE_ACCESS_TOKEN':'x'*32,'OPENAI_API_KEY':'test','TAVILY_API_KEY':'test'}), \
             patch.object(self.api.online,'post_json',side_effect=provider):
            code,result=self.dispatch()
            self.assertEqual(code,200);self.assertEqual(calls,['model','search','model'])
            self.assertEqual(result['recommendations'][0]['source_quote'],QUOTE)
            self.assertIsNone(result['recommendations'][0]['publication_date'])
            code,_=self.dispatch('incorrect');self.assertEqual(code,403);self.assertEqual(len(calls),3)
        payload=json.dumps({'script':str(self.path/'public/demo.js'),'result':result})
        subprocess.run(['node',str(ROOT/'tests/online_mvp_ui.cjs')],input=payload,text=True,check=True,timeout=10)

    def test_bad_evidence_never_becomes_recommendation(self):
        calls=[]
        def model(prompt,schema,timeout):
            calls.append(1)
            if schema is self.api.online.PLAN: return {'understanding':'A clinic','clarifications':[], 'queries':['recent clinic AI scheduling tools']}
            item={k:'invented' for k in self.api.online.ITEM['properties']};item['source_id']='1'
            return {'recommendations':[item]}
        result=self.api.online.discover('A clinic needs better appointment scheduling.',model=model,
            search=lambda q,t:{'results':[{'url':'https://example.com/source','content':QUOTE}]})
        self.assertEqual(result['recommendations'],[]);self.assertEqual(len(calls),2)

    def test_limits_clarification_and_no_automatic_retry(self):
        calls=[]
        def model(prompt,schema,timeout):
            calls.append('model')
            if schema is self.api.online.PLAN:
                return {'understanding':'A clinic','clarifications':[],
                        'queries':['recent clinic AI booking tools','recent clinic AI scheduling tools','recent AI clinic reminders']}
            return {'recommendations':[]}
        def search(query,timeout):
            calls.append('search')
            return {'results':[{'url':'https://example.com/'+str(len(calls)), 'content':QUOTE}]}
        self.api.online.discover('A clinic needs better appointment scheduling.',model=model,search=search)
        self.assertEqual(calls,['model','search','search','search','model'])
        calls.clear()
        result=self.api.online.discover('A clinic needs better appointment scheduling.',
            model=lambda p,s,t:{'understanding':'Unclear','clarifications':['What is the objective?'],'queries':[]},
            search=lambda q,t:self.fail('Clarification must not dispatch search'))
        self.assertEqual(result['clarifications'],['What is the objective?'])
        def fail(query,timeout): calls.append('search');raise OSError('offline')
        with self.assertRaises(OSError):
            self.api.online.discover('A clinic needs better appointment scheduling.',model=model,search=fail)
        self.assertEqual(calls,['model','search'])

    def test_github_is_fixed_host_public_and_reviewable(self):
        module=self.api.github_ingestion
        paths=[]
        def fetch(path):
            paths.append(path)
            if path.endswith('/readme'):
                return {'encoding':'base64','content':base64.b64encode(b'An example public README').decode()}
            return {'private':False,'description':'A synthetic public repository'}
        result=module.extract('https://github.com/example/project',fetch=fetch)
        self.assertIn('example public README',result['text'])
        self.assertEqual(paths,['/repos/example/project','/repos/example/project/readme'])
        for url in ('http://github.com/a/b','https://github.com.evil.test/a/b',
                    'https://github.com/a/b/extra','https://user@github.com/a/b'):
            with self.assertRaises(ValueError):module.repository(url)
        with self.assertRaises(ValueError):
            module.extract('https://github.com/a/b',fetch=lambda p:{'private':True})
        with patch.dict('os.environ',{'NEXTWISE_ACCESS_TOKEN':'x'*32}), patch.object(module,'extract',return_value=result):
            code,returned=self.dispatch(path='/api/github',data={'url':'https://github.com/example/project'})
            self.assertEqual(code,200);self.assertEqual(returned,result)
