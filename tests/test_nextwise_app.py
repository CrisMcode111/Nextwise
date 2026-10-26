"""App checks: official persisted H-MEM retrieval, offline Zetaris fixtures and HTTP failures."""
import copy
import csv
import io
import json
from pathlib import Path
import sys
import threading
import unittest
import urllib.error
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
import nextwise_app as app


class FixtureClient:
    def __init__(self, mem):
        docs = {name: mem["artifacts"][kind] for name,kind in app.KINDS.items()}
        hashes = {app.exporter.INPUTS[name]:mem["artifact_hashes"][kind] for name,kind in app.KINDS.items()}
        self.tables = {name:list(csv.DictReader(io.StringIO(app.exporter.csv_bytes(rows).decode(),newline="")))
                       for name,rows in app.exporter.project(docs,hashes).items()}
        self.empty = False

    def sql(self, query):
        if query.startswith("SELECT *"):
            name=query.rsplit(".",1)[-1]
            rows=self.tables[name]; columns=list(rows[0])
            return columns, [] if self.empty else [[r[c] for c in columns] for r in rows]
        if query.startswith("SELECT "):
            name=query.rsplit(".",1)[-1]
            spec=json.loads((app.integration.SNAPSHOT/"manifest.json").read_text())["tables"][name]
            columns=spec["primary_key"]+[k for k,v in spec["columns"].items() if v in ("BIGINT","DOUBLE")]
            return columns,[[r[c] for c in columns] for r in self.tables[name]]
        rows=app.integration.expected_join(self.tables)
        return list(rows[0]), [[str(v) if isinstance(v,app.integration.Decimal) else v for v in row.values()] for row in rows]


class DataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mem=app.retrieve_memory()  # Actual official bridge; no models/import/replacement store.

    def test_memory_and_exact_data_combine(self):
        result=app.load_investigation(FixtureClient(self.mem),lambda:self.mem)
        self.assertEqual(result["diagnostics"]["memory_ids"]["evaluation_results"],self.mem["artifact_ids"]["evaluation_results"])
        self.assertEqual(result["aggregate"]["attempted_cases"],str(len(result["cases"])))
        self.assertTrue(all(c["input"] and c["output"] and c["finding"] for c in result["cases"]))
        self.assertIsNone(result["investigation"]["decision"])

    def test_no_combining_different_run_or_hash(self):
        for change in (lambda m:m["artifacts"]["evaluation_results"].update(run_id="other"),
                       lambda m:m["artifact_hashes"].update(evidence_draft="0"*64),
                       lambda m:m.update(investigation_id="other")):
            mem=copy.deepcopy(self.mem);change(mem)
            with self.assertRaises(app.AppError) as error:
                app.load_investigation(FixtureClient(self.mem),lambda:mem)
            self.assertEqual(error.exception.code,"integrity")

    def test_empty_and_malformed_live_data_fail_closed(self):
        client=FixtureClient(self.mem);client.empty=True
        with self.assertRaises(app.AppError) as error: app.load_investigation(client,lambda:self.mem)
        self.assertEqual(error.exception.code,"empty")
        client=FixtureClient(self.mem);client.tables["evidence_claims"][0]["exact_supporting_quote"]="tampered"
        with self.assertRaises(app.AppError) as error: app.load_investigation(client,lambda:self.mem)
        self.assertEqual(error.exception.code,"integrity")

    def test_comparisons_preserve_saved_results_and_explicit_qualifications(self):
        result=app.load_investigation(FixtureClient(self.mem),lambda:self.mem)
        originals=self.mem['artifacts']['evaluation_results']
        for case in result['cases']:
            original=next(c for c in originals['cases'] if c['fixture_id']==case['fixture_id'])
            self.assertEqual(case['output'],original['output'])
            self.assertEqual(case['validation'],original['validation'])
        case=next(c for c in result['cases'] if c['fixture_id']=='synthetic-explicit')
        rows={r['field']:r for r in case['comparison']['rows']}
        self.assertEqual(rows['meal']['expected'],'dinner')
        self.assertEqual(rows['meal']['recorded'],[])
        self.assertEqual(rows['people_count']['expected'],2)
        self.assertEqual(rows['people_count']['recorded'][0]['value'],'two')
        self.assertTrue(any('preserves the stated quantity semantically' in q for q in rows['people_count']['qualifications']))
        self.assertEqual(rows['excluded_food_category_as_stated']['recorded'][0]['value'],'no nuts')
        self.assertEqual(rows['ready_within_minutes']['recorded'][0]['value'],20)
        self.assertTrue(any('Also listed as unknown: time_limit' in f for f in rows['ready_within_minutes']['findings']))
        self.assertIn('meaning_of_light',case['comparison']['additional_unknowns'])
        self.assertEqual(sum(c['validation']['quality_pass'] for c in result['cases']),1)

    def test_comparison_is_data_driven_and_uses_only_saved_alias(self):
        result=self.mem['artifacts']['evaluation_results'];rec=self.mem['artifacts']['evaluation_recommendation']
        case=copy.deepcopy(result['cases'][0]);fixture=copy.deepcopy(result['fixtures'][0]['snapshot'])
        fixture['id']='different-id';fixture['expected_explicit_facts']['people_count']=7
        p=app.present_case(case,fixture,result['local_rubric']['synthetic-explicit'],rec,result['scoring_protocol'])
        self.assertEqual(next(r for r in p['rows'] if r['field']=='people_count')['expected'],7)
        # Presentation does not alter saved flags or calculate a new pass/fail result.
        self.assertEqual(case,result['cases'][0]);self.assertNotIn('quality_pass',p)
        c=result['cases'][2];f=result['fixtures'][2]['snapshot'];rubric=result['local_rubric'][c['fixture_id']]
        row=app.present_case(c,f,rubric,rec,result['scoring_protocol'])['rows'][0]
        self.assertEqual(row['field'],'exclusion_as_stated');self.assertEqual(row['recorded'][0]['field'],'excluded_food_category_as_stated')


