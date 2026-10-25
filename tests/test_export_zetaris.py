"""Offline integrity and preservation checks for the bounded CSV export."""
import copy
import csv
import io
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import export_zetaris as exporter


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.data, self.hashes = exporter.load_inputs(exporter.ROOT)

    def test_deterministic_snapshot_and_original_output(self):
        first = exporter.build()
        self.assertEqual(first, exporter.build())
        cases = list(csv.DictReader(io.StringIO(first[1]["evaluation_cases.csv"].decode(), newline="")))
        for row, original in zip(cases, self.data["results"]["cases"]):
            self.assertEqual(row["output"], original["output"])
            self.assertEqual(json.loads(row["output_json"]), original["output"])
            self.assertEqual(json.loads(row["validation_json"]), original["validation"])
            self.assertEqual(row["decision_json"], "null")
            self.assertEqual(json.loads(row["approval_json"])["status"], "pending_user_approval")

    def test_changed_references_fixtures_and_approvals_abort(self):
        for mutate in (
            lambda d: d["review"]["reviewed_draft"].update(sha256="bad"),
            lambda d: d["results"]["fixtures"][0]["snapshot"].update(input="changed"),
            lambda d: d["draft"]["accepted"][0].update(source_id="unregistered"),
            lambda d: d["results"].update(decision="approved"),
            lambda d: d["review"]["approval"].update(status="approved"),
            lambda d: d["results"]["cases"][0].update(fixture_sha256="bad"),
            lambda d: d["sources"]["sources"][1].update(id=d["sources"]["sources"][0]["id"]),
        ):
            data = copy.deepcopy(self.data)
            mutate(data)
            with self.assertRaises(ValueError):
                exporter.validate_inputs(data, self.hashes)

    def test_null_measurements_are_not_zero(self):
        self.data["results"]["cases"][0].update(duration_seconds=None, token_usage=None)
        rows = exporter.project(self.data, self.hashes)["evaluation_cases"]
        row = next(csv.DictReader(io.StringIO(exporter.csv_bytes(rows).decode(), newline="")))
        self.assertEqual(row["duration_seconds"], "\\N")
        self.assertEqual(row["prompt_tokens"], "\\N")
        self.assertEqual(row["duration_seconds_json"], "null")
        self.assertEqual(row["token_usage_json"], "null")


if __name__ == "__main__":
    unittest.main()
