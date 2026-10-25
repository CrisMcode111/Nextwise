"""Offline, allowlisted CSV snapshot of existing Nextwise artifacts (stdlib only)."""
import csv
import hashlib
import io
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN_ID = "20261024T151413Z-fdf0c15b"
RUN = f"data/evaluations/{RUN_ID}"
INPUTS = {
    "profile": "data/project_profile.json",
    "investigation": "data/investigation.json",
    "sources": "data/sources.json",
    "draft": "data/evidence_draft.json",
    "review": "data/evidence_review.json",
    "use_case": "data/use_case.json",
    "results": f"{RUN}/results.json",
    "recommendation": f"{RUN}/recommendation.json",
}
KEYS = {
    "project_profiles": ("project_id",),
    "investigations": ("investigation_id",),
    "sources": ("investigation_id", "source_id"),
    "evidence_claims": ("draft_sha256", "claim_pointer"),
    "evidence_reviews": ("investigation_id", "artifact_sha256"),
    "evaluation_cases": ("investigation_id", "run_id", "fixture_id"),
}
COUNTS = dict(zip(KEYS, (1, 1, 3, 6, 1, 4)))
INTS = {"team_size", "http_status", "schema_valid", "quality_pass",
        "prompt_tokens", "completion_tokens", "total_tokens"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def load_inputs(root):
    raw = {name: (root / path).read_bytes() for name, path in INPUTS.items()}
    return ({name: json.loads(value) for name, value in raw.items()},
            {INPUTS[name]: sha(value) for name, value in raw.items()})


def validate_inputs(d, hashes):
    p, i, s, draft, review, use, result, rec = (d[k] for k in INPUTS)

    def reference(ref):
        require(ref["path"] in hashes, f"Reference outside input allowlist: {ref['path']}")
        require(hashes[ref["path"]] == ref["sha256"], f"Hash mismatch: {ref['path']}")

    for doc in (s, draft, review, use, result, rec):
        require(doc["investigation_id"] == i["id"], "Investigation reference mismatch")
    for doc in (i, review, use):
        require(doc["project_id"] == p["id"], "Project reference mismatch")
    for doc in (i, draft, review, use, result, rec):
        require("decision" in doc and doc["decision"] is None, "Decision must remain null")
    for doc in (review, result, rec):
        require(doc["approval"]["status"] == "pending_user_approval", "Approval changed")
    require(review["approved_project_context"] == p, "Approved profile mismatch")
    reference(review["reviewed_draft"])
    require(review["reviewed_draft"]["path"] == INPUTS["draft"], "Wrong reviewed draft")
    for ref in review["local_input_references"] + use["provenance"]["artifact_references"]:
        reference(ref)
    for doc in (result, rec):
        require({ref["path"] for ref in doc["evidence_references"]} ==
                {INPUTS["draft"], INPUTS["review"]}, "Missing evidence references")
        for ref in doc["evidence_references"]:
            reference(ref)
    reference(result["use_case_reference"])
    require(result["use_case_reference"]["path"] == INPUTS["use_case"], "Wrong use case")
    reference(rec["evaluation_reference"])
    require(rec["evaluation_reference"]["path"] == INPUTS["results"], "Wrong recommendation run")
    require(result["run_id"] == RUN_ID and result["status"] == "completed_pilot", "Wrong/incomplete pilot")
    require(not result["unattempted_fixture_ids"], "Unattempted fixtures")
    source_ids = [v["id"] for v in s["sources"]]
    require(len(set(source_ids)) == len(source_ids), "Duplicate source ID")
    for claim in draft["accepted"]:
        require(claim["source_id"] in source_ids, "Unregistered claim source")
        require(claim["claim_kind"] == "publisher_claim", "Unexpected claim kind")
    require(len(review["claim_reviews"]) == len(draft["accepted"]), "Review count mismatch")
    for index, cr in enumerate(review["claim_reviews"]):
        claim = draft["accepted"][index]
        require(cr["draft_pointer"] == f"/accepted/{index}", "Review pointer mismatch")
        require(cr["original_claim"] == claim["claim"] and cr["source_id"] == claim["source_id"],
                "Review claim mismatch")
        require(cr["quote_reference"]["sha256_utf8"] == sha(claim["exact_supporting_quote"].encode("utf-8")),
                "Quote hash mismatch")
    fixtures = result["fixtures"]
    fixture_ids = [f["id"] for f in fixtures]
    require(len(set(fixture_ids)) == len(fixture_ids), "Duplicate fixture ID")
    examples = {f["id"]: f for f in use["proposed_evaluation_examples"]["examples"]}
    for f in fixtures:
        require(f["snapshot"]["id"] == f["id"] and examples.get(f["id"]) == f["snapshot"],
                "Fixture snapshot mismatch")
        require(sha(canonical(f["snapshot"])) == f["sha256"], "Fixture hash mismatch")
        require(sha(f["snapshot"]["input"].encode("utf-8")) == f["input_sha256"], "Fixture input hash mismatch")
    require(sorted(c["fixture_id"] for c in result["cases"]) == sorted(fixture_ids), "Case/fixture mismatch")
    for c in result["cases"]:
        f = next(f for f in fixtures if f["id"] == c["fixture_id"])
        require(c["fixture_sha256"] == f["sha256"], "Case fixture hash mismatch")


def project(d, hashes):
    p, i, s, draft, review, use, result, rec = (d[k] for k in INPUTS)

    def row(name, original, **values):
        return dict(values, artifact_path=INPUTS[name], artifact_sha256=hashes[INPUTS[name]],
                    record_json=encode(original))

    tables = {
        "project_profiles": [row("profile", p, project_id=p["id"], project_name=p["name"],
            **{k: p[k] for k in ("stage", "objective", "team_size")}, constraints_json=encode(p["constraints"]))],
        "investigations": [row("investigation", i, investigation_id=i["id"], project_id=i["project_id"],
            question=i["question"], status=i["status"], decision_json=encode(i["decision"]))],
        "sources": [row("sources", v, investigation_id=s["investigation_id"], source_id=v["id"],
            **{k: v[k] for k in ("title", "requested_url", "final_url", "retrieved_at_utc")},
            publication_date_json=encode(v["publication_date"])) for v in s["sources"]],
        "evidence_claims": [row("draft", v, investigation_id=draft["investigation_id"],
            draft_sha256=hashes[INPUTS["draft"]], claim_pointer=f"/accepted/{index}",
            **{k: v[k] for k in ("source_id", "claim", "exact_supporting_quote", "claim_kind",
                                "relevance_to_criterion", "limitations")},
            draft_status=draft["status"], created_at_utc=draft["created_at_utc"])
            for index, v in enumerate(draft["accepted"])],
        "evidence_reviews": [row("review", review, investigation_id=review["investigation_id"],
            project_id=review["project_id"], review_status=review["status"],
            reviewed_draft_sha256=review["reviewed_draft"]["sha256"], approval_status=review["approval"]["status"],
            decision_json=encode(review["decision"]), readiness_status=review["readiness"]["status"],
            gaps_json=encode(review["unresolved_evidence_gaps"]), claim_reviews_json=encode(review["claim_reviews"]))],
        "evaluation_cases": [],
    }
    for c in result["cases"]:
        usage = c["token_usage"]
        tables["evaluation_cases"].append(row("results", c,
            investigation_id=result["investigation_id"], run_id=result["run_id"],
            evaluation_status=result["status"], draft_sha256=hashes[INPUTS["draft"]],
            use_case_sha256=result["use_case_reference"]["sha256"],
            **{k: c[k] for k in ("fixture_id", "fixture_sha256", "actual_model", "http_status", "duration_seconds")},
            schema_valid=int(c["validation"]["well_formed"]), quality_pass=int(c["validation"]["quality_pass"]),
            **{k: usage[k] if usage is not None else None for k in ("prompt_tokens", "completion_tokens", "total_tokens")},
            duration_seconds_json=encode(c["duration_seconds"]), token_usage_json=encode(usage),
            output=c["output"], output_json=encode(c["output"]), validation_json=encode(c["validation"]),
            approval_json=encode(result["approval"]), decision_json=encode(result["decision"]),
            monetary_cost_json=encode(result["monetary_cost"]), verified_prices_json=encode(result["verified_prices"]),
            created_at_utc=result["created_at_utc"], scoring_protocol=result["scoring_protocol"],
            recommendation_artifact_path=INPUTS["recommendation"],
            recommendation_artifact_sha256=hashes[INPUTS["recommendation"]], recommendation_json=encode(rec)))
    return tables


def column_type(name):
    return "BIGINT" if name in INTS else "DOUBLE" if name == "duration_seconds" else "STRING"


def csv_bytes(rows):
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]), lineterminator="\r\n")
    writer.writeheader()
    encoded = []
    for row in rows:
        converted = {}
        for name, value in row.items():
            kind = column_type(name)
            if kind == "BIGINT":
                require(value is None or type(value) is int, f"Invalid integer: {name}")
            elif kind == "DOUBLE":
                require(value is None or (type(value) in (int, float) and math.isfinite(value)), f"Invalid number: {name}")
            else:
                require(isinstance(value, str), f"Missing/non-string value: {name}")
            converted[name] = "\\N" if value is None else str(value)
            if name.endswith("_json"):
                require(encode(json.loads(converted[name])) == converted[name], f"Invalid JSON: {name}")
        writer.writerow(converted)
        encoded.append(converted)
    require(list(csv.DictReader(io.StringIO(buffer.getvalue(), newline=""), strict=True)) == encoded,
            "CSV round trip changed values")
    return buffer.getvalue().encode("utf-8")


