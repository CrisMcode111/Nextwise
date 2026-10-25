"""Human decisions: isolated official H-MEM, no real decisions or remote requests."""
import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import uuid

from decision_fixture import app, call, initialize


class DecisionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='nextwise-decision-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.mem = initialize(self.root)
        self.context = dict(manifest_id=self.mem['manifest_id'], artifact_hashes=self.mem['artifact_hashes'],
                            run_id=self.mem['evaluation_results']['run_id'])
        self.body = dict(explicit_action='record_human_decision', choice='Defer',
                         rationale='ISOLATED TEST FIXTURE only. Quotes "two", Unicode café.\nSecond line <script>plain text</script>',
                         next_action=None, request_id=str(uuid.uuid4()), expected_head=None, context=self.context)
        self.statefile = self.root / app.INVESTIGATION / 'state.json'

    def save(self, body=None):
        return call(self.root, 'decision_save', decision=body or self.body)

    def test_save_retry_restart_amend_history_and_immutable_artifacts(self):
        original = json.loads(self.statefile.read_text(encoding='utf-8'))
        saved = self.save(); self.assertTrue(saved['ok'], saved)
        first = saved['history'][0]
        self.assertEqual(first['rationale'], self.body['rationale'])
        self.assertFalse(first['needs_review']); self.assertEqual(len(first['evidence_references']), 8)
        self.assertEqual(first['project_id'], 'ai-raw-gourmet')
        self.assertTrue(first['created_at_utc'].endswith('Z'))
        self.assertTrue(self.save()['reused'])  # Fresh Node process, same retry ID.
        changed_retry = dict(self.body, rationale='different text')
        self.assertEqual(self.save(changed_retry)['error']['code'], 'idempotency_conflict')
        lost_ack = call(self.root, 'decision_history')
        self.assertEqual(lost_ack['history'][0]['decision_id'], first['decision_id'])
        stale = dict(self.body, request_id=str(uuid.uuid4()))
        self.assertEqual(self.save(stale)['error']['code'], 'decision_conflict')
        identical = dict(stale, expected_head=first['decision_id'])
        self.assertTrue(self.save(identical)['reused'])
        amendment = dict(identical, request_id=str(uuid.uuid4()), choice='Test', rationale='ISOLATED AMENDMENT FIXTURE')
        second = self.save(amendment); self.assertTrue(second['ok'], second)
        history = call(self.root, 'decision_history')['history']
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0], first)
        self.assertEqual(history[1]['previous_record_sha256'], first['record_sha256'])
        self.assertEqual(history[1]['previous_decision_id'], first['decision_id'])
        self.assertEqual(history[1]['evidence_references'], first['evidence_references'])
        resumed = call(self.root, 'resume')
        self.assertIsNone(resumed['decision'])
        self.assertEqual(resumed['artifact_hashes'], self.mem['artifact_hashes'])
        # All original content survives; official store may update graph/access metadata.
        now = json.loads(self.statefile.read_text(encoding='utf-8'))
        before_records = original['records']; after_records = now['records']
        for record in before_records:
            self.assertEqual(record['content'], next(r['content'] for r in after_records if r['id'] == record['id']))

    def test_validation_explicit_action_and_changed_context(self):
        for updates in ({'choice': ''}, {'rationale': '  '}, {'explicit_action': 'approve'}, {'rationale': 'x'*8001}):
            self.assertEqual(self.save(dict(self.body, **updates))['error']['code'], 'invalid_decision')
        bad = copy.deepcopy(self.body); bad['context']['run_id'] = 'other'
        self.assertEqual(self.save(bad)['error']['code'], 'evidence_changed')
        self.assertEqual(call(self.root, 'decision_history')['history'], [])

    def test_failed_save_lock_recovery_and_exact_evidence(self):
        lock = self.statefile.with_name('nextwise.lock'); lock.write_text('ISOLATED TEST OWNED LOCK')
        try:
            self.assertEqual(self.save()['error']['code'], 'memory_locked')
        finally:
            lock.unlink()
        saved = self.save(); self.assertEqual(len(saved['history']), 1)
        first = saved['history'][0]
        evidence = call(self.root, 'decision_evidence', decision_id=first['decision_id'], kind='evidence_review')
        self.assertTrue(evidence['ok']); self.assertEqual(evidence['artifact'], self.mem['artifacts']['evidence_review'])

    def test_missing_evidence_flagged_without_rewriting_decision(self):
        first = self.save()['history'][0]
        state = json.loads(self.statefile.read_text(encoding='utf-8'))
        missing = self.mem['artifact_ids']['evidence_review']
        state['records'] = [r for r in state['records'] if r['id'] != missing]
        self.statefile.write_text(json.dumps(state), encoding='utf-8')  # Isolated storage only.
        history = call(self.root, 'decision_history')
        self.assertTrue(history['ok'], history)
        self.assertTrue(history['history'][0]['needs_review'])
        self.assertEqual(history['history'][0]['rationale'], first['rationale'])
        evidence = call(self.root, 'decision_evidence', decision_id=first['decision_id'], kind='evidence_review')
        self.assertEqual(evidence['error']['code'], 'missing_evidence')
        self.assertFalse(self.save(dict(self.body, request_id=str(uuid.uuid4()), expected_head=first['decision_id']))['ok'])

    def test_tampered_evidence_and_decision_fail_closed(self):
        first = self.save()['history'][0]
        state = json.loads(self.statefile.read_text(encoding='utf-8'))
        memory = next(r for r in state['records'] if r['id'] == self.mem['artifact_ids']['evidence_draft'])
        envelope = json.loads(memory['content']); envelope['bytes_base64'] = 'e30='
        memory['content'] = json.dumps(envelope); self.statefile.write_text(json.dumps(state), encoding='utf-8')
        self.assertTrue(call(self.root, 'decision_history')['history'][0]['needs_review'])
        self.assertEqual(call(self.root, 'decision_evidence', decision_id=first['decision_id'], kind='evidence_draft')['error']['code'], 'evidence_mismatch')
        memory = next(r for r in state['records'] if r['id'] == first['memory_id'])
        envelope = json.loads(memory['content']); envelope['decision']['choice'] = 'Adopt'
        memory['content'] = json.dumps(envelope); self.statefile.write_text(json.dumps(state), encoding='utf-8')
        self.assertEqual(call(self.root, 'decision_history')['error']['code'], 'decision_integrity')

    def test_http_request_protections_and_storage_failure(self):
        state = app.State(self.root); state.key = 'SECRET_TEST_SENTINEL'
        def loader(unused):
            return {'diagnostics': self.context}
        http = app.ThreadingHTTPServer(('127.0.0.1', 0), app.make_handler(state, loader))
        threading.Thread(target=http.serve_forever, daemon=True).start()
        base = f'http://127.0.0.1:{http.server_port}'
        def request(path='/api/decision', body=None, origin=True, cookie=True, method='POST'):
            headers = {'Content-Type': 'application/json'}
            if origin: headers['Origin'] = base
            if cookie: headers['Cookie'] = f'nextwise={state.cookie}'
            req = urllib.request.Request(base+path, data=json.dumps(body or self.body).encode() if method=='POST' and origin and cookie and state.key else None, headers=headers, method=method)
            try: response = urllib.request.urlopen(req)
            except urllib.error.HTTPError as error: response = error
            with response: return response.status, response.headers, response.read()
        try:
            self.assertEqual(request(origin=False)[0], 403)
            self.assertEqual(request(cookie=False)[0], 401)
            self.assertEqual(request(body=dict(self.body, choice=''))[0], 400)
            lock = self.statefile.with_name('nextwise.lock'); lock.write_text('ISOLATED FIXTURE')
            try:
                status, _, body = request(); self.assertEqual(status, 409); self.assertNotIn(b'SECRET_TEST_SENTINEL', body)
            finally: lock.unlink()
            self.assertEqual(request()[0], 200)
            saved = json.loads(request('/api/decisions', method='GET')[2])['history'][0]
            status, headers, body = request('/api/decision-evidence?id='+saved['decision_id']+'&kind=evidence_review', method='GET')
            self.assertEqual(status, 200); self.assertTrue(headers['Content-Type'].startswith('text/plain'))
            state.key = None
            self.assertEqual(request()[0], 401)
            self.assertEqual(request('/api/decisions', method='GET')[0], 200)
        finally:
            http.shutdown(); http.server_close()


if __name__ == '__main__': unittest.main()
