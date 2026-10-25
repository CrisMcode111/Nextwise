"""Offline cases: no API or secret access."""
import copy
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import validate_zetaris_profile as validator


class ProfileValidationTests(unittest.TestCase):
    def setUp(self):
        self.table, self.expected = validator.expected_table()
        self.names = list(self.table["columns"])
        self.rows = [[self.expected[0][name] for name in self.names]]

    def checks(self, rows=None, names=None):
        return validator.compare(self.table, self.expected,
                                 self.names if names is None else names,
                                 self.rows if rows is None else rows)

    def test_exact_values_and_string_numeric(self):
        self.assertTrue(all(c["result"] == "MATCH" for c in self.checks()))
        self.rows[0][self.names.index("team_size")] = 1
        self.assertTrue(all(c["result"] == "MATCH" for c in self.checks()))

    def test_every_corrupted_column_fails(self):
        for index in range(len(self.names)):
            rows = copy.deepcopy(self.rows)
            rows[0][index] = "corrupted"
            self.assertTrue(any(c["result"] == "MISMATCH" for c in self.checks(rows)))

    def test_count_alignment_quotes_and_json_null(self):
        self.assertTrue(any(c["result"] == "MISMATCH" for c in self.checks([])))
        self.assertTrue(any(c["result"] == "MISMATCH" for c in self.checks(self.rows * 2)))
        swapped = self.names.copy()
        swapped[0], swapped[1] = swapped[1], swapped[0]
        self.assertTrue(any(c["result"] == "MISMATCH" for c in self.checks(names=swapped)))
        for change in (None, self.rows[0][-1].replace('"', '""'), json.dumps(json.loads(self.rows[0][-1]), indent=2)):
            rows = copy.deepcopy(self.rows)
            rows[0][-1] = change
            self.assertTrue(any(c["result"] == "MISMATCH" for c in self.checks(rows)))

    def test_explicit_envelopes_and_malformed_width(self):
        for response in (
            {"data": {"columns": self.names, "rows": self.rows}},
            {"data": {"schema": {"fields": [{"name": n, "type": "string"} for n in self.names]}, "data": self.rows}},
            {"data": {"columns": self.names, "rows": self.expected}},
        ):
            names, rows, _ = validator.unpack_response(response)
            self.assertEqual(names, self.names)
            self.assertEqual(rows, self.rows)
        for response in (
            {"data": {"columns": self.names, "rows": [["ai-raw-gourmet"]]}},
            {"data": {"columns": self.names + [self.names[0]], "rows": []}},
            {"data": {"anything": 1}},
        ):
            with self.assertRaises(ValueError):
                validator.unpack_response(response)


if __name__ == "__main__":
    unittest.main()