def build(root=ROOT):
    d, hashes = load_inputs(root)
    validate_inputs(d, hashes)
    tables = project(d, hashes)
    outputs = {}
    metadata = {}
    for name, rows in tables.items():
        require(len(rows) == COUNTS[name], f"Wrong row count: {name}")
        keys = [tuple(row[k] for k in KEYS[name]) for row in rows]
        require(len(set(keys)) == len(keys), f"Duplicate key: {name}")
        payload = csv_bytes(rows)
        outputs[f"{name}.csv"] = payload
        metadata[name] = {"filename": f"{name}.csv", "sha256": sha(payload), "row_count": len(rows),
            "primary_key": KEYS[name], "columns": {c: column_type(c) for c in rows[0]}}
    # Exercise delimiter, literal backslash, Unicode, empty text, CRLF and embedded quotes/newlines.
    csv_bytes([{"probe": 'comma, "quote"\r\nsecond line\nUnicode: é; literal \\N', "empty": ""}])
    exporter_hash = sha(Path(__file__).read_bytes())
    snapshot = f"{RUN_ID}-csv-{sha(canonical({'inputs': hashes, 'exporter': exporter_hash}))[:12]}"
    manifest = {"format_version": 1, "snapshot_id": snapshot, "evaluation_run_id": RUN_ID,
        "exporter": {"path": "scripts/export_zetaris.py", "sha256": exporter_hash},
        "inputs": [{"path": path, "sha256": digest} for path, digest in hashes.items()],
        "csv": {"encoding": "UTF-8 (no BOM)", "header": True, "delimiter": ",",
                "quotechar": '"', "doublequote": True, "line_terminator": "CRLF",
                "json_null": "null", "numeric_null": "\\N", "multiline": True},
        "tables": metadata,
        "validation": {"input_hashes_and_references": "passed", "fixture_snapshots": "passed",
                       "row_counts_and_unique_keys": "passed", "csv_and_json_round_trip": "passed",
                       "quotes_multiline_unicode_probe": "passed", "input_files_unchanged": "passed"}}
    require(load_inputs(root)[1] == hashes, "Inputs changed during export")
    outputs["manifest.json"] = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    return snapshot, outputs


def main():
    snapshot, outputs = build()
    target = ROOT / "data" / "zetaris_exports" / snapshot
    if target.exists():
        require({p.name for p in target.iterdir()} == set(outputs), "Existing snapshot contents differ")
        for name, payload in outputs.items():
            require((target / name).read_bytes() == payload, f"Existing snapshot differs: {name}")
    else:
        target.mkdir(parents=True)
        for name, payload in outputs.items():
            with (target / name).open("xb") as stream:
                stream.write(payload)
            require((target / name).read_bytes() == payload, f"Disk verification failed: {name}")
    print(f"Validated snapshot: {target}")
    for name, count in COUNTS.items():
        print(f"{name}.csv: {count} rows")


if __name__ == "__main__":
    main()
