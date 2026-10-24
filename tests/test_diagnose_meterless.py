"""The live diagnostic runs only its two explicit requests and keeps tokens private."""

import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import diagnose_meterless as diagnostic


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        argv = patch.object(sys, "argv", ["diagnose_meterless.py"])
        argv.start()
        self.addCleanup(argv.stop)

    def test_short_failure_stops_without_full_request(self):
        with tempfile.TemporaryDirectory() as directory:
            report_path = Path(directory) / "report.json"
            failure = {"ok": False, "http_status": 502, "error": "HTTP 502: Bad Gateway"}
            with patch.object(diagnostic, "REPORT_PATH", report_path), \
                 patch("sys.stdin.isatty", return_value=True), \
                 patch("getpass.getpass", return_value="offline-placeholder") as get_token, \
                 patch.object(diagnostic.analyzer, "request_claims", return_value=failure) as request, \
                 patch.object(diagnostic.analyzer, "main") as full, patch("sys.stdout", io.StringIO()):
                self.assertEqual(diagnostic.main(), 1)
            get_token.assert_called_once()
            request.assert_called_once()
            full.assert_not_called()
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "baseline_failed_full_not_sent")
            self.assertNotIn("offline-placeholder", report_path.read_text(encoding="utf-8"))

    def test_successful_baseline_reuses_hidden_token_for_full_analysis(self):
        analyzer = diagnostic.analyzer
        original_max, original_timeout = analyzer.MAX_TOKENS, analyzer.TIMEOUT_SECONDS
        observed = []
        success = {"ok": True, "http_status": 200, "data": {
            "model": "test-model", "choices": [{"message": {"content": "test response"}}],
        }}
        def request(token, messages, **options):
            observed.append((analyzer.MAX_TOKENS, analyzer.TIMEOUT_SECONDS))
            return success
        def full_analysis():
            token = analyzer.getpass.getpass("hidden")
            analyzer.request_claims(token, [{"role": "user", "content": "full"}])
            return 0
        with tempfile.TemporaryDirectory() as directory:
            report_path = Path(directory) / "report.json"
            with patch.object(diagnostic, "REPORT_PATH", report_path), \
                 patch("sys.stdin.isatty", return_value=True), \
                 patch("getpass.getpass", return_value="offline-placeholder") as get_token, \
                 patch.object(analyzer, "request_claims", side_effect=request), \
                 patch.object(analyzer, "main", side_effect=full_analysis), \
                 patch("sys.stdout", io.StringIO()):
                self.assertEqual(diagnostic.main(), 0)
            get_token.assert_called_once()
            self.assertEqual(observed, [(1024, 120), (original_max, original_timeout)])
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(len(report["tests"]), 2)
            self.assertEqual(report["status"], "completed")
            self.assertNotIn("offline-placeholder", report_path.read_text(encoding="utf-8"))
        self.assertEqual((analyzer.MAX_TOKENS, analyzer.TIMEOUT_SECONDS), (original_max, original_timeout))


if __name__ == "__main__":
    unittest.main()
