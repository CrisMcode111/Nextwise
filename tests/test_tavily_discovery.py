"""Mocked Tavily and source responses only; external sockets/models/memory forbidden."""
import copy
import io
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError
from test_tool_discovery import d, app, dispatch, ROOT, NOW
from test_project_tool_discovery import source_fetch
import tavily_discovery as t

FIXTURE=json.loads((ROOT/'tests/fixtures/tavily_tools.json').read_text(encoding='utf-8'))
KEY='OFFLINE_TEST_SECRET_NOT_A_REAL_KEY'


class Response:
    def __init__(self, raw, status=200, headers=None):
        self.stream=io.BytesIO(raw);self.status=status
        self.headers=headers or {'Content-Type':'text/html'}
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def read1(self,n):return self.stream.read(n)
    def getheader(self,name,default=None):return self.headers.get(name,default)


class TavilyTests(unittest.TestCase):
    def setUp(self):
        for guard in (patch('socket.socket',side_effect=AssertionError('External network forbidden')),
                      patch.object(d.memory,'call_bridge',side_effect=AssertionError('Memory forbidden')),
                      patch.dict('os.environ',{'TAVILY_API_KEY':KEY})):
            guard.start();self.addCleanup(guard.stop)
        import semantic_discovery as semantic
        guard=patch.object(semantic.analyzer,'request_claims',side_effect=AssertionError('Models forbidden'))
        guard.start();self.addCleanup(guard.stop)

    def discover(self, existing=(), **kwargs):
        responses=iter(copy.deepcopy(FIXTURE['searches']))
        def search(query,key):return next(responses)['results']
        def page(url):return {'raw':FIXTURE['pages'][url].encode(),'error':None}
        return t.discover(existing,now=NOW,searcher=search,page_fetcher=page,fetcher=source_fetch,**kwargs)

    def test_finds_unknown_products_evidence_and_exact_success_budget(self):
        result=self.discover()
        self.assertEqual({c['title'].casefold() for c in result['candidates']},{'forge','evalbench','planleaf'})
        self.assertEqual(result['search']['requests_attempted'],2)
        self.assertEqual(result['search']['maximum_credits'],2)
        self.assertEqual(result['search']['credits_if_attempts_billed'],2)
        self.assertEqual(result['search']['source_pages_attempted'],3)
        for candidate in result['candidates']:
            self.assertEqual(candidate['kind'],'discovered_product')
            self.assertEqual(candidate['label'],d.TOOL_LABEL)
            self.assertIn(candidate['description'],FIXTURE['pages'][candidate['url']])
            self.assertNotIn('Unverified snippet',candidate['description'])
            self.assertTrue(candidate['limitations'])
        self.assertNotIn(KEY,json.dumps(result))

    def test_queries_use_actual_needs_without_project_secrets(self):
        project=d.context();project['task']+=' PRIVATE_DO_NOT_SEND';project['constraints'].append('PRIVATE_BUDGET')
        plans=t.plans(project)
        self.assertEqual(len(plans),2)
        self.assertNotIn('PRIVATE',json.dumps(plans))
        self.assertIn('dietary',plans[1]['query'])
        self.assertEqual(t.plans({'task':'Send invoices','objective':'Manage invoices','constraints':[]}),[])

    def test_transport_basic_parameters_no_redirects_no_proxies_no_secret_return(self):
        seen=[]
        def opened(request,timeout):
            seen.append((request.full_url,json.loads(request.data),request.get_header('Authorization'),timeout,request))
            return Response(json.dumps(FIXTURE['searches'][0]).encode())
        opener=MagicMock();opener.open.side_effect=opened
        with patch.object(t,'build_opener',return_value=opener) as build:
            self.assertEqual(len(t.search('safe project need',KEY)),3)
        endpoint,payload,auth,timeout,request=seen[0]
        self.assertEqual(endpoint,'https://api.tavily.com/search')
        self.assertEqual(auth,'Bearer '+KEY)
        self.assertIsNone(request.get_header('Authorization'))
        self.assertNotIn(KEY,json.dumps(payload))
        self.assertEqual(payload['search_depth'],'basic')
        self.assertEqual(payload['max_results'],5)
        self.assertFalse(payload['auto_parameters'])
        self.assertFalse(payload['include_answer'])
        self.assertFalse(payload['include_raw_content'])
        self.assertTrue(payload['include_usage'])
        self.assertNotIn('time_range',payload)
        self.assertEqual(build.call_args.args[0].proxies,{})
        self.assertIsNone(build.call_args.args[1].redirect_request(None,None,302,'',{},'https://evil.example'))
        self.assertEqual(timeout,8)

    def test_transport_rejects_bad_oversized_echoed_and_unexpected_credit_responses(self):
        for raw in (b'not-json', b'x'*(t.MAX_SEARCH_BYTES+1), json.dumps({'results':[],'leak':KEY}).encode(),
                    b'{"results":[],"usage":{"credits":2}}',b'{"results":"bad"}'):
            opener=MagicMock();opener.open.return_value=Response(raw)
            with self.subTest(size=len(raw)),patch.object(t,'build_opener',return_value=opener):
                with self.assertRaises(t.SearchUnavailable) as error:t.search('query',KEY)
                self.assertNotIn(KEY,str(error.exception))
                self.assertEqual(opener.open.call_count,1)
        for code in (401,429,432,500,302):
            opener=MagicMock();opener.open.side_effect=HTTPError(t.ENDPOINT,code,KEY,{},io.BytesIO(KEY.encode()))
            with patch.object(t,'build_opener',return_value=opener):
                with self.assertRaises(t.SearchUnavailable):t.search('query',KEY)
                self.assertEqual(opener.open.call_count,1)
        opener=MagicMock();opener.open.side_effect=TimeoutError(KEY)
        with patch.object(t,'build_opener',return_value=opener):
            with self.assertRaises(t.SearchUnavailable):t.search('query',KEY)
        opener.open.return_value=Response(b'{}');opener.open.side_effect=None
        with patch.object(t,'build_opener',return_value=opener),patch.object(t.time,'monotonic',side_effect=[0,20]):
            with self.assertRaises(t.SearchUnavailable):t.search('query',KEY)

    def test_missing_key_failure_empty_results_catalog_fallback_and_no_retries(self):
        search=MagicMock(side_effect=t.SearchUnavailable())
        result=t.discover([],searcher=search,fetcher=source_fetch,now=NOW)
        self.assertEqual(search.call_count,1)
        self.assertEqual(result['search']['requests_attempted'],1)
        self.assertEqual(len(result['candidates']),3)
        self.assertEqual(result['search']['status'],'failed_or_unconfirmed')
        with patch.dict('os.environ',{'TAVILY_API_KEY':''}):
            result=t.discover([],searcher=search,fetcher=source_fetch,now=NOW)
            self.assertEqual(result['search']['requests_attempted'],0)
            self.assertEqual(result['search']['maximum_credits'],0)
        search=MagicMock(return_value=[])
        result=t.discover([],searcher=search,fetcher=source_fetch,now=NOW)
        self.assertEqual(search.call_count,2)
        self.assertTrue(all(c['kind']=='product_documentation' for c in result['candidates']))

    def test_hard_result_page_limits_and_unsupported_sources(self):
        search=MagicMock(return_value=[{'url':f'https://product{i}.example/'} for i in range(100)])
        page=MagicMock(return_value={'raw':b'<title>Best AI tools</title><p>Generic AI news only.</p>','error':None})
        result=t.discover([],searcher=search,page_fetcher=page,fetcher=source_fetch,now=NOW)
        self.assertEqual(search.call_count,2)
        self.assertEqual(page.call_count,4)
        self.assertEqual(len(result['candidates']),3)
        self.assertTrue(all(c['kind']=='product_documentation' for c in result['candidates']))

    def test_dedup_decisions_aliases_and_shared_host_product_identity(self):
        history=[{'candidate_id':'prior','choice':'Defer','version':1,'title':'Forge'},
                 {'candidate_id':'meal','choice':'Reject','version':1,'evidence_references':{'url':'https://planleaf.example/prior'}}]
        result=self.discover(decision_history=history)
        self.assertFalse({'Forge','PlanLeaf'} & {c['title'] for c in result['candidates']})
        self.assertNotEqual(t.product_key('https://github.com/acme/one'),t.product_key('https://github.com/acme/two'))
        self.assertEqual(t.product_key('https://github.com/acme/one/docs'),t.product_key('https://github.com/acme/one'))
        self.assertFalse(t.excluded('Different','https://github.com/acme/two',[{'url':'https://github.com/acme/one'}]))

    def test_unsafe_urls_dns_rebinding_redirects_and_no_source_auth(self):
        for url in ('http://example.com','https://127.0.0.1/','https://[::1]/','https://localhost/',
                    'https://a.local/','https://user:pass@example.com/','https://example.com:8443/',
                    'https://example.com/?api_key=secret','https:///broken'):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):t.source_url(url)
        self.assertEqual(t.source_url('https://example.com/path?utm_source=x#fragment'),'https://example.com/path')
        for address in ('127.0.0.1','169.254.169.254','10.0.0.1','::1'):
            with patch.object(t.socket,'getaddrinfo',return_value=[(None,None,None,None,(address,443))]),patch.object(t.socket,'create_connection') as connection:
                self.assertIsNotNone(t.public_page('https://example.com')['error'])
                connection.assert_not_called()
        connection=MagicMock();connection.getresponse.return_value=Response(b'',status=302)
        with patch.object(t.socket,'getaddrinfo',return_value=[(None,None,None,None,('8.8.8.8',443))]),patch.object(t.http.client.HTTPSConnection,'request'),patch.object(t.http.client.HTTPSConnection,'getresponse',return_value=Response(b'',status=302)):
            self.assertIsNotNone(t.public_page('https://example.com')['error'])

    def test_public_page_pins_ip_preserves_tls_hostname_and_caps_response(self):
        fake_socket=MagicMock();tls=MagicMock();tls.wrap_socket.return_value=fake_socket
        response=Response(b'<title>Public product</title>')
        with patch.object(t.socket,'getaddrinfo',return_value=[(None,None,None,None,('8.8.8.8',443))]) as dns, \
             patch.object(t.socket,'create_connection',return_value=fake_socket) as connect, \
             patch.object(t.ssl,'create_default_context',return_value=tls), \
             patch.object(t.http.client.HTTPSConnection,'getresponse',return_value=response):
            result=t.public_page('https://example.com/docs')
        self.assertIsNone(result['error'])
        self.assertEqual(dns.call_count,1)
        connect.assert_called_once_with(('8.8.8.8',443),timeout=d.TIMEOUT)
        tls.wrap_socket.assert_called_once_with(fake_socket,server_hostname='example.com')
        sent=b''.join(call.args[0] for call in fake_socket.sendall.call_args_list)
        self.assertNotIn(KEY.encode(),sent)
        self.assertNotIn(b'Authorization',sent)
        self.assertIn(b'Host: example.com',sent)
        for response in (Response(b'x'*(d.MAX_BYTES+1)),
                         Response(b'',headers={'Content-Type':'text/html','Content-Length':str(d.MAX_BYTES+1)}),
                         Response(b'{}',headers={'Content-Type':'application/json'})):
            with patch.object(t.socket,'getaddrinfo',return_value=[(None,None,None,None,('8.8.8.8',443))]), \
                 patch.object(t.http.client.HTTPSConnection,'request'), \
                 patch.object(t.http.client.HTTPSConnection,'getresponse',return_value=response):
                self.assertIsNotNone(t.public_page('https://example.com/docs')['error'])

    def test_actual_ui_and_api_use_tavily_strategy_without_real_requests(self):
        result=self.discover()
        rendered=subprocess.run(['node',str(ROOT/'tests/tool_discovery_ui.cjs')],input=json.dumps(result),text=True,capture_output=True,cwd=ROOT)
        self.assertEqual(rendered.returncode,0,rendered.stdout+rendered.stderr)
        state=app.State();state.tool_existing_items=[];state.tool_human_history=[];state.tool_opportunity_history=[]
        class Thread:
            def __init__(self,target,**kwargs):self.target=target
            def start(self):self.target()
        with patch.object(app.threading,'Thread',Thread),patch.object(t,'discover',return_value=result) as discover:
            self.assertEqual(dispatch(state,'/api/discovery/check?scope=tools','POST')[0],202)
            code,payload=dispatch(state,'/api/discovery?scope=tools')
            self.assertEqual(code,200)
            self.assertEqual(payload['tool_preview']['search']['requests_attempted'],2)
            self.assertEqual(discover.call_count,1)
            self.assertNotIn(KEY,json.dumps(payload))


if __name__=='__main__':unittest.main()
