"""Offline tool preview, real HTTP handler dispatch and real JS rendering; no network."""
from datetime import datetime, timedelta, timezone
import copy
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import update_discovery as d
import nextwise_app as app

NOW = datetime(2026, 10, 27, 12, tzinfo=timezone.utc)
FEEDS = d.tool_feeds()
RSS = (ROOT/'tests/fixtures/tool_announcements.rss').read_bytes()
ATOM = (ROOT/'tests/fixtures/tool_announcements.atom').read_bytes()


def fixture_fetch(url):
    if url == FEEDS[1]['url']: return {'raw':RSS, 'error':None}
    if url == FEEDS[2]['url']: return {'raw':ATOM, 'error':None}
    return {'raw':b'', 'error':'Synthetic HTTP 503'}


def dispatch(state, path, method='GET', cookie=True, origin=True):
    class Connection:
        def __init__(self): self.output = bytearray()
        def makefile(self, *args):
            headers = [f'{method} {path} HTTP/1.1', 'Host: 127.0.0.1:8765', 'Connection: close']
            if cookie: headers.append('Cookie: nextwise='+state.cookie)
            if origin: headers.append('Origin: http://127.0.0.1:8765')
            return io.BytesIO(('\r\n'.join(headers)+'\r\n\r\n').encode())
        def sendall(self, data): self.output.extend(data)
    connection = Connection()
    app.make_handler(state)(connection, ('127.0.0.1', 0), SimpleNamespace(server_port=8765))
    headers, body = bytes(connection.output).split(b'\r\n\r\n', 1)
    return int(headers.split()[1]), json.loads(body)


