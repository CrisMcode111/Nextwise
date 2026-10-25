/** App-owned human decision records. No changes to the official H-MEM reference. */
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { HMEM } from "../vendor/meterless/hmem/reference/src/index.ts";

const SCHEMA = "nextwise.human-decision.v1";
const SOURCE = "nextwise:human-decision";
const hash = (v: string | Buffer) => crypto.createHash("sha256").update(v).digest("hex");
function canonical(v: any): string {
  return JSON.stringify(Array.isArray(v) ? v.map(sort) : sort(v));
}
function sort(v: any): any {
  return Array.isArray(v) ? v.map(sort) : v && typeof v === "object" ?
    Object.fromEntries(Object.keys(v).sort().map(k => [k, sort(v[k])])) : v;
}
export class DecisionError extends Error {
  constructor(public code: string, message: string) { super(message); }
}
function check(v: any, code: string, text: string): asserts v { if (!v) throw new DecisionError(code, text); }
function records(hmem: HMEM, investigation: string): any[] {
  const found = hmem.store.all().filter(r => r.source === SOURCE && r.chatId === investigation).map(memory => {
    let envelope: any;
    try { envelope = JSON.parse(memory.content); } catch { throw new DecisionError("decision_integrity", "Decision storage is damaged; no decision was replaced."); }
    const d = envelope.decision;
    check(envelope.schema === "nextwise.human-decision-envelope.v1" && d?.schema === SCHEMA &&
      envelope.sha256 === hash(canonical(d)) && d.investigation_id === investigation &&
      ["Adopt", "Test", "Defer", "Reject"].includes(d.choice) && typeof d.rationale === "string" && d.rationale.trim() &&
      /^[0-9a-f-]{36}$/.test(d.decision_id) && Number.isInteger(d.version) && d.version > 0 &&
      !Number.isNaN(Date.parse(d.created_at_utc)) && Array.isArray(d.evidence_references) &&
      memory.provenance?.origin === "manual" && memory.provenance.refs?.includes(`sha256:${envelope.sha256}`) &&
      d.evidence_references.every((ref: any) => memory.derivedFrom?.includes(ref.memory_id)),
      "decision_integrity", "A saved decision failed its identity or content checks; manual recovery is required.");
    return { ...d, memory_id: memory.id, record_sha256: envelope.sha256 };
  }).sort((a, b) => a.version - b.version);
  for (let n = 0; n < found.length; n++) {
    const d = found[n], previous = found[n - 1];
    check(d.version === n + 1 && d.previous_decision_id === (previous?.decision_id ?? null) &&
      d.previous_record_sha256 === (previous?.record_sha256 ?? null) &&
      d.series_id === (previous?.series_id ?? d.decision_id) &&
      (!previous || d.project_id === previous.project_id), "decision_integrity", "Decision history has a missing, duplicate or mismatched version.");
  }
  return found;
}
function verifyReference(hmem: HMEM, ref: any, investigation: string): any {
  const memory = hmem.store.get(ref.memory_id);
  check(memory && memory.chatId === investigation, "missing_evidence", "A saved evidence memory is missing or belongs to another investigation.");
  let envelope: any;
  try { envelope = JSON.parse(memory.content); } catch { throw new DecisionError("evidence_mismatch", "A saved evidence envelope is damaged."); }
  const raw = Buffer.from(envelope.bytes_base64 ?? "", "base64");
  check(envelope.schema === "nextwise.hmem.artifact.v1" && envelope.investigation_id === investigation &&
    envelope.kind === ref.kind && envelope.path === ref.path && envelope.sha256 === ref.sha256 &&
    raw.toString("base64") === envelope.bytes_base64 && hash(raw) === ref.sha256,
    "evidence_mismatch", "Saved evidence bytes do not match the decision's recorded hash.");
  return JSON.parse(raw.toString("utf8"));
}
export function decisionHistory(hmem: HMEM, investigation: string, resume: () => any) {
  const all = records(hmem, investigation);
  let current: any = null;
  try { current = resume(); } catch { /* History must stay readable when current evidence is unavailable. */ }
  return { history: all.map(d => {
    const issues: string[] = [];
    for (const ref of d.evidence_references) {
      try { verifyReference(hmem, ref, investigation); } catch { issues.push(`${ref.kind}: saved evidence is missing or mismatched`); }
      if (!current || current.artifact_hashes[ref.kind] !== ref.sha256 || current.artifact_ids[ref.kind] !== ref.memory_id)
        issues.push(`${ref.kind}: current evidence differs or cannot be checked`);
      // Compare only the exact allowlisted original artifact paths from the validated manifest.
      if (current?.artifact_paths[ref.kind] === ref.path) {
        try {
          const root = path.resolve(import.meta.dirname, "..");
          const target = path.resolve(root, ref.path);
          check(target.startsWith(root + path.sep), "evidence_mismatch", "Invalid evidence path.");
          if (hash(fs.readFileSync(target)) !== ref.sha256) issues.push(`${ref.kind}: current original artifact differs`);
        } catch { issues.push(`${ref.kind}: current original artifact unavailable`); }
      }
    }
    const manifest = hmem.store.get(d.manifest_id);
    if (!manifest || hash(manifest.content) !== d.manifest_sha256) issues.push("The referenced evidence manifest is missing or changed");
    return { ...d, needs_review: issues.length > 0, integrity_issues: issues };
  }), current_manifest_id: current?.manifest_id ?? null };
}
export function decisionEvidence(hmem: HMEM, investigation: string, id: string, kind: string) {
  const d = records(hmem, investigation).find(r => r.decision_id === id);
  check(d, "decision_missing", "This decision record was not found.");
  const ref = d.evidence_references.find((r: any) => r.kind === kind);
  check(ref, "missing_evidence", "This evidence reference was not found.");
  return { decision_id: id, reference: ref, artifact: verifyReference(hmem, ref, investigation) };
}
export function saveDecision(hmem: HMEM, investigation: string, request: any, resume: () => any, directory: string) {
  const input = request.decision;
  check(input && input.explicit_action === "record_human_decision" && ["Adopt", "Test", "Defer", "Reject"].includes(input.choice) &&
    typeof input.rationale === "string" && input.rationale.trim().length > 0 && input.rationale.length <= 8000 &&
    (input.next_action === null || typeof input.next_action === "string" && input.next_action.length <= 4000) &&
    typeof input.request_id === "string" && /^[0-9a-f]{8}-[0-9a-f-]{27}$/i.test(input.request_id) &&
    Object.hasOwn(input, "expected_head"), "invalid_decision", "Choose Adopt, Test, Defer or Reject, and write a rationale before explicitly saving.");
  const fingerprint = hash(canonical(input));
  const existing = records(hmem, investigation);
  const repeated = existing.find(d => d.request_id === input.request_id);
  if (repeated) {
    check(repeated.request_sha256 === fingerprint, "idempotency_conflict", "This retry ID belongs to different text. Refresh history before retrying.");
    return { reused: true, ...decisionHistory(hmem, investigation, resume) };
  }
  const head = existing.at(-1);
  check(input.expected_head === (head?.decision_id ?? null), "decision_conflict", "A newer decision exists. Review history before saving an amendment.");
  const snapshot = resume();
  check(snapshot.evaluation_results?.status === "completed_pilot" && snapshot.manifest_id === input.context?.manifest_id &&
    snapshot.evaluation_results.run_id === input.context?.run_id &&
    canonical(snapshot.artifact_hashes) === canonical(input.context?.artifact_hashes),
    "evidence_changed", "The evidence changed or is incomplete. Reload the investigation and review it before saving.");
  const refs = Object.keys(snapshot.artifact_ids).map(kind => ({ kind, memory_id: snapshot.artifact_ids[kind],
    path: snapshot.artifact_paths[kind], sha256: snapshot.artifact_hashes[kind] }));
  check(refs.some(r => r.kind === "evidence_draft") && refs.some(r => r.kind === "evidence_review") &&
    refs.some(r => r.kind === "evaluation_results"), "missing_evidence", "The draft, review and pilot must be present.");
  refs.forEach(ref => verifyReference(hmem, ref, investigation));
  for (const ref of refs) {
    const root = path.resolve(import.meta.dirname, "..");
    const target = path.resolve(root, ref.path);
    check(target.startsWith(root + path.sep) && fs.existsSync(target) && hash(fs.readFileSync(target)) === ref.sha256,
      "evidence_changed", "An original artifact is missing or differs from the evidence being viewed. Review it before saving.");
  }
  // Identical repeated choices/text/context are not new amendments, even with a new retry ID.
  if (head && head.choice === input.choice && head.rationale === input.rationale && head.next_action === input.next_action &&
      canonical(head.evidence_references) === canonical(refs)) return { reused: true, ...decisionHistory(hmem, investigation, resume) };
  const id = crypto.randomUUID();
  const record = { schema: SCHEMA, decision_id: id, series_id: head?.series_id ?? id, version: existing.length + 1,
    created_at_utc: new Date().toISOString(), project_id: snapshot.artifacts.project_profile.id, investigation_id: investigation,
    run_id: snapshot.evaluation_results.run_id, choice: input.choice, rationale: input.rationale, next_action: input.next_action,
    actor: "local_human_user", request_id: input.request_id, request_sha256: fingerprint,
    previous_decision_id: head?.decision_id ?? null, previous_record_sha256: head?.record_sha256 ?? null,
    manifest_id: snapshot.manifest_id, manifest_sha256: hash(hmem.store.get(snapshot.manifest_id)!.content),
    evidence_references: refs,
    boundary: "Records a human choice only. Does not approve evidence, verify claims, or authorize models, experiments or deployment." };
  const digest = hash(canonical(record));
  hmem.add({ content: JSON.stringify({ schema: "nextwise.human-decision-envelope.v1", decision: record, sha256: digest }),
    type: "general", layer: "working", source: SOURCE, chatId: investigation, missionId: investigation,
    tags: ["project:nextwise", "human-decision", `decision:${id}`],
    provenance: { origin: "manual", learnedAt: Date.now(), label: "Explicit human decision; no evidence approval or execution authorization",
      refs: [snapshot.manifest_id, ...refs.map(r => r.memory_id), `sha256:${digest}`] },
    derivedFrom: [snapshot.manifest_id, ...refs.map(r => r.memory_id), ...(head ? [head.memory_id] : [])],
    ...(head ? { supersedes: head.memory_id } : {}) });
  // A new official store instance must read the exact record back from disk before success.
  const disk = new HMEM({ persistDir: directory, actor: "nextwise:decision-readback" });
  check(records(disk, investigation).some(d => d.decision_id === id && d.record_sha256 === digest),
    "persistence_unconfirmed", "The save could not be confirmed from disk. Keep your text and retry the same submission.");
  return { reused: false, ...decisionHistory(hmem, investigation, resume) };
}
