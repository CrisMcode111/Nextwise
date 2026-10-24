#!/usr/bin/env python3
"""Import and resume saved Nextwise investigations through official H-MEM."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "scripts" / "hmem_bridge.ts"
DEFAULT_MEMORY_ROOT = ROOT / "data" / "memory" / "hmem"
ARTIFACT_PATHS = {
    "project_profile": "data/project_profile.json",
    "investigation": "data/investigation.json",
    "sources": "data/sources.json",
    "evidence_draft": "data/evidence_draft.json",
    "evidence_review": "data/evidence_review.json",
}


def import_artifacts() -> list[dict[str, str]]:
    """Read only the five explicit approved Nextwise files, preserving bytes."""
    artifacts = []
    for kind, relative in ARTIFACT_PATHS.items():
        raw = (ROOT / relative).read_bytes()
        artifacts.append({
            "kind": kind, "path": relative,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes_base64": base64.b64encode(raw).decode("ascii"),
        })
    return artifacts


def call_bridge(request: dict) -> dict:
    node = shutil.which("node")
    if node is None:
        raise RuntimeError("Node.js with experimental TypeScript transformation is required; nothing was installed.")
    completed = subprocess.run(
        [node, "--experimental-transform-types", str(BRIDGE)],
        input=json.dumps(request), capture_output=True, encoding="utf-8", cwd=ROOT,
        timeout=60, check=False,
    )
    try:
        result = json.loads(completed.stdout)
    except (ValueError, TypeError):
        # Do not dump stderr, source text, stack traces or the request payload.
        raise RuntimeError("H-MEM bridge did not return JSON; check Node.js compatibility and vendored files.") from None
    if not isinstance(result, dict) or (completed.returncode and result.get("ok")):
        raise RuntimeError("H-MEM bridge returned an inconsistent result.")
    return result


def local_artifact_comparison(hashes: dict[str, str]) -> dict:
    changed = []
    for kind, relative in ARTIFACT_PATHS.items():
        path = ROOT / relative
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != hashes[kind]:
            changed.append(relative)
    return {"snapshot_matches_current_files": not changed, "changed_or_missing_files": changed}


def display(result: dict, operation: str) -> None:
    if operation == "import":
        print("Existing H-MEM snapshot reused." if result["reused"] else "Investigation imported into official H-MEM.")
        print(f"Investigation: {result['investigation_id']}")
        print(f"Manifest memory ID: {result['manifest_id']}")
        for kind, memory_id in result["artifact_ids"].items():
            print(f"  {kind}: {memory_id} | SHA-256 {result['artifact_hashes'][kind]}")
        print("Review approval remains pending. Decision remains null.")
        return
    print(f"Investigation: {result['investigation_id']}")
    print(f"Question: {result['question']}")
    print(f"Evidence: {result['evidence']['status']} | accepted entries: {result['evidence']['accepted_count']}")
    print("Claim kinds: " + json.dumps(result["evidence"]["claim_kind_counts"]))
    print(f"AI-assisted review: {result['review']['status']}")
    print(f"User approval: {result['approval']['status']}")
    print("Decision: null")
    print("Artifact hashes and review-to-draft relationship: verified against the imported snapshot.")
    if not result["local_artifacts"]["snapshot_matches_current_files"]:
        print("Current local files differ from this snapshot; import a new consistent version before treating it as current.")
    observation = result["analysis_observation"]
    print(f"Nextwise analysis observation only: {observation['duration_seconds']} seconds; tokens {json.dumps(observation['token_usage'])}")
    print("These observations do not measure the reference project's extraction performance.")
    print("Unresolved investigation questions:")
    for question in result["unresolved_questions"]:
        print(f"  - {question}")
    print("Recorded unknowns:")
    for unknown in result["unknowns"]:
        print(f"  - {unknown}")
    print("Evidence gaps and proposed evaluation steps (not executed):")
    for gap in result["unresolved_evidence_gaps"]:
        print(f"  {gap['gap_id']}: {gap['unknown']}")
        print(f"    Next action: {gap['concrete_next_action']}")
    print(f"Recommendation readiness: {result['readiness']['status']}")
    print("Memory retrieval is not independent verification, user approval or a decision.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["import", "resume"])
    parser.add_argument("--investigation-id", help="Defaults to the investigation in data/investigation.json")
    parser.add_argument("--memory-root", type=Path, default=DEFAULT_MEMORY_ROOT,
                        help="Isolated H-MEM persistence root; defaults to data/memory/hmem")
    parser.add_argument("--json", action="store_true", help="Emit structured results, including retrieved artifacts")
    args = parser.parse_args()
    try:
        investigation_id = args.investigation_id
        if not investigation_id:
            investigation_id = json.loads((ROOT / ARTIFACT_PATHS["investigation"]).read_text(encoding="utf-8"))["id"]
        request = {"operation": args.operation, "investigation_id": investigation_id,
                   "memory_root": str(args.memory_root.resolve())}
        if args.operation == "import":
            request["artifacts"] = import_artifacts()
        result = call_bridge(request)
        if result.get("ok") and args.operation == "resume":
            result["local_artifacts"] = local_artifact_comparison(result["artifact_hashes"])
        if args.json:
            print(json.dumps(result, ensure_ascii=True, indent=2))
        elif result.get("ok"):
            display(result, args.operation)
        else:
            print(f"H-MEM {result['error']['code']}: {result['error']['message']}", file=sys.stderr)
        return 0 if result.get("ok") else 1
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.TimeoutExpired) as error:
        # Operational failures stay concise and do not expose artifact content.
        message = str(error) if isinstance(error, RuntimeError) else "Check approved input files, Node.js and H-MEM persistence; the operation did not complete."
        result = {"ok": False, "error": {"code": "local_operation_failed", "message": message}}
        if args.json:
            print(json.dumps(result))
        else:
            print(f"H-MEM: {message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