class ToolDiscoveryTests(unittest.TestCase):
    def setUp(self):
        # A default-network accident must fail, even when called through the API.
        self.network = patch('socket.socket', side_effect=AssertionError('External network forbidden'))
        self.network.start()
        self.addCleanup(self.network.stop)

    def preview(self, existing=(), **kwargs):
        return d.tool_preview(existing, fetcher=fixture_fetch, now=NOW, **kwargs)

    def test_rss_atom_dates_and_traceability(self):
        items = d.tool_feed_items(RSS, FEEDS[1], NOW)
        self.assertEqual(len(items), 4)
        self.assertEqual(items[0]['url'], 'https://openai.com/index/fixture-api')
        self.assertEqual(items[0]['publisher'], 'OpenAI')
        self.assertTrue(all(item['publication_date'].endswith('+00:00') for item in items))
        self.assertEqual(len(d.tool_feed_items(ATOM, FEEDS[2], NOW)), 2)
        self.assertEqual(d.tool_feed_items(RSS, FEEDS[1], NOW+timedelta(days=30)), [])
        invalid = RSS.replace(b'Mon, 26 Oct 2026 09:00:00 GMT', b'nonsense')
        self.assertEqual(len(d.tool_feed_items(invalid, FEEDS[1], NOW)), 1)
        naive = RSS.replace(b' 09:00:00 GMT', b' 09:00:00')
        self.assertEqual(d.tool_feed_items(naive, FEEDS[1], NOW), [])
        for raw in (b'<!DOCTYPE x><rss><channel/></rss>', b'<!ENTITY x "y"><rss/>', b'<html/>'):
            with self.assertRaises(ValueError): d.tool_feed_items(raw, FEEDS[1], NOW)
        malformed = RSS.replace(b'https://openai.com/index/fixture-api/?utm_source=fixture#top', b'https:///missing-host')
        self.assertEqual(len(d.tool_feed_items(malformed, FEEDS[1], NOW)), 3)

    def test_configuration_is_small_public_and_explicit(self):
        self.assertEqual(len(FEEDS), 3)
        self.assertIn(d.FEED, [f['url'] for f in FEEDS])
        for feeds in ([], FEEDS*2, [FEEDS[0],FEEDS[0]],
                      [{'publisher':'OpenAI','url':'http://openai.com/rss'}],
                      [{'publisher':'OpenAI','url':'https://127.0.0.1/rss'}],
                      [{'publisher':'OpenAI','url':'https://openai.com:8443/rss'}],
                      [{'publisher':'OpenAI','url':'https://user:secret@openai.com/rss'}],
                      [{'publisher':'Wrong publisher','url':FEEDS[0]['url']}],
                      [{'publisher':'OpenAI','url':'https:///missing-host'}]):
            with self.subTest(feeds=feeds), patch.object(Path,'read_text',return_value=json.dumps({'feeds':feeds})):
                with self.assertRaises(ValueError): d.tool_feeds()

    def test_dedup_existing_tracking_and_cross_feed_aliases(self):
        preview = self.preview()
        self.assertEqual(len(preview['candidates']), 3)
        self.assertEqual(sum('Fixture LLM API' in i['title'] for i in preview['candidates']), 1)
        existing = [{'url':'https://openai.com/index/fixture-api/?utm_source=old#fragment'},
                    {'url':'https://elsewhere.invalid/saved', 'title':'Introducing Fixture SDK'}]
        before = copy.deepcopy(existing)
        self.assertEqual([i['title'] for i in self.preview(existing)['candidates']], ['New Fixture recipe app'])
        self.assertEqual(existing, before)

    def test_relevance_source_grounding_and_labels(self):
        candidates = self.preview()['candidates']
        for item in candidates:
            self.assertEqual(item['label'], 'Discovery candidate — not yet validated')
            self.assertTrue(item['reasons'])
            self.assertTrue(all(phrase in item['title']+'. '+item['description'] for phrase in item['supporting_phrases']))
            self.assertNotIn('funding', item['title'])
            self.assertNotIn('image', item['title'])
            self.assertFalse({'recommended_choice','semantic_assessment','potential_value'} & item.keys())
        for description in ('A language model does not support structured outputs.',
                            'AI is transforming the world for every business.'):
            raw = RSS.replace(b'A language model supports structured outputs for extracting user requirements.', description.encode())
            result = d.tool_preview([], feeds=[FEEDS[1]], now=NOW, fetcher=lambda url:{'raw':raw,'error':None})
            self.assertEqual([i['title'] for i in result['candidates']], ['New Fixture recipe app'])

    def test_failures_zero_results_and_cap(self):
        result = self.preview()
        self.assertEqual(result['status'], 'partial_failure')
        self.assertIsNotNone(result['sources'][0]['error'])
        for response in ({'raw':b'', 'error':'503'}, {'raw':b'not xml', 'error':None}):
            calls=[]
            def fetch(url): calls.append(url); return response
            result = d.tool_preview([], fetcher=fetch, now=NOW)
            self.assertEqual(result['candidates'], [])
            self.assertEqual(calls, [feed['url'] for feed in FEEDS])
            self.assertEqual(result['status'], 'partial_failure')
        result = self.preview(feeds=[])
        self.assertEqual(result['candidates'], [])
        dated_empty = RSS.replace(b'2026', b'2020')
        result = d.tool_preview([], feeds=[FEEDS[1]], now=NOW, fetcher=lambda url:{'raw':dated_empty,'error':None})
        self.assertEqual(result['candidates'], [])
        self.assertEqual(result['status'], 'success')
        root = '<rss><channel>'+''.join(
            f'<item><title>Introducing Fixture {i} LLM API</title><link>https://openai.com/index/fixture-{i}</link><pubDate>Mon, 26 Oct 2026 09:00:00 GMT</pubDate><description>A language model supports structured outputs for user requirements.</description></item>'
            for i in range(20))+'</channel></rss>'
        result = d.tool_preview([], feeds=[FEEDS[1]], now=NOW, fetcher=lambda url:{'raw':root.encode(),'error':None})
        self.assertEqual(result['sources'][0]['eligible_items'], 10)
        self.assertEqual(len(result['candidates']), 3)

    def test_api_manual_authentication_readiness_overlap_and_no_memory_or_model(self):
        import semantic_discovery as semantic
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(d.memory, 'call_bridge', side_effect=AssertionError('Memory forbidden')), \
             patch.object(semantic.analyzer, 'request_claims', side_effect=AssertionError('Model forbidden')):
            state=app.State(tmp)
            route='/api/discovery/check?scope=tools'
            self.assertEqual(dispatch(state, route, 'POST', cookie=False)[0], 401)
            self.assertEqual(dispatch(state, route, 'POST', origin=False)[0], 403)
            self.assertEqual(dispatch(state, route, 'POST')[0], 409)
            state.tool_existing_items=[]
            original=d.tool_preview
            class ImmediateThread:
                def __init__(self, target, **kwargs): self.target=target
                def start(self): self.target()
            with patch.object(app.threading, 'Thread', ImmediateThread), \
                 patch.object(d, 'tool_preview', side_effect=lambda items, **kw:original(items, fetcher=fixture_fetch, now=NOW, **kw)):
                self.assertEqual(dispatch(state, route, 'POST')[0], 202)
                code,payload=dispatch(state, '/api/discovery?scope=tools')
                self.assertEqual(code, 200)
                self.assertEqual(len(payload['tool_preview']['candidates']), 3)
                self.assertFalse(payload['status']['running'])
                with state.discovery_lock:
                    self.assertEqual(dispatch(state, route, 'POST')[0], 409)
            self.assertEqual(list(Path(tmp).iterdir()), [])
            self.assertIsNone(app.State(tmp).tool_preview)

    def test_ui_rendering_and_manual_preview_routes(self):
        result=subprocess.run(['node',str(ROOT/'tests/tool_discovery_ui.cjs')], input=json.dumps(self.preview()),
                              text=True, capture_output=True, cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertIn('PASS', result.stdout)


if __name__ == '__main__': unittest.main()
