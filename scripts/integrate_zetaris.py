"""Register missing allowlisted tables, validate exact CSVs, execute the SQL join.

Standard library only. Default is read-only; --register-missing permits five CREATEs.
One getpass prompt, no key persistence, no raw HTTP body/error logging.
"""
import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import getpass
import hashlib
import json
from pathlib import Path
import urllib.error
import urllib.request
import uuid
import warnings

import export_zetaris as exporter
import validate_zetaris_profile as profile

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = profile.SNAPSHOT
QUERY = ROOT / "scripts/sql/nextwise_investigation.sql"
PARAMS = {"header": "true", "inferSchema": "false", "multiLine": "true", "escape": '"'}
TABLES = tuple(exporter.KEYS)
ALLOWED_CREATE = TABLES[1:]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_snapshot():
    manifest = json.loads((SNAPSHOT / "manifest.json").read_text(encoding="utf-8"))
    snapshot, outputs = exporter.build()  # Pure validation; writes nothing.
    require(snapshot == manifest["snapshot_id"], "Snapshot identity changed")
    for name, raw in outputs.items():
        require((SNAPSHOT / name).read_bytes() == raw, f"Snapshot bytes differ: {name}")
    tables = {}
    for name in TABLES:
        spec = manifest["tables"][name]
        with (SNAPSHOT / spec["filename"]).open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f, strict=True)
            require(reader.fieldnames == list(spec["columns"]), f"Local columns differ: {name}")
            tables[name] = list(reader)
    return manifest, tables


def registration_sql(name):
    require(name in ALLOWED_CREATE, "CREATE outside the five missing-table allowlist")
    return (f"CREATE LIGHTNING FILESTORE TABLE {name} FROM nextwise FORMAT csv OPTIONS (\n"
            f"  path 'dffs://nextwise/{name}.csv', delimiter ',', header 'true',\n"
            "  inferSchema 'false', multiLine 'true', escape '\"'\n)")


def check_registration(name, value):
    expected = {"format": "csv", "storageType": "NdpFs", "path": f"dffs://nextwise/{name}.csv",
                "delimiter": ",", "parameters": PARAMS}
    for field, wanted in expected.items():
        require(value.get(field) == wanted, f"Conflicting registration nextwise.{name}: {field}")
    require(value.get("scanType") in (None, "", "FILE_SCAN"), f"Conflicting scanType: {name}")
    require(value.get("pathGlobFilter") in (None, ""), f"Conflicting pathGlobFilter: {name}")


def key_for(row, spec):
    return tuple(row[k] for k in spec["primary_key"])


def compare_rows(name, spec, expected, names, raw_rows):
    require(names == list(spec["columns"]), f"{name}: column names/order mismatch")
    require(len(raw_rows) == len(expected) == spec["row_count"],
            f"{name}: row count expected {len(expected)}, got {len(raw_rows)}")
    require(all(len(row) == len(names) for row in raw_rows), f"{name}: row width mismatch")
    actual = [dict(zip(names, row)) for row in raw_rows]
    expected_by_key = {key_for(row, spec): row for row in expected}
    actual_by_key = {}
    for row in actual:
        key = key_for(row, spec)
        require(all(type(v) is str for v in key), f"{name}: non-string/missing primary key")
        require(key not in actual_by_key, f"{name}: duplicate primary key {key!r}")
        actual_by_key[key] = row
    require(set(actual_by_key) == set(expected_by_key), f"{name}: primary key set differs")
    stats = Counter()
    for key, wanted in expected_by_key.items():
        for column, text in wanted.items():
            got = actual_by_key[key][column]
            kind = spec["columns"][column]
            if kind in ("BIGINT", "DOUBLE") and text == "\\N":
                same = got is None
            else:
                # Exact raw STRING preservation is required with inferSchema=false.
                same = type(got) is str and got == text
            require(same, f"{name} key={key!r} column={column}: expected {text!r}, got {got!r}")
            stats["cells"] += 1
            if column.endswith("_json"):
                require(json.loads(got) == json.loads(text), f"{name}.{column}: JSON differs")
                stats["json_cells"] += 1
                stats["json_null_cells"] += int(text == "null")
            stats["quoted_text_cells"] += int('"' in text)
            stats["multiline_cells"] += int("\n" in text or "\r" in text)
            stats["numeric_null_cells"] += int(kind in ("BIGINT", "DOUBLE") and text == "\\N")
    return actual, {"status": "PASS", "rows": len(actual), "unique_keys": len(actual_by_key), **stats}


