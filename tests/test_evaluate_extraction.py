"""Offline pilot checks: no real endpoint or token is used."""
import copy
import http.client
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import evaluate_extraction as evaluator


class ExtractionTests(unittest.TestCase):
    def setUp(self):
        self.use_case = json.loads(evaluator.USE_CASE.read_text(encoding="utf-8"))
        self.schema = json.loads(evaluator.SCHEMA_PATH.read_text(encoding="utf-8"))
        self.fixtures = self.use_case["proposed_evaluation_examples"]["examples"]

    def valid(self, fixture):
        return {"facts": [{"field": k, "value": v, "evidence": fixture["input"]} for k, v in fixture["expected_explicit_facts"].items()],
            "unknowns": evaluator.RUBRIC[fixture["id"]]["unknowns"],
            "issues": [{"kind": evaluator.RUBRIC[fixture["id"]]["issue"], "evidence": [fixture["input"]], "clarification_question": "Please clarify the uncertain requirement?"}]}

    def response(self, fixture, output=None):
        return {"ok": True, "output": json.dumps(self.valid(fixture) if output is None else output),
                "actual_model": "offline-fixture-model", "token_usage": None, "duration_seconds": 0.01, "http_status": 200, "error": None}

    def test_valid_output_all_four(self):
        for fixture in self.fixtures:
            findings, _ = evaluator.assess(json.dumps(self.valid(fixture)), fixture, self.schema)
            self.assertTrue(findings["quality_pass"], findings)

    def test_missing_and_invented_requirements(self):
        fixture = self.fixtures[0]
        output = self.valid(fixture)
        output["facts"].pop()
        output["facts"][0]["value"] = "lunch"
        findings, _ = evaluator.assess(json.dumps(output), fixture, self.schema)
        self.assertFalse(findings["quality_pass"])
        self.assertIn("ready_within_minutes", findings["missing_requirements"])
        self.assertIn("meal", findings["invented_or_changed_requirements"])

    def test_contradiction_must_remain_visible(self):
        fixture = self.fixtures[2]
        output = self.valid(fixture)
        output["issues"] = []
        findings, _ = evaluator.assess(json.dumps(output), fixture, self.schema)
        self.assertTrue(findings["well_formed"])
        self.assertFalse(findings["required_issue_detected"])
        self.assertFalse(findings["quality_pass"])

    def test_unknowns_and_evidence_are_checked(self):
        fixture = self.fixtures[0]
        output = self.valid(fixture)
        output["unknowns"] = ["people_count"]
        output["facts"][0]["evidence"] = "not in input"
        findings, _ = evaluator.assess(json.dumps(output), fixture, self.schema)
        self.assertIn("meal", findings["unsupported_evidence"])
        self.assertTrue(findings["missing_unknown_categories"])
        self.assertIn("people_count", findings["incorrect_unknown_categories"])

    def test_malformed_json_and_schema(self):
        for output in ["not JSON", "```json\n{}\n```", '{"facts":[],"facts":[]}', '{"facts":NaN}', '{}', '[]']:
            self.assertFalse(evaluator.assess(output, self.fixtures[0], self.schema)[0]["well_formed"])

    def test_expected_answers_never_in_request(self):
        fixture = copy.deepcopy(self.fixtures[0])
        fixture["expected_explicit_facts"]["secret_test_marker"] = "DO_NOT_SEND_EXPECTATIONS"
        payload = evaluator.payload_for(evaluator.messages_for(fixture["input"], self.schema))
        self.assertNotIn("DO_NOT_SEND_EXPECTATIONS", json.dumps(payload))
        self.assertEqual(payload["max_tokens"], 1024)
        self.assertNotIn("tools", payload)

    def test_request_failures_and_configuration(self):
        class ResetBody:
            def read(self, *args):
                raise ConnectionResetError("private text")
            def close(self):
                pass
        for error in [TimeoutError("private text"), urllib.error.HTTPError("url", 502, "Bad Gateway", {}, ResetBody()),
                      urllib.error.HTTPError("url", 502, "Bad Gateway", {}, io.BytesIO(b'{"error":{"message":"Bearer secret-token","code":"provider_error"}}'))]:
            with patch.object(evaluator.urllib.request, "urlopen", side_effect=error) as call:
                result = evaluator.request_output("secret-token", evaluator.messages_for(self.fixtures[0]["input"], self.schema))
            self.assertFalse(result["ok"])
            self.assertNotIn("secret-token", json.dumps(result))
            self.assertNotIn("private text", json.dumps(result))
            self.assertEqual(call.call_args.kwargs["timeout"], 180)
            request = call.call_args.args[0]
            self.assertEqual(request.full_url, evaluator.transport_helpers.ENDPOINT)
            self.assertEqual(request.get_header("Meterless-tier-split"), "off")

    def run_mock_pilot(self, requester):
        base = ROOT / "data/evaluations"
        base.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as directory:
            result = evaluator.run_pilot(self.use_case, self.schema, "offline-only", Path(directory) / "offline-run", requester)
            saved = json.loads((Path(directory) / "offline-run/results.json").read_text())
            self.assertEqual(saved, result)
            recommendation = json.loads((Path(directory) / "offline-run/recommendation.json").read_text())
            self.assertIsNone(recommendation["decision"])
            self.assertEqual(recommendation["approval"]["status"], "pending_user_approval")
            return result

    def test_stop_request_failure_preserves_partial_results(self):
        calls = []
        def requester(*args):
            calls.append(1)
            return self.response(self.fixtures[0]) if len(calls) == 1 else {"ok": False, "error": "offline timeout", "duration_seconds": 180}
        result = self.run_mock_pilot(requester)
        self.assertEqual(len(calls), 2)
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(result["stop_reason"], "request_failure")
        self.assertEqual(len(result["unattempted_fixture_ids"]), 2)

    def test_stop_malformed_output(self):
        calls = []
        def requester(*args):
            calls.append(1)
            return {"ok": True, "output": "broken"}
        result = self.run_mock_pilot(requester)
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["stop_reason"], "malformed_output")

    def test_quality_failure_continues_without_retry(self):
        calls = []
        def requester(*args):
            i = len(calls)
            calls.append(1)
            output = self.valid(self.fixtures[i])
            output["facts"] = []
            return self.response(self.fixtures[i], output)
        result = self.run_mock_pilot(requester)
        self.assertEqual(len(calls), 4)
        self.assertEqual(result["status"], "completed_pilot")
        self.assertTrue(all(not c["validation"]["quality_pass"] for c in result["cases"]))

    def test_dry_run_has_no_network_or_getpass(self):
        with patch.object(sys, "argv", ["evaluate_extraction.py", "--dry-run"]), patch.object(evaluator, "request_output") as request, patch.object(evaluator.getpass, "getpass") as prompt:
            self.assertEqual(evaluator.main(), 0)
            request.assert_not_called()
            prompt.assert_not_called()


if __name__ == "__main__":
    unittest.main()
