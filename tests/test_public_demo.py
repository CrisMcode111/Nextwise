"""Offline public deployment checks: isolated bundle, real handlers and UI, mocked sources."""
import importlib.util
import hashlib
import io
import json
from html.parser import HTMLParser
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import build_vercel_demo as builder

PHRASES={'instructor':'Instructor extracts structured data from LLMs using explicit output schemas and validation.',
         'pydantic':'Pydantic provides data validation using Python type hints and structured schemas.',
         'promptfoo':'promptfoo provides evaluation of LLM outputs using explicit fixtures and assertions.'}


def repository_fixture(name,description):
    """Synthetic GitHub-shaped record; never claimed as a live discovery."""
    full_name='fixture-owner/'+name
    return {'name':name,'full_name':full_name,'owner':{'login':'fixture-owner'},
        'url':'https://api.github.com/repos/'+full_name,'html_url':'https://github.com/'+full_name,
        'description':description,'private':False,'fork':False,'archived':False,'disabled':False,
        'created_at':'2025-01-01T00:00:00Z','pushed_at':'2026-01-01T00:00:00Z'}


def business_repository_fixture(need):
    descriptions={
        'meal_planning':'An online AI assistant for meal planning that adapts recipes to customer food preferences.',
        'customer_support':'A no-code AI customer support service for answering customer questions through an online dashboard.',
        'appointments':'An online AI scheduling app for customer bookings, appointments and reminders.',
        'marketing_content':'An online AI marketing app for social media content creation and short promotional posts.',
        'business_admin':'An online AI document assistant for handling invoices and receipts through a browser dashboard.'}
    item=repository_fixture('Fixture-'+need,descriptions[need]);item['homepage']='https://'+need.replace('_','-')+'.example/'
    return item


def dispatch(api,path,method='GET',headers=None):
    class Connection:
        def __init__(self):self.output=bytearray()
        def makefile(self,*args):
            lines=[f'{method} {path} HTTP/1.1','Host: public-demo.example','Connection: close']
            lines += [f'{key}: {value}' for key,value in (headers or {}).items()]
            return io.BytesIO(('\r\n'.join(lines)+'\r\n\r\n').encode())
        def sendall(self,data):self.output.extend(data)
    connection=Connection()
    api.handler(connection,('127.0.0.1',0),SimpleNamespace(server_port=8769))
    headers,body=bytes(connection.output).split(b'\r\n\r\n',1)
    return int(headers.split()[1]),json.loads(body),headers.decode()


class PublicDemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='nextwise-public-offline-');cls.addClassCleanup(cls.temp.cleanup)
        cls.bundle=Path(cls.temp.name)/'upload'
        cls.report=builder.build(cls.bundle)
        spec=importlib.util.spec_from_file_location('nextwise_public_api',cls.bundle/'api/index.py')
        cls.api=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.api)

    def setUp(self):
        for guard in (patch('socket.socket',side_effect=AssertionError('External network forbidden')),
                      patch('subprocess.Popen',side_effect=AssertionError('Service/model subprocess forbidden'))):
            guard.start();self.addCleanup(guard.stop)

    def fixture_fetch(self,url):
        source=next(source for source in self.api.SOURCES if source['url']==url)
        return {'raw':f"<title>{source['name']}</title><p>{PHRASES[source['id']]}</p>".encode(),'error':None}

    def test_allowlisted_bundle_and_shared_code_not_private_data(self):
        files={str(p.relative_to(self.bundle)).replace('\\','/') for p in self.bundle.rglob('*') if p.is_file()}
        self.assertEqual(files,builder.EXPECTED)
        combined='\n'.join(p.read_text(encoding='utf-8') for p in self.bundle.rglob('*') if p.is_file())
        for forbidden in ('nemotron-lightning-requirements-extraction','data/memory','subprocess',
                          'state.discovery','TAVILY_API_KEY','api.tavily.com','localhost:8888','127.0.0.1:8088'):
            self.assertNotIn(forbidden,combined)
        shared=(self.bundle/'public/app.js').read_text(encoding='utf-8')
        original=(ROOT/'web/app.js').read_text(encoding='utf-8')
        self.assertIn(builder.js_between(original,'function paintToolCandidates(','async function readDiscovery('),shared)
        self.assertNotIn("fetch('/api/status')",shared)
        config=json.loads((self.bundle/'vercel.json').read_text())
        self.assertEqual(config['outputDirectory'],'public')
        self.assertEqual(config['functions']['api/index.py']['maxDuration'],15)
        self.assertEqual(len(config['rewrites']),3)
        self.assertEqual((ROOT/'.vercelignore').read_text().strip().splitlines()[-1],'**')

    def test_build_never_reads_private_records_and_refuses_extra_upload_files(self):
        allowed={ROOT/'web/app.js',ROOT/'deploy/vercel_demo/index.html',ROOT/'web/style.css',ROOT/'scripts/update_discovery.py',
                 ROOT/'scripts/collect_sources.py',ROOT/'scripts/tavily_discovery.py',ROOT/'deploy/vercel_demo/search.py',ROOT/'deploy/vercel_demo/api.py',ROOT/'deploy/vercel_demo/demo.js',ROOT/'deploy/vercel_demo/style.css',ROOT/'deploy/vercel_demo/project.js',ROOT/'deploy/vercel_demo/business_needs.json'}
        allowed.add(ROOT/'deploy/vercel_demo/guided_opportunities.json')
        allowed.update(ROOT/'deploy/vercel_demo/pdfjs'/name for name in ('pdf.mjs','pdf.worker.mjs','LICENSE','provenance.json'))
        original=Path.read_text
        def checked(path,*args,**kwargs):
            self.assertIn(path.resolve(),allowed)
            return original(path,*args,**kwargs)
        with tempfile.TemporaryDirectory() as tmp,patch.object(Path,'read_text',checked):
            builder.build(Path(tmp)/'upload')
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);(path/'private-record.json').write_text('DO NOT UPLOAD')
            with self.assertRaises(ValueError):builder.build(path)
            self.assertTrue((path/'private-record.json').exists())
        with self.assertRaises(ValueError):builder.build(ROOT)

    def test_pdf_parser_is_pinned_self_hosted_and_license_is_bundled(self):
        provenance=json.loads((self.bundle/'public/pdfjs/provenance.json').read_text())
        self.assertEqual(provenance['version'],'6.4.299')
        for name,digest in provenance['sha256'].items():
            self.assertEqual(hashlib.sha256((self.bundle/'public/pdfjs'/name).read_bytes()).hexdigest(),digest)
        self.assertIn('Apache License',(self.bundle/'public/pdfjs/LICENSE').read_text())

    def test_two_panel_homepage_has_local_project_inputs_and_collapsed_details(self):
        class Page(HTMLParser):
            def __init__(self):super().__init__();self.tags=[];self.details=[]
            def handle_starttag(self,tag,attrs):
                self.tags.append(tag)
                if tag=='details':self.details.append(dict(attrs))
        page=Page();page.feed((self.bundle/'public/index.html').read_text(encoding='utf-8'))
        for tag in ('nav','form','select'):self.assertNotIn(tag,page.tags)
        self.assertEqual(page.tags.count('textarea'),1)
        self.assertEqual(len(page.details),1)
        self.assertNotIn('open',page.details[0])
        html=(self.bundle/'public/index.html').read_text(encoding='utf-8')
        self.assertNotIn('check-updates',html)
        self.assertNotIn('reload-discovery',html)
        self.assertIn('PUBLIC DEMO',html)
        self.assertIn('assistant-layout',html)
        self.assertIn('project-file',html)
        self.assertIn('Nothing from your project or file is uploaded or saved.',html)
        config=json.loads((self.bundle/'vercel.json').read_text())
        self.assertIn("worker-src 'self'",next(header['value'] for header in config['headers'][0]['headers'] if header['key']=='Content-Security-Policy'))

    def test_demo_metadata_is_new_example_context_and_environment_is_ignored(self):
        with patch.dict('os.environ',{'TAVILY_API_KEY':'DO_NOT_EXPOSE_TAVILY','ZETARIS_API_KEY':'DO_NOT_EXPOSE_SQL'}), \
             patch.object(self.api,'fetch_public',side_effect=AssertionError('No fetch during initialization')):
            code,result,headers=dispatch(self.api,'/api/demo')
        self.assertEqual(code,200)
        self.assertEqual(result['mode'],'public_demo')
        self.assertFalse(result['tavily_enabled'])
        self.assertEqual(result['decision_storage'],'browser_only')
        self.assertIn('example',result['project']['name'])
        self.assertNotIn('history',result)
        self.assertNotIn('DO_NOT_EXPOSE',json.dumps(result))
        self.assertIn('no-store',headers)
        self.assertIn("default-src 'self'",headers)

    def test_one_source_per_request_live_label_and_real_evidence_algorithm(self):
        with patch.object(self.api,'fetch_public',side_effect=self.fixture_fetch) as fetch, \
             patch.object(Path,'open',side_effect=AssertionError('Runtime file reads/writes forbidden')):
            code,result,_=dispatch(self.api,'/api/discover?source=instructor')
        self.assertEqual(code,200);self.assertEqual(fetch.call_count,1)
        self.assertEqual(result['mode'],'public_demo')
        self.assertEqual(len(result['candidates']),1)
        candidate=result['candidates'][0]
        self.assertEqual(candidate['description'],PHRASES['instructor'])
        self.assertEqual(candidate['demo_source_id'],'instructor')
        self.assertEqual(candidate['label'],'Discovery candidate — not yet validated')
        self.assertIn('Live public-page',result['notice'])

    def test_vercel_rewrite_preserves_original_path_and_adds_route_query(self):
        with patch.object(self.api,'fetch_public',side_effect=AssertionError('No fetch during initialization')):
            code,result,_=dispatch(self.api,'/api/demo?route=demo')
        self.assertEqual(code,200)
        self.assertEqual(result,self.api.demo_data())
        with patch.object(self.api,'fetch_public',side_effect=self.fixture_fetch) as fetch:
            code,result,_=dispatch(self.api,'/api/discover?route=discover&source=instructor')
        self.assertEqual(code,200)
        self.assertEqual(result['source_id'],'instructor')
        self.assertEqual(fetch.call_count,1)
        with patch.object(self.api,'fetch_public',side_effect=AssertionError('No fetch for bad rewrite')):
            for path in ('/api/demo?route=discover','/api/discover?route=demo&source=instructor',
                         '/api/demo?route=demo&route=demo','/api/demo?route=',
                         '/api/demo?route=demo&extra=1',
                         '/api/discover?route=discover&source=http://localhost:8888'):
                self.assertIn(dispatch(self.api,path)[0],(400,404))

    def test_private_write_proxy_and_arbitrary_source_routes_are_rejected(self):
        with patch.object(self.api,'fetch_public',side_effect=AssertionError('No fetch for bad route')):
            for path in ('/api/load','/api/decisions','/api/decision-evidence?id=x',
                         '/data/memory/state.json','/lib/discovery_public.py','/.env',
                         '/api/discover?source=http://localhost:8888','/api/discover?source=instructor&url=https://evil.example',
                         '/api/discover?source=instructor&source=pydantic'):
                self.assertIn(dispatch(self.api,path)[0],(400,404))
            for method in ('POST','PUT','PATCH','DELETE'):
                self.assertEqual(dispatch(self.api,'/api/decision',method)[0],405)
            self.assertEqual(dispatch(self.api,'/api/demo',headers={'Sec-Fetch-Site':'cross-site'})[0],403)
        self.assertEqual(dispatch(self.api,'/api/index?route=demo')[0],200)
        self.assertEqual(dispatch(self.api,'/api/index?route=demo&route=discover')[0],404)
        with patch.object(self.api,'fetch_public',side_effect=self.fixture_fetch) as fetch:
            self.assertEqual(dispatch(self.api,'/api/index?route=discover&source=instructor')[0],200)
        self.assertEqual(fetch.call_count,1)

    def test_failed_or_unsupported_source_never_becomes_a_fake_candidate(self):
        for response in ({'raw':b'', 'error':'No source'},
                         {'raw':b'<title>Instructor</title><p>Generic news without a capability.</p>','error':None}):
            with patch.object(self.api,'fetch_public',return_value=response) as fetch:
                code,result,_=dispatch(self.api,'/api/discover?source=instructor')
            self.assertEqual(code,200);self.assertEqual(fetch.call_count,1)
            self.assertEqual(result['candidates'],[])

    def test_transport_has_strict_scope_caps_and_no_auth_proxy_redirect_or_retry(self):
        api=self.api
        class Response:
            status=200
            headers={'Content-Type':'text/html'}
            def __init__(self,raw):self.stream=io.BytesIO(raw)
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read1(self,n):return self.stream.read(n)
        opener=MagicMock();opener.open.return_value=Response(b'<title>Instructor</title>')
        with patch.object(api,'build_opener',return_value=opener) as build:
            self.assertIsNone(api.fetch_public(api.SOURCES[0]['url'])['error'])
        request=opener.open.call_args.args[0]
        self.assertIsNone(request.get_header('Authorization'))
        self.assertEqual(opener.open.call_args.kwargs['timeout'],3)
        self.assertEqual(build.call_args.args[0].proxies,{})
        self.assertIsNone(build.call_args.args[1].redirect_request(None,None,302,'',{},'https://evil.example'))
        self.assertEqual(opener.open.call_count,1)
        with patch.object(api,'build_opener',side_effect=AssertionError('Unapproved URL must not connect')):
            self.assertIsNotNone(api.fetch_public('https://evil.example/')['error'])
        opener.open.return_value=Response(b'x'*(api.MAX_BYTES+1))
        with patch.object(api,'build_opener',return_value=opener):
            self.assertIsNotNone(api.fetch_public(api.SOURCES[0]['url'])['error'])
        opener.open.side_effect=TimeoutError()
        with patch.object(api,'build_opener',return_value=opener):
            self.assertIsNotNone(api.fetch_public(api.SOURCES[0]['url'])['error'])

    def test_public_ui_works_offline_decisions_stay_local_and_checks_are_bounded(self):
        previews={}
        for source in self.api.SOURCES:
            item=repository_fixture(source['name'],PHRASES[source['id']])
            previews[source['id']]=self.api.search_public.discover(source['id'],searcher=lambda _,item=item:{'items':[item],'incomplete_results':False})
        for key in self.api.search_public.BUSINESS_NEEDS:
            item=business_repository_fixture(key)
            previews[key]=self.api.search_public.discover(key,searcher=lambda _,item=item:{'items':[item],'incomplete_results':False})
        # This test is allowed to execute Node only for the actual public UI.
        self.doCleanups()
        result=subprocess.run(['node',str(ROOT/'tests/public_demo_ui.cjs'),str(self.bundle)],
            input=json.dumps({'demo':self.api.demo_data(),'previews':previews}),text=True,capture_output=True,cwd=ROOT)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('PASS',result.stdout)

    def test_repository_discovery_finds_uncatalogued_tools_with_traceable_evidence(self):
        module=self.api.search_public
        item=repository_fixture('FixtureAgent','An LLM agent toolkit that extracts structured data from customer requests using explicit schemas.')
        response={'items':[item,item],'incomplete_results':False}
        with patch.object(module,'search',return_value=response) as search:
            code,result,_=dispatch(self.api,'/api/discover?need=instructor')
        self.assertEqual(code,200);self.assertEqual(search.call_count,1)
        self.assertEqual(len(result['candidates']),1)
        tool=result['candidates'][0]
        self.assertNotIn(tool['title'],[source['name'] for source in self.api.SOURCES])
        self.assertEqual(tool['description'],item['description'])
        self.assertEqual(tool['evidence_url'],item['url'])
        self.assertEqual(tool['url'],item['html_url'])
        self.assertTrue(tool['demo_source_id'].startswith('repo-'))
        self.assertIn('not independently checked',tool['limitations'][0])
        self.assertEqual(tool['label'],self.api.discovery.TOOL_LABEL)
        many=[repository_fixture('FixtureAgent'+str(index),item['description']) for index in range(8)]
        capped=module.discover('instructor',searcher=lambda _:{'items':many,'incomplete_results':False})
        self.assertEqual(len(capped['candidates']),3)
        # Repository identity is shared with Tavily and case-insensitive.
        lower=repository_fixture('fixtureagent',item['description'])
        deduped=module.discover('instructor',searcher=lambda _:{'items':[item,lower],'incomplete_results':False})
        self.assertEqual(len(deduped['candidates']),1)
        for path in ('/api/discover?need=evil','/api/discover?need=instructor&url=http://localhost',
                     '/api/discover?need=instructor&project=secret','/api/discover?need=instructor&need=pydantic'):
            with patch.object(module,'search',side_effect=AssertionError('Invalid route cannot search')):
                self.assertIn(dispatch(self.api,path)[0],(400,404))
        with patch.object(module,'search',return_value=response):
            self.assertEqual(dispatch(self.api,'/api/discover?route=discover&need=instructor')[0],200)

    def test_repository_evidence_rejects_mismatches_unsafe_missing_and_inactive_records(self):
        from datetime import datetime,timezone
        module=self.api.search_public;now=datetime(2026,10,27,tzinfo=timezone.utc)
        good=repository_fixture('FixtureAgent','An AI agent for extracting structured data and requirements from customer messages.')
        cases=[dict(good,**{key:value}) for key,value in [('private',True),('fork',True),('archived',True),('disabled',True),
            ('html_url','https://evil.example/tool'),('url','http://localhost:8888'),('created_at',None),
            ('pushed_at','2099-01-01T00:00:00Z'),('description','AI news today.'),
            ('description','An AI collection of structured data tools and tutorials for language models.'),
            ('description','A structured data tool that is not supported for AI agents and language models.')]]
        for item in cases:self.assertIsNone(module.candidate(item,'structured_extraction',now))
        self.assertIsNone(module.candidate(good,'extraction_evaluation',now))
        for payload in ({'items':[],'incomplete_results':False},{'items':[],'incomplete_results':True}):
            result=module.discover('instructor',searcher=lambda _:payload,now=now)
            self.assertEqual(result['candidates'],[])
        attempts=[]
        def unavailable(_):attempts.append(1);raise TimeoutError()
        result=module.discover('instructor',searcher=unavailable,now=now)
        self.assertEqual(attempts,[1]);self.assertEqual(result['candidates'],[])
        self.assertEqual(result['status'],'partial_failure')

    def test_repository_transport_is_fixed_free_bounded_and_does_not_read_credentials(self):
        module=self.api.search_public
        class Response:
            status=200;headers={'Content-Type':'application/json'}
            def __init__(self,raw):self.raw=io.BytesIO(raw)
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read1(self,n):return self.raw.read(n)
        opener=MagicMock();opener.open.return_value=Response(json.dumps({'items':[],'incomplete_results':False}).encode())
        with patch.object(module,'build_opener',return_value=opener) as build,patch.dict('os.environ',{'TAVILY_API_KEY':'SECRET_DO_NOT_USE','GITHUB_TOKEN':'SECRET_DO_NOT_USE'}):
            self.assertEqual(module.search('instructor')['items'],[])
        request=opener.open.call_args.args[0]
        self.assertTrue(request.full_url.startswith('https://api.github.com/search/repositories?'))
        self.assertNotIn('SECRET_DO_NOT_USE',repr(request.headers)+request.full_url)
        self.assertIsNone(request.get_header('Authorization'))
        self.assertEqual(opener.open.call_count,1);self.assertEqual(opener.open.call_args.kwargs['timeout'],3)
        self.assertEqual(build.call_args.args[0].proxies,{})
        self.assertIsNone(build.call_args.args[1].redirect_request(None,None,302,'',{},'https://evil.example'))
        with patch.object(module,'build_opener',side_effect=AssertionError('Unknown need must not connect')):
            with self.assertRaises(ValueError):module.search('raw visitor project')
        for raw in (b'x'*(module.MAX_BYTES+1),b'not json',b'{"items":[],"incomplete_results":"false"}'):
            opener.open.return_value=Response(raw)
            with patch.object(module,'build_opener',return_value=opener):
                with self.assertRaises(ValueError):module.search('instructor')

    def test_nontechnical_opportunities_require_product_access_and_business_evidence(self):
        from datetime import datetime,timezone
        module=self.api.search_public;now=datetime(2026,10,27,tzinfo=timezone.utc)
        for need in ('meal_planning','appointments','customer_support'):
            item=business_repository_fixture(need)
            tool=module.candidate(item,need,now)
            self.assertIsNotNone(tool)
            self.assertEqual(tool['product_url'],item['homepage'])
            self.assertEqual(tool['description'],item['description'])
            self.assertGreater(tool['usability_score'],0)
            self.assertIn('not independently checked',tool['limitations'][1])
            for update in ({'homepage':None},{'homepage':'http://localhost:8888'},
                           {'homepage':'https://docs.example.com/'},
                           {'homepage':'https://product.example/docs/'},
                           {'description':item['description']+' A Python SDK and library.'},
                           {'description':item['description'].replace('online','self-hosted').replace('no-code','self-hosted')}):
                self.assertIsNone(module.candidate(dict(item,**update),need,now),update)
        food=business_repository_fixture('meal_planning')
        self.assertIsNone(module.candidate(food,'appointments',now))
        hosted=business_repository_fixture('appointments')
        uncertain=dict(hosted,**{'name':'PossibleApp','full_name':'fixture-owner/PossibleApp','url':'https://api.github.com/repos/fixture-owner/PossibleApp','html_url':'https://github.com/fixture-owner/PossibleApp','description':hosted['description'].replace('online ','')})
        result=module.discover('appointments',searcher=lambda _:{'items':[uncertain,hosted],'incomplete_results':False},now=now)
        self.assertEqual(result['candidates'][0]['title'],hosted['name'])


if __name__=='__main__':unittest.main()