def references(tables):
    p = {r["project_id"] for r in tables["project_profiles"]}
    inv = {r["investigation_id"] for r in tables["investigations"]}
    sources = {(r["investigation_id"], r["source_id"]) for r in tables["sources"]}
    drafts = {(r["investigation_id"], r["draft_sha256"]) for r in tables["evidence_claims"]}
    reviews = {(r["investigation_id"], r["reviewed_draft_sha256"]): r for r in tables["evidence_reviews"]}
    for name, rows in tables.items():
        for row in rows:
            if "project_id" in row:
                require(row["project_id"] in p, f"{name}: orphan project")
            if "investigation_id" in row:
                require(row["investigation_id"] in inv, f"{name}: orphan investigation")
            if "decision_json" in row:
                require(row["decision_json"] == "null", f"{name}: decision changed")
    for row in tables["evidence_claims"]:
        require((row["investigation_id"], row["source_id"]) in sources, "Orphan claim source")
        require((row["investigation_id"], row["draft_sha256"]) in reviews, "Claim/review draft mismatch")
        require(row["claim_kind"] == "publisher_claim", "Claim kind changed")
    for row in tables["evidence_reviews"]:
        require((row["investigation_id"], row["reviewed_draft_sha256"]) in drafts, "Review/draft mismatch")
        require(row["approval_status"] == "pending_user_approval", "Review approval changed")
    for row in tables["evaluation_cases"]:
        require((row["investigation_id"], row["draft_sha256"]) in reviews, "Pilot/review mismatch")
        record = json.loads(row["record_json"])
        require(record["fixture_sha256"] == row["fixture_sha256"], "Pilot fixture mismatch")
        rec = json.loads(row["recommendation_json"])
        for doc in (json.loads(row["approval_json"]), rec["approval"]):
            require(doc["status"] == "pending_user_approval", "Pilot/recommendation approval changed")
        require(rec["decision"] is None, "Recommendation decision changed")
    return "PASS: project, investigation, source, draft/review/pilot and fixture lineage; approvals and decisions unchanged"


def number(text):
    return None if text is None or text == "\\N" else Decimal(str(text))


def numeric_sql(name, spec):
    columns = list(spec["primary_key"])
    for column, kind in spec["columns"].items():
        if kind in ("BIGINT", "DOUBLE"):
            sql_type = "BIGINT" if kind == "BIGINT" else "DECIMAL(20,6)"
            columns.append(f"CASE WHEN {column} = '\\\\N' THEN NULL ELSE CAST({column} AS {sql_type}) END AS {column}")
    return f"SELECT {', '.join(columns)} FROM nextwise.{name}"


def validate_numeric(name, spec, expected, names, rows):
    numeric = [k for k, v in spec["columns"].items() if v in ("BIGINT", "DOUBLE")]
    require(names == spec["primary_key"] + numeric, f"{name}: numeric projection columns differ")
    wanted = {key_for(r, spec): r for r in expected}
    require(len(rows) == len(wanted), f"{name}: numeric projection row count differs")
    seen = set()
    for raw in rows:
        row = dict(zip(names, raw))
        key = key_for(row, spec)
        require(key in wanted and key not in seen, f"{name}: numeric projection keys differ")
        seen.add(key)
        for col in numeric:
            original, converted = number(wanted[key][col]), number(row[col])
            require(original == converted, f"{name} key={key!r}: SQL numeric conversion differs for {col}")
            if original is not None:
                require(original.is_finite() and original >= 0, f"{name}.{col}: invalid measurement")
                if spec["columns"][col] == "BIGINT":
                    require(original == original.to_integral_value(), f"{name}.{col}: non-integral value")
            if col in ("schema_valid", "quality_pass"):
                require(original in (Decimal(0), Decimal(1), None), f"{name}.{col}: invalid flag")
    return {"status": "PASS", "rows": len(rows), "columns": numeric,
            "calculation_types": {c: "DECIMAL(20,6)" if spec["columns"][c] == "DOUBLE" else "BIGINT" for c in numeric}}


def expected_join(t):
    # Independent oracle only: the saved result must still come from live Zetaris SQL.
    p, i, r = (t[k][0] for k in ("project_profiles", "investigations", "evidence_reviews"))
    cases = t["evaluation_cases"]
    def total(col):
        values = [number(c[col]) for c in cases]
        return None if any(v is None for v in values) else sum(values, Decimal(0))
    rows = []
    for s in sorted(t["sources"], key=lambda row: row["source_id"]):
        row = {k: p[k] for k in ("project_id", "project_name", "stage")}
        row.update(team_size=number(p["team_size"]), constraints_json=p["constraints_json"],
                   investigation_id=i["investigation_id"], question=i["question"],
                   investigation_decision_json=i["decision_json"])
        row.update({k: r[k] for k in ("review_status", "approval_status", "readiness_status", "reviewed_draft_sha256")})
        row["review_decision_json"] = r["decision_json"]
        row.update({k: s[k] for k in ("source_id", "requested_url", "retrieved_at_utc", "publication_date_json")})
        row["accepted_publisher_claim_count"] = Decimal(sum(c["source_id"] == s["source_id"] for c in t["evidence_claims"]))
        row.update({k: cases[0][k] for k in ("run_id", "actual_model", "evaluation_status")})
        row.update({"pilot_"+k: cases[0][k] for k in ("approval_json", "decision_json", "monetary_cost_json")})
        row.update(attempted_cases=Decimal(len(cases)), schema_valid_cases=total("schema_valid"),
                   quality_pass_cases=total("quality_pass"), request_seconds=total("duration_seconds"),
                   reported_prompt_tokens=total("prompt_tokens"), reported_completion_tokens=total("completion_tokens"),
                   reported_total_tokens=total("total_tokens"))
        rows.append(row)
    return rows


