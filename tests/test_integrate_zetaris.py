"""Offline integration checks using the exact pinned exports; no endpoint/key access."""
import copy
from decimal import Decimal
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import integrate_zetaris as integration


class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest, cls.tables = integration.read_snapshot()

    def compare(self, name, rows=None):
        spec = self.manifest["tables"][name]
        original = self.tables[name]
        return integration.compare_rows(name, spec, original, list(spec["columns"]),
            [[r[k] for k in spec["columns"]] for r in (original if rows is None else rows)])

    def test_all_six_tables_and_arbitrary_row_order(self):
        for name in integration.TABLES:
            live, report = self.compare(name, list(reversed(self.tables[name])))
            self.assertEqual(report["status"], "PASS")
            self.assertEqual(report["rows"], self.manifest["tables"][name]["row_count"])
        _, cases = self.compare("evaluation_cases")
        self.assertGreaterEqual(cases["multiline_cells"], 4)
        self.assertGreater(cases["json_null_cells"], 0)

    def test_every_column_corruption_is_rejected(self):
        for name, original in self.tables.items():
            for col in original[0]:
                rows = copy.deepcopy(original)
                rows[0][col] = "corrupted"
                with self.assertRaises(ValueError, msg=f"{name}.{col}"):
                    self.compare(name, rows)

    def test_quotes_newlines_json_null_and_duplicate_keys(self):
        for col, replacement in (("output", self.tables["evaluation_cases"][0]["output"].replace("\n", " ")),
                                 ("output_json", "null"), ("decision_json", None)):
            rows = copy.deepcopy(self.tables["evaluation_cases"])
            rows[0][col] = replacement
            with self.assertRaises(ValueError):
                self.compare("evaluation_cases", rows)
        rows = copy.deepcopy(self.tables["evaluation_cases"])
        rows[1] = rows[0]
        with self.assertRaises(ValueError):
            self.compare("evaluation_cases", rows)

    def test_reference_and_approval_checks(self):
        self.assertTrue(integration.references(self.tables).startswith("PASS"))
        for name, col, value in (("evidence_claims", "source_id", "missing"),
                                 ("evidence_reviews", "approval_status", "approved"),
                                 ("evaluation_cases", "draft_sha256", "wrong")):
            tables = copy.deepcopy(self.tables)
            tables[name][0][col] = value
            with self.assertRaises(ValueError):
                integration.references(tables)

    def test_numeric_casts_and_unknown_aggregates(self):
        for name in ("project_profiles", "evaluation_cases"):
            spec = self.manifest["tables"][name]
            columns = spec["primary_key"] + [k for k,v in spec["columns"].items() if v in ("BIGINT", "DOUBLE")]
            rows = [[r[k] for k in columns] for r in self.tables[name]]
            self.assertEqual(integration.validate_numeric(name, spec, self.tables[name], columns, rows)["status"], "PASS")
            rows[0][-1] = None
            with self.assertRaises(ValueError):
                integration.validate_numeric(name, spec, self.tables[name], columns, rows)
        tables = copy.deepcopy(self.tables)
        tables["evaluation_cases"][0]["duration_seconds"] = "\\N"
        self.assertIsNone(integration.expected_join(tables)[0]["request_seconds"])

    def test_join_oracle_counts_and_detects_duplication(self):
        expected = integration.expected_join(self.tables)
        self.assertEqual([r["accepted_publisher_claim_count"] for r in expected], [4, 2, 0])
        self.assertTrue(all(r["attempted_cases"] == 4 and r["quality_pass_cases"] == 1 for r in expected))
        self.assertEqual(expected[0]["request_seconds"], Decimal("10.378"))
        self.assertEqual(expected[0]["reported_total_tokens"], 3200)
        names = list(expected[0])
        rows = [[str(r[k]) if isinstance(r[k], Decimal) else r[k] for k in names] for r in reversed(expected)]
        integration.compare_join(expected, names, rows)
        rows[0][names.index("attempted_cases")] = "24"
        with self.assertRaises(ValueError):
            integration.compare_join(expected, names, rows)

    def test_conflicts_and_profile_creation_rejected(self):
        name = "investigations"
        original = {"format": "csv", "storageType": "NdpFs", "path": f"dffs://nextwise/{name}.csv",
                    "delimiter": ",", "parameters": dict(integration.PARAMS)}
        integration.check_registration(name, original)
        original["parameters"]["escape"] = "\\"
        with self.assertRaises(ValueError):
            integration.check_registration(name, original)
        with self.assertRaises(ValueError):
            integration.registration_sql("project_profiles")


if __name__ == "__main__":
    unittest.main()