class HttpTests(unittest.TestCase):
    def test_production_listener_refuses_duplicate_binding(self):
        server=app.LocalHTTPServer(('127.0.0.1',0),app.make_handler(app.State()))
        try:
            with self.assertRaises(OSError):
                app.LocalHTTPServer(server.server_address,app.make_handler(app.State()))
            with self.assertRaises(OSError):
                app.ThreadingHTTPServer(server.server_address,app.make_handler(app.State()))
        finally:server.server_close()

    def setUp(self):
        self.state=app.State()
        self.error=None
        def loader(client):
            if self.error: raise self.error
            return {"ok":True}
        self.server=app.ThreadingHTTPServer(("127.0.0.1",0),app.make_handler(self.state,loader))
        self.server.daemon_threads=True
        threading.Thread(target=self.server.serve_forever,daemon=True).start()
        self.base=f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown();self.server.server_close()

    def request(self,path="/api/load",origin=True,cookie=True,method="POST"):
        headers={}
        if origin:headers["Origin"]=self.base
        if cookie:headers["Cookie"]=f"nextwise={self.state.cookie}"
        req=urllib.request.Request(self.base+path,headers=headers,method=method)
        try:r=urllib.request.urlopen(req)
        except urllib.error.HTTPError as e:r=e
        with r:return r.status,r.headers,r.read()

    def test_auth_masking_origin_and_security_headers(self):
        status,headers,body=self.request()
        self.assertEqual(status,401)
        self.assertEqual(json.loads(body)["code"],"authentication")
        self.state.key="SECRET_TEST_SENTINEL"
        self.assertEqual(self.request(origin=False)[0],403)
        self.assertEqual(self.request(cookie=False)[0],401)
        status,headers,body=self.request()
        self.assertEqual(status,200);self.assertNotIn(b"SECRET_TEST_SENTINEL",body)
        self.assertEqual(headers["Cache-Control"],"no-store")
        self.assertIn("script-src 'self'",headers["Content-Security-Policy"])

    def test_service_memory_integrity_empty_and_auth_errors(self):
        self.state.key="SECRET_TEST_SENTINEL"
        for code in ("memory","integrity","empty"):
            self.error=app.AppError(code,"Safe failure",409)
            status,headers,body=self.request();self.assertEqual(json.loads(body)["code"],code)
        self.error=RuntimeError("SECRET_TEST_SENTINEL")
        status,headers,body=self.request();self.assertEqual(status,503);self.assertNotIn(b"SECRET_TEST_SENTINEL",body)
        self.error=ValueError("HTTP 401; response body suppressed")
        self.assertEqual(self.request()[0],401);self.assertIsNone(self.state.key)

    def test_disconnect_and_path_allowlist(self):
        self.state.key="SECRET_TEST_SENTINEL"
        self.assertEqual(self.request('/api/disconnect')[0],200);self.assertIsNone(self.state.key)
        self.assertEqual(self.request('/../data/evidence_draft.json',method='GET')[0],404)
        status,headers,body=self.request('/',method='GET')
        self.assertEqual(status,200);self.assertIn('HttpOnly',headers['Set-Cookie'])


if __name__=="__main__":unittest.main()
