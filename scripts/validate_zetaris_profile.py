"""Read-only exact validation of nextwise.project_profiles; no key/body logging."""
import csv
from datetime import datetime, timezone
import getpass
import hashlib
import json
from pathlib import Path
import sys
import urllib.error
import urllib.request
import uuid
import warnings

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "data/zetaris_exports/20261024T151413Z-fdf0c15b-csv-5fa0db458643"
REPORT = ROOT / "reports/zetaris_project_profiles_validation.json"
ENDPOINT = "http://localhost:8888/api/v1.0/sql-editor/sqls/run"
SQL = "SELECT * FROM nextwise.project_profiles"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def expected_table():
    manifest = json.loads((SNAPSHOT / "manifest.json").read_text(encoding="utf-8"))
    table = manifest["tables"]["project_profiles"]
    path = SNAPSHOT / "project_profiles.csv"
    require(hashlib.sha256(path.read_bytes()).hexdigest() == table["sha256"], "Export hash mismatch")
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, strict=True)
        require(reader.fieldnames == list(table["columns"]), "Export header differs from manifest")
        rows = list(reader)
    require(len(rows) == table["row_count"] == 1, "Unexpected exported row count")
    require(rows[0]["project_id"] == "ai-raw-gourmet", "Unexpected exported project ID")
    require(all(None not in row and all(v is not None for v in row.values()) for row in rows),
            "Malformed exported column alignment")
    return table, rows


def unpack_response(body):
    """Accept explicit tabular envelopes only; never search arbitrary scalar values."""
    require(isinstance(body, dict) and "data" in body, "Response has no data envelope")
    candidates = []

    def visit(node, depth=0):
        if depth > 4 or not isinstance(node, dict):
            return
        columns = node.get("columns", node.get("columnNames", node.get("headers", node.get("schema"))))
        if isinstance(columns, dict):
            columns = columns.get("fields")
        names, types = None, None
        if isinstance(columns, list) and columns:
            if all(isinstance(c, str) for c in columns):
                names = columns
            elif all(isinstance(c, dict) and isinstance(c.get("name"), str) for c in columns):
                names = [c["name"] for c in columns]
                types = [c.get("dataType", c.get("type")) for c in columns]
        for key in ("rows", "data", "records", "resultSet"):
            rows = node.get(key)
            if names is not None and isinstance(rows, list):
                candidates.append((names, rows, types))
        for key in ("data", "result", "results", "queryResult"):
            visit(node.get(key), depth + 1)

    visit(body)
    require(len(candidates) == 1, "Unsupported or ambiguous tabular response envelope")
    names, rows, types = candidates[0]
    require(len(set(names)) == len(names), "Duplicate returned column names")
    normalized = []
    for row in rows:
        if isinstance(row, dict):
            require(set(row) == set(names), "Returned object row has missing/extra columns")
            normalized.append([row[name] for name in names])
        else:
            require(isinstance(row, list) and len(row) == len(names), "Returned positional row width mismatch")
            normalized.append(row)
    return names, normalized, types


def compare(table, expected, names, rows):
    checks = []

    def check(label, ok):
        checks.append({"check": label, "result": "MATCH" if ok else "MISMATCH"})

    check("column names and order", names == list(table["columns"]))
    check("row count (expected 1)", len(rows) == len(expected))
    if len(rows) == 1 and len(names) == len(set(names)):
        actual = dict(zip(names, rows[0]))
        for name, value in expected[0].items():
            got = actual.get(name)
            kind = table["columns"][name]
            # inferSchema=false returns numeric CSV text as STRING. A typed integer
            # is also lossless, but no float, trimming, case or JSON normalization.
            same = name in actual and (type(got) is str and got == value)
            if kind == "BIGINT":
                same = same or (type(got) is int and str(got) == value)
                if value == "\\N":
                    same = got is None
            check(f"column {name}: exact exported value", same)
            if name.endswith("_json"):
                try:
                    valid = type(got) is str and json.loads(got) == json.loads(value)
                except (ValueError, TypeError):
                    valid = False
                check(f"column {name}: JSON content and quote preservation", valid and same)
        check("project ID ai-raw-gourmet", actual.get("project_id") == "ai-raw-gourmet")
    else:
        check("all exported cells comparable", False)
    return checks


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def query_once():
    # Never fall back to echoed stdin if no private console is available.
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        api_key = getpass.getpass("Zetaris API key (hidden): ").strip()
    require(bool(api_key), "Empty API key")
    payload = {"queryId": str(uuid.uuid4()), "sql": SQL, "source": "SqlEditor", "limit": 100}
    request = urllib.request.Request(ENDPOINT, data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
                 "X-Org-ID": "1", "X-Request-ID": str(uuid.uuid4())})
    del api_key
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        with opener.open(request, timeout=60) as response:
            status = response.status
            raw = response.read()
    finally:
        request.remove_header("Authorization")
    require(status == 200, "Non-200 response")
    try:
        return json.loads(raw)
    except (ValueError, UnicodeError):
        raise ValueError("Response was not valid JSON") from None


def main():
    report = {"observed_at_utc": datetime.now(timezone.utc).isoformat(),
              "table": "nextwise.project_profiles", "sql": SQL,
              "export_path": str(SNAPSHOT / "project_profiles.csv"), "status": "NOT_VALIDATED"}
    try:
        table, expected = expected_table()
        report["export_sha256"] = table["sha256"]
        names, rows, types = unpack_response(query_once())
        report["returned_row_count"] = len(rows)
        # Report only known local column names and aggregate alignment results.
        # Never write response bodies, arbitrary returned strings, or metadata.
        report["checks"] = compare(table, expected, names, rows)
        report["status"] = "PASS" if all(c["result"] == "MATCH" for c in report["checks"]) else "FAIL"
        report["schema_note"] = "inferSchema=false: numeric text accepted; numeric SQL typing not established."
    except urllib.error.HTTPError as exc:
        report["error"] = f"HTTP {exc.code}; body suppressed"
        exc.close()
    except (urllib.error.URLError, TimeoutError, OSError):
        report["error"] = "Connection or local I/O failure; details suppressed"
    except getpass.GetPassWarning:
        report["error"] = "Private console unavailable; no key requested through echoed input"
    except (EOFError, KeyboardInterrupt):
        report["error"] = "Private input cancelled"
    except ValueError as exc:
        # Only fixed validator messages reach here; never interpolate server data.
        report["error"] = str(exc)
    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Validation: {report['status']}")
    for check in report.get("checks", []):
        print(f"{check['result']}: {check['check']}")
    if "error" in report:
        print(report["error"])
    print(f"Sanitized report: {REPORT}")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
