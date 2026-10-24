"""Additional H-MEM artifacts survive independent Python and Node processes."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import evaluate_extraction as evaluator


class ExtractionMemoryTests(unittest.TestCase):
    def test_extended_round_trip_and_hash_rejection(self):
        base = ROOT / "data/evaluations"
        base.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as temporary:
            directory = Path(temporary)
            directory.rmdir()
            use_case = json.loads(evaluator.USE_CASE.read_text())
            schema = json.loads(evaluator.SCHEMA_PATH.read_text())
            # Request failure is an offline fixture, not a real endpoint call.
            result = evaluator.run_pilot(use_case, schema, "offline-only", directory,
                requester=lambda *args: {"ok": False, "error": "offline fixture failure", "duration_seconds": 1, "actual_model": None, "token_usage": None})
            results_path = directory / "results.json"
            memory = directory / "memory"
            command = [sys.executable, str(ROOT / "scripts/investigation_memory.py")]
            def call(operation, extra=(), expected=0):
                completed = subprocess.run(command + [operation, "--memory-root", str(memory), "--json", *extra],
                    capture_output=True, encoding="utf-8", timeout=60, cwd=ROOT)
                self.assertEqual(completed.returncode, expected, completed.stdout + completed.stderr)
                return json.loads(completed.stdout)
            old = call("import")
            imported = call("import", ["--evaluation-results", str(results_path)])
            repeated = call("import", ["--evaluation-results", str(results_path)])
            self.assertTrue(repeated["reused"])
            self.assertEqual(imported["artifact_ids"], repeated["artifact_ids"])
            self.assertEqual(old["artifact_ids"]["evidence_review"], imported["artifact_ids"]["evidence_review"])
            resumed = call("resume")
            self.assertEqual(resumed["evaluation_results"], result)
            self.assertEqual(resumed["use_case"], use_case)
            self.assertEqual(resumed["evaluation_results"]["status"], "incomplete")
            self.assertEqual(resumed["evaluation_recommendation"]["approval"]["status"], "pending_user_approval")
            self.assertIsNone(resumed["decision"])
            self.assertIsNone(resumed["evaluation_recommendation"]["decision"])
            self.assertTrue(resumed["local_artifacts"]["snapshot_matches_current_files"])
            recommendation = directory / "recommendation.json"
            document = json.loads(recommendation.read_text())
            document["evaluation_reference"]["sha256"] = "0" * 64
            recommendation.write_text(json.dumps(document))
            rejected = call("import", ["--evaluation-results", str(results_path)], expected=1)
            self.assertEqual(rejected["error"]["code"], "evaluation_integrity_error")


if __name__ == "__main__":
    unittest.main()
