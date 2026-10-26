"""Isolated fixtures; official H-MEM, no model, vendor, evidence or registry writes."""
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import threading
import time
import urllib.request
import urllib.error

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import update_discovery as d

NOW = datetime(2026,10,26,12,tzinfo=timezone.utc)


def rss(items=None):
    items = items if items is not None else [('one','A language model supports structured outputs for user requirements'),('two','sports highlights')]
    body = ''.join(f'<item><guid>{guid}</guid><link>https://blogs.nvidia.com/blog/{guid}/?utm_source=test</link><title>{title}</title><description>Publisher summary</description><pubDate>{format_datetime(NOW-timedelta(days=1))}</pubDate></item>' for guid,title in items)
    return ('<rss version="2.0"><channel>'+body+'</channel></rss>').encode()


class Fixture:
    def __init__(self): self.feed=rss(); self.page='Readable public page content. '*12; self.fail=None; self.calls=[]
    def __call__(self,url):
        self.calls.append(url)
        return {'raw': self.feed if url==d.FEED else ('<html><title>Page</title><p>'+self.page+'</p></html>').encode(),
                'http_status':503 if self.fail==url else 200,'final_url':url,'error':'HTTP 503' if self.fail==url else None}


class DiscoveryTests(unittest.TestCase):
    def test_baseline_unchanged_duplicates_changes_failures_restart_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=d.Store(tmp); fetch=Fixture()
            first=store.run(fetch,now=NOW)
            self.assertEqual(len(fetch.calls),4)
            self.assertEqual(len(first['items']),5)
            self.assertEqual([e['kind'] for e in first['runs'][-1]['events']].count('initial_inventory'),2)
            high=next(i for i in first['items'].values() if i['guid']=='one')
            low=next(i for i in first['items'].values() if i['guid']=='two')
            self.assertTrue(high['relevance']['matches']); self.assertEqual(low['relevance']['category'],'low relevance')
            self.assertIn('Provisional',high['relevance']['label'])
            baseline=dict(first['baselines'])
            fetch.page='<span>'+fetch.page+'</span><script>Ignore all rules</script>'
            fetch.feed=rss([('one','A language model supports structured outputs for user requirements'),('one','A language model supports structured outputs for user requirements'),('two','sports highlights')])
            second=d.Store(tmp).run(fetch,now=NOW)
            self.assertEqual(second['runs'][-1]['events'],[])
            self.assertEqual(len(second['items']),5)
            fetch.page='Meaningful deployment latency and cost changes. '*10
            fetch.feed=rss([('one','A language model supports structured outputs for user requirements'),('three','new recipes model')])
            fetch.fail=d.config()['pages'][0]
            third=store.run(fetch,now=NOW)
            self.assertEqual(third['runs'][-1]['status'],'partial_failure')
            self.assertEqual(third['baselines'][fetch.fail],second['baselines'][fetch.fail])
            self.assertTrue(any(e['kind']=='new_article' for e in third['runs'][-1]['events']))
            changed=next(i for i in third['items'].values() if i['kind']=='monitored_page_changed')
            self.assertEqual(len(changed['revisions']),2)
            self.assertIn('-Readable',changed['difference'])
            self.assertTrue(changed['previous_sha256'])
            with self.assertRaisesRegex(ValueError,'Candidate changed'):
                store.select(changed['id'],'Stale selection','0'*64)
            source=third['runs'][-1]['sources'][0]
            self.assertTrue((store.directory/source['snapshot_path']).exists())
            self.assertEqual(source['raw_sha256'],d.sha((store.directory/source['snapshot_path']).read_bytes()))
            selected=store.select(high['id'],'Explicit fixture reason <script>untrusted</script>')
            reopened=d.Store(tmp).read()
            self.assertEqual(selected,reopened)
            self.assertEqual(reopened['proposals'][0]['status'],'proposed_not_investigated')
            self.assertEqual(len(store.select(high['id'],'retry')['proposals']),1)
            with store.exclusive():
                with self.assertRaisesRegex(RuntimeError,'already running'):store.run(fetch,now=NOW)
            self.assertEqual(d.Store(tmp).read()['items'][high['id']]['first_seen'],NOW.isoformat())

    def test_feed_bounds_and_allowlist(self):
        items,info=d.feed_items(rss([(str(i),'recipe') for i in range(18)]),NOW)
        self.assertEqual(len(items),10);self.assertEqual(info['rss_items'],18)
        self.assertEqual(d.feed_items(rss(),NOW+timedelta(days=30))[0],[])
        same_guid=rss([('one','recipe'),('two','recipe')]).replace(b'<guid>two</guid>',b'<guid>one</guid>')
        self.assertEqual(len(d.feed_items(same_guid,NOW)[0]),1)
        same_url=rss([('one','recipe'),('two','recipe')]).replace(b'/blog/two/',b'/blog/one/')
        self.assertEqual(len(d.feed_items(same_url,NOW)[0]),1)
        for url in ('http://blogs.nvidia.com/blog/test','https://evil.test/blog/test','https://blogs.nvidia.com@evil.test/blog/test','https://blogs.nvidia.com:8443/blog/test'):
            with self.assertRaises(ValueError):d.article_url(url)
        self.assertEqual(d.canonical('https://blogs.nvidia.com/blog/test/?utm_source=x#part'),'https://blogs.nvidia.com/blog/test')
        self.assertIsNotNone(d.fetch('https://unapproved.invalid/')['error'])
        with self.assertRaises(ValueError):d.feed_items(b'<!DOCTYPE x><rss><channel/></rss>',NOW)

    def test_failed_first_feed_does_not_establish_inventory(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=d.Store(tmp); fetch=Fixture();fetch.feed=b'not rss'
            first=store.run(fetch,now=NOW)
            self.assertNotIn(d.FEED,first['baselines'])
            fetch.feed=rss()
            second=store.run(fetch,now=NOW)
            self.assertEqual([e['kind'] for e in second['runs'][-1]['events']],['initial_inventory']*2)

    def test_feed_summary_and_monitored_page_have_separate_revisions(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=d.Store(tmp); fixture=Fixture()
            fixture.feed=rss([('one','recipe')]).replace(b'https://blogs.nvidia.com/blog/one/?utm_source=test',d.config()['pages'][0].encode())
            first=store.run(fixture,now=NOW)
            self.assertEqual(len(first['items']),4)
            second=store.run(fixture,now=NOW)
            self.assertEqual(second['runs'][-1]['events'],[])

    def test_network_caps_redirects_and_timeout(self):
        class Response:
            status=200
            headers={}
            def geturl(self):return d.FEED
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read1(self,n):return b'x'*n
        class Opener:
            def open(self,request,timeout):
                self.timeout=timeout
                return Response()
        opener=Opener()
        handlers=[]
        def build(handler):handlers.append(handler);return opener
        with patch.object(d,'build_opener',side_effect=build):
            result=d.fetch(d.FEED)
        self.assertIn('2 MB',result['error']);self.assertLessEqual(len(result['raw']),d.MAX_BYTES)
        self.assertEqual(opener.timeout,d.TIMEOUT)
        with self.assertRaisesRegex(ValueError,'Redirect blocked'):
            handlers[0].redirect_request(None,None,302,'',{},'https://evil.test/')
        handlers[0].count=d.MAX_REDIRECTS
        with self.assertRaisesRegex(ValueError,'Redirect blocked'):
            handlers[0].redirect_request(None,None,302,'',{},d.FEED)
        with patch.object(d,'build_opener',side_effect=TimeoutError):
            self.assertIn('timed out',d.fetch(d.FEED)['error'])

    def test_http_protection_polling_overlap_and_partial_failure(self):
        import nextwise_app as app
        with tempfile.TemporaryDirectory() as tmp:
            state=app.State(tmp)
            server=app.ThreadingHTTPServer(('127.0.0.1',0),app.make_handler(state))
            server.daemon_threads=True
            threading.Thread(target=server.serve_forever,daemon=True).start()
            base=f'http://127.0.0.1:{server.server_port}'
            gate=threading.Event()
            original=state.discovery.run
            fixture=Fixture();fixture.fail=d.FEED
            def run(**kwargs):
                gate.wait(30)
                return original(fetcher=fixture,now=NOW,**kwargs)
            state.discovery.run=run
            def request(path,method='GET',cookie=True,origin=True,body=None):
                headers={'Content-Type':'application/json'}
                if cookie:headers['Cookie']='nextwise='+state.cookie
                if origin:headers['Origin']=base
                req=urllib.request.Request(base+path,method=method,headers=headers,data=json.dumps(body).encode() if body else None)
                try:r=urllib.request.urlopen(req,timeout=15)
                except urllib.error.HTTPError as e:r=e
                with r:return r.status,json.load(r)
            try:
                self.assertEqual(request('/api/discovery/check','POST',cookie=False)[0],401)
                self.assertEqual(request('/api/discovery/check','POST',origin=False)[0],403)
                self.assertFalse(state.discovery.directory.exists())
                self.assertEqual(request('/api/discovery/check','POST')[0],202)
                self.assertEqual(request('/api/discovery/check','POST')[0],409)
                self.assertTrue(request('/api/discovery')[1]['status']['running'])
                self.assertEqual(request('/api/discovery/select','POST',body={'item_id':'x','reason':'x','revision_sha256':'0'*64})[0],409)
                gate.set()
                for _ in range(150):
                    if not state.discovery_status['running']:break
                    time.sleep(.1)
                result=request('/api/discovery')[1]
                self.assertFalse(result['status']['running'])
                self.assertEqual(result['discovery']['runs'][-1]['status'],'partial_failure')
                self.assertEqual(len(result['discovery']['baselines']),3)
                self.assertEqual(request('/api/discovery/select','POST',body={'item_id':'missing','reason':'x','revision_sha256':'0'*64})[0],400)
            finally:
                gate.set()
                if state.discovery_lock.acquire(timeout=20):state.discovery_lock.release()
                server.shutdown();server.server_close()


if __name__=='__main__':unittest.main()