def compare_join(expected, names, rows):
    require(set(names) == set(expected[0]), "Joined result columns differ")
    require(len(rows) == len(expected), f"Joined row count expected {len(expected)}, got {len(rows)}")
    wanted = {row["source_id"]: row for row in expected}
    seen = set()
    for raw in rows:
        row = dict(zip(names, raw))
        sid = row["source_id"]
        require(sid in wanted and sid not in seen, "Joined source IDs differ/duplicate")
        seen.add(sid)
        for key, value in wanted[sid].items():
            got = row[key]
            same = number(got) == value if isinstance(value, Decimal) else got == value
            require(same, f"Joined source={sid!r} column={key}: expected {value!r}, got {got!r}")
    return "PASS: all joined columns and values, one row per source; separately aggregated claim/pilot counts"


class Client:
    def __init__(self, key):
        self._key = key
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), profile.NoRedirect())

    def request(self, path, payload=None, missing_ok=False):
        request = urllib.request.Request("http://localhost:8888"+path,
            data=json.dumps(payload).encode("utf-8") if payload is not None else None,
            method="POST" if payload is not None else "GET",
            headers={"Authorization": f"Bearer {self._key}", "Content-Type": "application/json",
                     "X-Org-ID": "1", "X-Request-ID": str(uuid.uuid4())})
        try:
            with self.opener.open(request, timeout=60) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as exc:
            code = exc.code
            exc.close()
            if code == 404 and missing_ok:
                return None
            raise ValueError(f"HTTP {code}; response body suppressed") from None
        except (urllib.error.URLError, OSError, UnicodeError, json.JSONDecodeError):
            raise ValueError("Request/JSON decoding failed; body and connection details suppressed") from None
        finally:
            request.remove_header("Authorization")

    def registration(self, name):
        result = self.request(f"/api/v1.0/lightning-database/databases/nextwise/file-store-tables/{name}", missing_ok=True)
        if result is None:
            return None
        doc = result.get("data", result)
        require(isinstance(doc, dict), "Unexpected registration metadata envelope")
        fields = ("format", "storageType", "path", "delimiter", "parameters", "description", "scanType", "pathGlobFilter")
        return {k: doc[k] for k in fields if k in doc}

    def sql(self, sql):
        response = self.request("/api/v1.0/sql-editor/sqls/run",
            {"queryId": str(uuid.uuid4()), "sql": sql, "source": "SqlEditor", "limit": 100})
        return profile.unpack_response(response)[:2]

    def redact(self, value):
        if isinstance(value, str):
            return value.replace(self._key, "[REDACTED]") if self._key else value
        if isinstance(value, dict):
            return {k: self.redact(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self.redact(v) for v in value]
        return value


def run(client, output, allow_create):
    report = {"status": "RUNNING", "started_at_utc": datetime.now(timezone.utc).isoformat(),
              "registrations_before": {}, "registrations_after": {}, "tables": {}, "created": [], "steps": []}
    def save():
        (output / "validation.json").write_text(json.dumps(client.redact(report), indent=2)+"\n", encoding="utf-8")
    def step(label):
        report["current_step"] = label
        save()
        print(label, flush=True)
    try:
        step("Validate local snapshot and provenance")
        manifest, expected = read_snapshot()
        report.update(snapshot_id=manifest["snapshot_id"], manifest_sha256=sha(SNAPSHOT/"manifest.json"),
                      input_hashes=manifest["inputs"], csv_hashes={k: v["sha256"] for k,v in manifest["tables"].items()},
                      query_sha256=sha(QUERY), script_sha256=sha(Path(__file__)))
        initial_hashes = {str(ROOT/i["path"]): i["sha256"] for i in manifest["inputs"]}
        initial_hashes.update({str(SNAPSHOT/v["filename"]): v["sha256"] for v in manifest["tables"].values()})
        step("List existing registrations in nextwise")
        inventory_names, inventory_rows = client.sql("SHOW LIGHTNING TABLES nextwise")
        require(inventory_names and all(row and type(row[0]) is str for row in inventory_rows),
                "Unexpected installed SHOW LIGHTNING TABLES response")
        inventory = {row[0] for row in inventory_rows}
        report["existing_allowlisted_tables"] = sorted(inventory.intersection(TABLES))
        for name in TABLES:
            step(f"Inspect registration nextwise.{name}")
            registration = client.registration(name) if name in inventory else None
            report["registrations_before"][name] = registration
            save()
            if registration is not None:
                check_registration(name, registration)
            else:
                require(name != "project_profiles", "Existing profile registration is missing; no profile CREATE permitted")
                require(allow_create, f"Missing nextwise.{name}; rerun with --register-missing to authorize CREATE")
        live = {}
        for name in TABLES:
            spec = manifest["tables"][name]
            if report["registrations_before"][name] is None:
                step(f"Register missing nextwise.{name}")
                # Recheck immediately to avoid overwriting a registration created meanwhile.
                _, now = client.sql("SHOW LIGHTNING TABLES nextwise")
                require(name not in {row[0] for row in now}, f"Registration appeared during run: {name}")
                sql = registration_sql(name)
                (output/f"register_{name}.sql").write_text(sql+";\n", encoding="utf-8")
                client.sql(sql)
                report["created"].append(name)
            current = client.registration(name)
            require(current is not None, f"Registration missing after CREATE: {name}")
            check_registration(name, current)
            report["registrations_after"][name] = current
            step(f"Validate every CSV value in nextwise.{name}")
            names, rows = client.sql(f"SELECT * FROM nextwise.{name}")
            live[name], report["tables"][name] = compare_rows(name, spec, expected[name], names, rows)
            type_names, type_rows = client.sql(f"DESC nextwise.{name}")
            require(type_names[:2] == ["col_name", "data_type"], f"{name}: unexpected DESC columns")
            types = {r[0]: r[1] for r in type_rows}
            require(types == {c: "string" for c in spec["columns"]}, f"{name}: unexpected registered types")
            report["tables"][name]["registered_types"] = types
            save()
        step("Validate live IDs, references, approvals and decisions")
        report["references"] = references(live)
        numeric = {}
        for name in ("project_profiles", "evaluation_cases"):
            step(f"Validate SQL numeric conversions for {name}")
            sql = numeric_sql(name, manifest["tables"][name])
            (output/f"numeric_{name}.sql").write_text(sql+";\n", encoding="utf-8")
            names, rows = client.sql(sql)
            numeric[name] = validate_numeric(name, manifest["tables"][name], expected[name], names, rows)
            report["numeric_conversions"] = numeric
            save()
        step("Execute and validate aggregated investigation query in Zetaris")
        sql = QUERY.read_text(encoding="utf-8")
        (output/"investigation.sql").write_text(sql, encoding="utf-8")
        names, rows = client.sql(sql)
        report["query_validation"] = compare_join(expected_join(expected), names, rows)
        results = {"executed_by": "Zetaris SQL API", "query_sha256": sha(QUERY), "columns": names,
                   "rows": [dict(zip(names, row)) for row in rows],
                   "scope": "Publisher claims and pending review linked to synthetic extraction-pilot results only; no source-analysis measurements or production accuracy claim. Pilot totals repeat per source and must not be summed across rows."}
        (output/"query_results.json").write_text(json.dumps(client.redact(results), ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
        step("Verify profile registration and all local artifacts remain unchanged")
        require(client.registration("project_profiles") == report["registrations_before"]["project_profiles"],
                "Profile registration changed during integration")
        require(all(sha(Path(p)) == digest for p,digest in initial_hashes.items()), "Local input/export changed during integration")
        report.update(status="PASS", completed_at_utc=datetime.now(timezone.utc).isoformat(),
                      preservation="PASS: all 8 source artifacts, 6 CSVs, profile registration unchanged; no approvals/decisions changed")
    except (ValueError, KeyError, TypeError, InvalidOperation, OSError) as exc:
        report.update(status="FAIL", failure=str(exc))
        print(client.redact(f"STOP: {exc}"), flush=True)
    finally:
        save()
    print(f"{report['status']}: {output}", flush=True)
    return 0 if report["status"] == "PASS" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--register-missing", action="store_true")
    args = parser.parse_args()
    read_snapshot()  # Fail before requesting credentials if local provenance changed.
    output = ROOT / "reports/zetaris_integration" / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+"-"+uuid.uuid4().hex[:8])
    output.mkdir(parents=True)
    print(f"Sanitized report directory: {output}", flush=True)
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        key = getpass.getpass("Zetaris API key (hidden; one prompt for this integration): ").strip()
    require(bool(key), "Empty API key")
    client = Client(key)
    del key
    try:
        return run(client, output, args.register_missing)
    finally:
        client._key = None


if __name__ == "__main__":
    raise SystemExit(main())
