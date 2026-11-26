"""Offline tests for the not-yet-wired public URL ingestion primitive."""
import importlib.util
from pathlib import Path
import socket
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import collect_sources

with patch.dict(sys.modules, {'collector_public':collect_sources}):
    spec = importlib.util.spec_from_file_location('public_ingestion', ROOT/'deploy/vercel_demo/public_ingestion.py')
    ingest = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ingest)


def addresses(*values):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (v,443)) for v in values]


class Response:
    status = 200
    def __init__(self, body=b'<main>Public project</main>', headers=None):
        self.body = body
        self.headers = headers or {'Content-Type':'text/html'}
    def getheader(self, name, default=None): return self.headers.get(name, default)
    def read(self, length):
        data, self.body = self.body[:length], self.body[length:]
        return data


class IngestionTests(unittest.TestCase):
    def test_rejects_unsafe_urls_and_dns(self):
        for url in ('http://example.com/', 'https://user@example.com/', 'https://example.com:444/',
                    'https://localhost/', 'https://foo.local/', 'https://example.com/#fragment'):
            with self.subTest(url=url), self.assertRaises(ValueError): ingest.validate_url(url)
        for ips in (('127.0.0.1',), ('169.254.169.254',), ('8.8.8.8','10.0.0.1')):
            with self.subTest(ips=ips), self.assertRaises(ValueError):
                ingest.public_addresses('example.com', lambda *a,**k:addresses(*ips))

    def test_pins_public_address_and_extracts_inert_text(self):
        observed = []
        class Connection:
            def __init__(self, host, ip): observed.append((host,ip))
            def request(self, *args, **kwargs): observed.append(args)
            def getresponse(self): return Response()
            def close(self): pass
        result=ingest.extract_public_url('https://example.com/project',
            resolver=lambda *a,**k:addresses('8.8.8.8'), connection=Connection)
        self.assertEqual(observed[0],('example.com','8.8.8.8'))
        self.assertIn('Public project',result['text'])
        self.assertEqual(result['provenance'],'untrusted_public_page')

    def test_redirects_and_oversized_content_are_rejected(self):
        class Connection:
            response = None
            def __init__(self, *args): pass
            def request(self, *args, **kwargs): pass
            def getresponse(self): return self.response
            def close(self): pass
        redirect=Response(); redirect.status=302
        for response in (redirect, Response(headers={'Content-Type':'text/plain','Content-Length':'1000001'}),
                         Response(headers={'Content-Type':'text/html','Content-Encoding':'gzip'})):
            Connection.response=response
            with self.assertRaises(ValueError):
                ingest.extract_public_url('https://example.com', resolver=lambda *a,**k:addresses('8.8.8.8'), connection=Connection)
