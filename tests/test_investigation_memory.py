"""Cross-process H-MEM persistence, provenance, lifecycle and locking checks."""

import base64
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "investigation_memory.py"
BRIDGE = ROOT / "scripts" / "hmem_bridge.ts"
ARTIFACT_PATHS = {
    "project_profile": "data/project_profile.json", "investigation": "data/investigation.json",
    "sources": "data/sources.json", "evidence_draft": "data/evidence_draft.json",
    "evidence_review": "data/evidence_review.json",
}
PROTECTED = list(ARTIFACT_PATHS.values()) + ["scripts/analyze_sources.py"]


def artifact(kind, raw):
    return {"kind": kind, "path": ARTIFACT_PATHS[kind],
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes_base64": base64.b64encode(raw).decode("ascii")}


class InvestigationMemoryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.memory_root = Path(self.directory.name) / "memory"
        self.protected = {p: (ROOT / p).read_bytes() for p in PROTECTED}
        self.documents = {kind: json.loads((ROOT / p).read_text(encoding="utf-8"))
                          for kind, p in ARTIFACT_PATHS.items()}
        self.investigation_id = self.documents["investigation"]["id"]

    def tearDown(self):
        for p, raw in self.protected.items():
            self.assertEqual((ROOT / p).read_bytes(), raw, p)

    def cli(self, operation, investigation_id=None, expect=0):
        command = [sys.executable, str(CLI), operation, "--memory-root", str(self.memory_root), "--json"]
        if investigation_id is not None:
            command.extend(["--investigation-id", investigation_id])
        completed = subprocess.run(command, capture_output=True, encoding="utf-8", cwd=ROOT, timeout=60)
        self.assertEqual(completed.returncode, expect, completed.stdout + completed.stderr)
        return json.loads(completed.stdout)

    def direct_import(self, investigation_id, artifacts, expect=0):
        request = {"operation": "import", "investigation_id": investigation_id,
                   "memory_root": str(self.memory_root), "artifacts": artifacts}
        completed = subprocess.run(
            [shutil.which("node"), "--experimental-transform-types", str(BRIDGE)],
            input=json.dumps(request), capture_output=True, encoding="utf-8", cwd=ROOT, timeout=60,
        )
        self.assertEqual(completed.returncode, expect, completed.stdout + completed.stderr)
        return json.loads(completed.stdout)

    def synthetic_artifacts(self, investigation_id):
        docs = copy.deepcopy(self.documents)
        docs["investigation"]["id"] = investigation_id
        for kind in ["sources", "evidence_draft", "evidence_review"]:
            docs[kind]["investigation_id"] = investigation_id
        artifacts = []
        for kind in ARTIFACT_PATHS:
            if kind == "evidence_review":
                hashes = {a["path"]: a["sha256"] for a in artifacts}
                docs[kind]["reviewed_draft"]["sha256"] = hashes[ARTIFACT_PATHS["evidence_draft"]]
                for ref in docs[kind]["local_input_references"]:
                    ref["sha256"] = hashes[ref["path"]]
            raw = (json.dumps(docs[kind], ensure_ascii=False, indent=2) + "\n").encode("utf-8")
            artifacts.append(artifact(kind, raw))
        return artifacts

    def state(self, investigation_id=None):
        return self.memory_root / (investigation_id or self.investigation_id) / "state.json"

    def test_round_trip_separate_processes_isolation_and_pending_review(self):
        imported = self.cli("import")
        repeated = self.cli("import")
        self.assertFalse(imported["reused"])
        self.assertTrue(repeated["reused"])
        self.assertEqual(imported["manifest_id"], repeated["manifest_id"])
        self.assertEqual(imported["artifact_ids"], repeated["artifact_ids"])
        other_id = "isolation-fixture"
        self.direct_import(other_id, self.synthetic_artifacts(other_id))
        resumed = self.cli("resume")
        other = self.cli("resume", other_id)
        self.assertEqual(resumed["investigation_id"], self.investigation_id)
        self.assertEqual(other["investigation_id"], other_id)
        self.assertEqual(other["artifacts"]["investigation"]["id"], other_id)
        self.assertNotEqual(resumed["artifact_hashes"]["investigation"], other["artifact_hashes"]["investigation"])
        self.assertTrue(resumed["local_artifacts"]["snapshot_matches_current_files"])
        self.assertFalse(other["local_artifacts"]["snapshot_matches_current_files"])
        self.assertIsNone(resumed["decision"])
        self.assertEqual(resumed["approval"], self.documents["evidence_review"]["approval"])
        self.assertEqual(resumed["approval"]["status"], "pending_user_approval")
        self.assertEqual(resumed["artifacts"], self.documents)
        self.assertEqual(resumed["unresolved_questions"], self.documents["investigation"]["open_questions"])
        self.assertEqual(resumed["unresolved_evidence_gaps"], self.documents["evidence_review"]["unresolved_evidence_gaps"])
        self.assertEqual(resumed["analysis_observation"]["duration_seconds"], 30.152)
        self.assertEqual(resumed["evidence"]["claim_kind_counts"], {"publisher_claim": 6})
        self.assertEqual(resumed["review_to_draft"]["reviewed_draft_sha256"], imported["artifact_hashes"]["evidence_draft"])
        state = json.loads(self.state().read_text(encoding="utf-8"))
        self.assertEqual(len(state["records"]), 6)
        by_id = {r["id"]: r for r in state["records"]}
        for kind, memory_id in imported["artifact_ids"].items():
            memory = by_id[memory_id]
            envelope = json.loads(memory["content"])
            raw = base64.b64decode(envelope["bytes_base64"])
            self.assertEqual(raw, self.protected[ARTIFACT_PATHS[kind]])
            self.assertEqual(hashlib.sha256(raw).hexdigest(), imported["artifact_hashes"][kind])
            self.assertEqual(memory["layer"], "working")
            self.assertEqual(memory["provenance"]["origin"], "document")
        self.assertIn(imported["artifact_ids"]["evidence_draft"], by_id[imported["artifact_ids"]["evidence_review"]]["derivedFrom"])
        ledger = [json.loads(line) for line in (self.state().parent / "ledger.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(sum(e["action"] == "create" for e in ledger), 6)
        self.assertEqual(sum(e["action"] == "read" for e in ledger), 18)
        self.assertEqual({e["action"] for e in ledger}, {"create", "read"})
        self.assertFalse((self.state().parent / "nextwise.lock").exists())

    def test_concurrent_operation_is_refused_without_removing_owner_lock(self):
        self.cli("import")
        lock = self.state().parent / "nextwise.lock"
        code = (
            "import fs from 'node:fs'; const p=process.argv[1]; const fd=fs.openSync(p,'wx');"
            "fs.writeFileSync(fd,'test lock owner'); console.log('READY');"
            "process.stdin.once('data',()=>{fs.closeSync(fd);fs.unlinkSync(p);process.exit(0)});"
        )
        owner = subprocess.Popen([shutil.which("node"), "--input-type=module", "-e", code, str(lock)],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertEqual(owner.stdout.readline().strip(), "READY")
            result = self.cli("resume", expect=1)
            self.assertEqual(result["error"]["code"], "memory_locked")
            self.assertEqual(lock.read_text(encoding="utf-8"), "test lock owner")
        finally:
            owner.communicate("release\n", timeout=10)
        self.assertTrue(self.cli("resume")["ok"])

    def test_corrupt_artifact_fails_integrity_check(self):
        imported = self.cli("import")
        state = json.loads(self.state().read_text(encoding="utf-8"))
        record = next(r for r in state["records"] if r["id"] == imported["artifact_ids"]["evidence_draft"])
        envelope = json.loads(record["content"])
        envelope["bytes_base64"] = base64.b64encode(base64.b64decode(envelope["bytes_base64"]) + b" ").decode()
        record["content"] = json.dumps(envelope)
        self.state().write_text(json.dumps(state), encoding="utf-8")
        result = self.cli("resume", expect=1)
        self.assertEqual(result["error"]["code"], "integrity_error")
        self.assertFalse((self.state().parent / "nextwise.lock").exists())

    def test_missing_recorded_id_is_not_replaced_by_similar_memory(self):
        imported = self.cli("import")
        state = json.loads(self.state().read_text(encoding="utf-8"))
        state["records"] = [r for r in state["records"] if r["id"] != imported["artifact_ids"]["evidence_draft"]]
        self.state().write_text(json.dumps(state), encoding="utf-8")
        self.assertEqual(self.cli("resume", expect=1)["error"]["code"], "missing_memory")

    def test_bad_review_reference_is_rejected_before_creating_state(self):
        fixtures = self.synthetic_artifacts(self.investigation_id)
        index = next(i for i, a in enumerate(fixtures) if a["kind"] == "evidence_review")
        review = json.loads(base64.b64decode(fixtures[index]["bytes_base64"]))
        review["reviewed_draft"]["sha256"] = "0" * 64
        fixtures[index] = artifact("evidence_review", json.dumps(review).encode())
        result = self.direct_import(self.investigation_id, fixtures, expect=1)
        self.assertEqual(result["error"]["code"], "review_draft_mismatch")
        self.assertFalse(self.state().exists())

    def test_import_cannot_approve_review_or_create_a_decision(self):
        for field in ["approval", "decision"]:
            with self.subTest(field=field):
                fixtures = self.synthetic_artifacts(self.investigation_id)
                index = next(i for i, a in enumerate(fixtures) if a["kind"] == "evidence_review")
                review = json.loads(base64.b64decode(fixtures[index]["bytes_base64"]))
                if field == "approval":
                    review["approval"]["status"] = "approved"
                else:
                    review["decision"] = "adopt"
                fixtures[index] = artifact("evidence_review", json.dumps(review).encode())
                result = self.direct_import(self.investigation_id, fixtures, expect=1)
                self.assertEqual(result["error"]["code"], "unsupported_lifecycle")
                self.assertFalse(self.state().exists())

    def test_unknown_investigation_and_path_traversal_do_not_read_other_stores(self):
        self.cli("import")
        self.assertEqual(self.cli("resume", "not-imported", expect=1)["error"]["code"], "not_imported")
        self.assertFalse((self.memory_root / "not-imported").exists())
        self.assertEqual(self.cli("resume", "../outside", expect=1)["error"]["code"], "invalid_request")

    def test_vendored_files_match_recorded_official_bytes(self):
        manifest = json.loads((ROOT / "vendor/meterless/upstream.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["commit"], "1742dec56a66e58eef9dda2d2b865823758ca8cd")
        self.assertEqual(manifest["adaptations"], [])
        for item in manifest["files"]:
            self.assertEqual(hashlib.sha256((ROOT / item["local_path"]).read_bytes()).hexdigest(), item["sha256"], item["local_path"])


if __name__ == "__main__":
    unittest.main()
