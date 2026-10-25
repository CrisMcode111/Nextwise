/** Nextwise adapter; official H-MEM remains unchanged under vendor/meterless. */
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { HMEM } from "../vendor/meterless/hmem/reference/src/index.ts";
import { DecisionError, decisionHistory, decisionEvidence, saveDecision } from "./decision_records.ts";

const COMMIT = "1742dec56a66e58eef9dda2d2b865823758ca8cd";
const FILES: Record<string, string> = {
  project_profile: "data/project_profile.json",
  investigation: "data/investigation.json",
  sources: "data/sources.json",
  evidence_draft: "data/evidence_draft.json",
  evidence_review: "data/evidence_review.json",
};
const BASE_KINDS = Object.keys(FILES);
function configureOptionalFiles(paths: Record<string, string>) {
  for (const kind of Object.keys(FILES)) if (!BASE_KINDS.includes(kind)) delete FILES[kind];
  for (const [kind, file] of Object.entries(paths)) {
    if (BASE_KINDS.includes(kind)) {
      requireCondition(file === FILES[kind], "invalid_artifact", "Base artifact paths must not change.");
      continue;
    }
    const allowed = kind === "use_case" ? file === "data/use_case.json" :
      kind === "evaluation_results" ? /^data\/evaluations\/[A-Za-z0-9_-]+\/results\.json$/.test(file) :
      kind === "evaluation_recommendation" ? /^data\/evaluations\/[A-Za-z0-9_-]+\/recommendation\.json$/.test(file) : false;
    requireCondition(allowed, "invalid_artifact", "Optional artifact kind or path is invalid.");
    FILES[kind] = file;
  }
  requireCondition(!FILES.evaluation_results || (FILES.use_case && FILES.evaluation_recommendation &&
    path.posix.dirname(FILES.evaluation_results) === path.posix.dirname(FILES.evaluation_recommendation)),
    "invalid_artifact", "Evaluation import requires its use case and matching recommendation.");
  requireCondition(!FILES.evaluation_recommendation || FILES.evaluation_results,
    "invalid_artifact", "Recommendation requires its evaluation results.");
}
const ACTOR = "nextwise:artifact-memory";
const sha = (bytes: Buffer | string): string => crypto.createHash("sha256").update(bytes).digest("hex");
const canonical = (value: any): string => JSON.stringify(sortKeys(value));
function sortKeys(value: any): any {
  return Array.isArray(value) ? value.map(sortKeys) : value && typeof value === "object" ?
    Object.fromEntries(Object.keys(value).sort().map(k => [k, sortKeys(value[k])])) : value;
}
type Artifact = { kind: string; path: string; sha256: string; bytes_base64: string };
type Request = { operation: "import" | "resume" | "decision_save" | "decision_history" | "decision_evidence"; investigation_id: string; memory_root: string; artifacts?: Artifact[]; decision?: any; decision_id?: string; kind?: string };
type Envelope = Artifact & { schema: string; investigation_id: string };
type Manifest = {
  schema: string; investigation_id: string; upstream_commit: string; revision_key: string;
  artifact_ids: Record<string, string>; artifact_hashes: Record<string, string>;
  review_to_draft: { review_id: string; draft_id: string; reviewed_draft_sha256: string };
  approval: object; decision: null;
  artifact_paths?: Record<string, string>;
};
class BridgeError extends Error {
  constructor(public code: string, message: string) { super(message); }
}
function requireCondition(condition: unknown, code: string, message: string): asserts condition {
  if (!condition) throw new BridgeError(code, message);
}
function parseObject(text: string): any {
  let value: any;
  try { value = JSON.parse(text); } catch { throw new BridgeError("invalid_json", "An artifact or request is not valid JSON."); }
  requireCondition(value && typeof value === "object" && !Array.isArray(value), "invalid_shape", "Expected a JSON object.");
  return value;
}
function decode(artifact: Artifact): { bytes: Buffer; document: any } {
  requireCondition(typeof artifact.bytes_base64 === "string" && /^[a-f0-9]{64}$/.test(artifact.sha256), "invalid_artifact", "Invalid artifact encoding or hash.");
  const bytes = Buffer.from(artifact.bytes_base64, "base64");
  requireCondition(bytes.toString("base64") === artifact.bytes_base64 && sha(bytes) === artifact.sha256,
    "integrity_error", "Artifact bytes do not match their recorded SHA-256 hash.");
  return { bytes, document: parseObject(bytes.toString("utf8")) };
}
function validateArtifacts(artifacts: Artifact[], investigationId: string): Record<string, any> {
  requireCondition(Array.isArray(artifacts) && artifacts.length === Object.keys(FILES).length,
    "invalid_artifacts", "Import requires all declared Nextwise artifact files.");
  const documents: Record<string, any> = {};
  const hashes: Record<string, string> = {};
  for (const artifact of artifacts) {
    requireCondition(Object.hasOwn(FILES, artifact.kind) && artifact.path === FILES[artifact.kind] && !Object.hasOwn(documents, artifact.kind),
      "invalid_artifact", "Unknown, duplicate or incorrectly named artifact.");
    documents[artifact.kind] = decode(artifact).document;
    hashes[artifact.path] = artifact.sha256;
  }
  const { project_profile: profile, investigation, sources, evidence_draft: draft, evidence_review: review } = documents;
  requireCondition(investigation.id === investigationId && profile.id === investigation.project_id &&
    [sources, draft, review].every(d => d.investigation_id === investigationId) && review.project_id === profile.id,
    "investigation_mismatch", "Artifacts do not belong to the requested investigation and approved profile.");
  requireCondition(review.reviewed_draft?.path === FILES.evidence_draft && review.reviewed_draft?.sha256 === hashes[FILES.evidence_draft],
    "review_draft_mismatch", "The review does not reference the exact imported draft.");
  requireCondition(Array.isArray(review.local_input_references), "missing_provenance", "Review input references are missing.");
  for (const artifact of artifacts.filter(a => BASE_KINDS.includes(a.kind) && a.kind !== "evidence_review")) {
    const refs = review.local_input_references.filter((ref: any) => ref.path === artifact.path);
    requireCondition(refs.length === 1 && refs[0].sha256 === artifact.sha256,
      "review_input_mismatch", "A saved input no longer matches the provenance recorded in the review.");
  }
  requireCondition(draft.status === "grounded_draft_requiring_review" &&
    review.status === "ai_assisted_review_pending_user_approval" &&
    review.approval?.status === "pending_user_approval" && review.approval.approved_by === null &&
    review.approval.approved_at_utc === null &&
    [investigation, draft, review, review.readiness].every(d => d && d.decision === null),
    "unsupported_lifecycle", "This adapter preserves pending review and a null decision; it cannot approve or decide.");
  requireCondition(Array.isArray(draft.accepted) && Array.isArray(draft.unknowns) &&
    Array.isArray(investigation.open_questions) && Array.isArray(review.unresolved_evidence_gaps),
    "invalid_shape", "Required evidence, unknowns or evaluation steps are missing.");
  const useCase = documents.use_case;
  if (useCase) {
    requireCondition(useCase.investigation_id === investigationId && useCase.project_id === profile.id && useCase.decision === null,
      "investigation_mismatch", "Use case must belong to this investigation with no decision.");
    for (const kind of ["project_profile", "investigation", "evidence_draft", "evidence_review"]) {
      requireCondition(useCase.provenance?.artifact_references?.some((ref: any) => ref.path === FILES[kind] && ref.sha256 === hashes[FILES[kind]]),
        "missing_provenance", "Use case input provenance does not match imported artifacts.");
    }
  }
  const evaluation = documents.evaluation_results, recommendation = documents.evaluation_recommendation;
  if (evaluation) {
    requireCondition(evaluation.investigation_id === investigationId && evaluation.decision === null &&
      evaluation.approval?.status === "pending_user_approval" && ["incomplete", "completed_pilot"].includes(evaluation.status) &&
      evaluation.use_case_reference?.path === FILES.use_case && evaluation.use_case_reference?.sha256 === hashes[FILES.use_case],
      "evaluation_integrity_error", "Evaluation status or use-case provenance is inconsistent.");
    requireCondition(recommendation.investigation_id === investigationId && recommendation.decision === null &&
      recommendation.approval?.status === "pending_user_approval" && recommendation.status === "ai_assisted_recommendation_pending_user_approval" &&
      recommendation.evaluation_reference?.path === FILES.evaluation_results &&
      recommendation.evaluation_reference?.sha256 === hashes[FILES.evaluation_results],
      "evaluation_integrity_error", "Recommendation must reference the exact results and remain pending.");
    for (const item of [evaluation, recommendation]) for (const kind of ["evidence_draft", "evidence_review"]) {
      requireCondition(item.evidence_references?.some((ref: any) => ref.path === FILES[kind] && ref.sha256 === hashes[FILES[kind]]),
        "missing_provenance", "Evaluation evidence references do not match saved evidence.");
    }
    const fixtures = useCase.proposed_evaluation_examples?.examples;
    requireCondition(Array.isArray(fixtures) && Array.isArray(evaluation.fixtures) && evaluation.fixtures.length === fixtures.length &&
      evaluation.fixtures.every((f: any) => fixtures.some((original: any) => original.id === f.id &&
        sha(canonical(original)) === f.sha256 && sha(canonical(f.snapshot)) === f.sha256 && sha(original.input) === f.input_sha256)) &&
      sha(canonical(evaluation.output_schema)) === evaluation.output_schema_sha256 &&
      Array.isArray(evaluation.cases) && evaluation.cases.length <= 4 &&
      evaluation.cases.every((c: any) => evaluation.fixtures.some((f: any) => f.id === c.fixture_id && f.sha256 === c.fixture_sha256)),
      "evaluation_integrity_error", "Evaluation fixture, case or schema hashes are inconsistent.");
  }
  return documents;
}
function envelopeOf(record: any): any {
  try { return JSON.parse(record.content); } catch { return null; }
}
function readSnapshot(hmem: HMEM, record: any, investigationId: string) {
  const manifest = parseObject(record.content) as Manifest;
  requireCondition(manifest.schema === "nextwise.hmem.manifest.v1" && manifest.investigation_id === investigationId &&
    record.chatId === investigationId && manifest.upstream_commit === COMMIT,
    "manifest_integrity_error", "Invalid investigation manifest or upstream version.");
  requireCondition(manifest.artifact_ids && manifest.artifact_hashes && manifest.review_to_draft,
    "manifest_integrity_error", "Manifest artifact references are missing.");
  configureOptionalFiles(manifest.artifact_paths ?? Object.fromEntries(BASE_KINDS.map(k => [k, FILES[k]])));
  requireCondition(Object.keys(manifest.artifact_ids).length === Object.keys(FILES).length,
    "manifest_integrity_error", "Manifest paths and IDs disagree.");
  const artifacts: Artifact[] = [];
  const records = [record];
  for (const kind of Object.keys(FILES)) {
    const memory = hmem.store.get(manifest.artifact_ids[kind]);
    requireCondition(memory, "missing_memory", "A required artifact memory ID is missing.");
    const envelope = parseObject(memory.content) as Envelope;
    requireCondition(envelope.schema === "nextwise.hmem.artifact.v1" && envelope.investigation_id === investigationId &&
      memory.chatId === investigationId && envelope.kind === kind && envelope.sha256 === manifest.artifact_hashes[kind] &&
      memory.source === `nextwise:file:${FILES[kind]}` && memory.provenance?.origin === "document" &&
      Array.isArray(memory.provenance.refs) && memory.provenance.refs.includes(FILES[kind]) &&
      memory.provenance.refs.includes(`sha256:${envelope.sha256}`),
      "integrity_error", "An artifact memory does not match its manifest.");
    artifacts.push(envelope);
    records.push(memory);
  }
  const documents = validateArtifacts(artifacts, investigationId);
  const review = documents.evidence_review;
  requireCondition(manifest.review_to_draft.review_id === manifest.artifact_ids.evidence_review &&
    manifest.review_to_draft.draft_id === manifest.artifact_ids.evidence_draft &&
    manifest.review_to_draft.reviewed_draft_sha256 === manifest.artifact_hashes.evidence_draft &&
    manifest.decision === null && JSON.stringify(manifest.approval) === JSON.stringify(review.approval),
    "manifest_integrity_error", "Manifest lifecycle or review-to-draft relationship is invalid.");
  const reviewMemory = records.find(r => r.id === manifest.artifact_ids.evidence_review)!;
  requireCondition(reviewMemory.derivedFrom?.includes(manifest.artifact_ids.evidence_draft),
    "missing_provenance", "Review memory lacks its draft lineage.");
  for (const [child, parent] of [["use_case", "evidence_review"], ["evaluation_results", "use_case"], ["evaluation_recommendation", "evaluation_results"]]) {
    if (manifest.artifact_ids[child]) requireCondition(hmem.store.get(manifest.artifact_ids[child])?.derivedFrom?.includes(manifest.artifact_ids[parent]),
      "missing_provenance", "Optional artifact lacks its recorded lineage.");
  }
  for (const memory of records) {
    // store.get() is an actual lookup but does not audit or persist touches.
    // Use the official services to record only the reads that just happened.
    hmem.store.touch(memory.id);
    hmem.ledger.log(memory.id, "read", ACTOR, { details: { operation: "verified_snapshot_read" } });
  }
  hmem.store.persist();
  return { manifest, documents };
}
function importArtifacts(hmem: HMEM, request: Request) {
  const artifacts = request.artifacts!;
  const documents = validateArtifacts(artifacts, request.investigation_id);
  const hashes = Object.fromEntries(artifacts.map(a => [a.kind, a.sha256]));
  const revisionKey = sha(JSON.stringify(Object.keys(FILES).map(k => [k, hashes[k]])));
  const manifests = hmem.store.all().filter(r => {
    const value = envelopeOf(r);
    return value?.schema === "nextwise.hmem.manifest.v1" && value.investigation_id === request.investigation_id && value.revision_key === revisionKey;
  });
  requireCondition(manifests.length <= 1, "duplicate_manifest", "Duplicate manifests require manual inspection.");
  if (manifests.length) {
    const snapshot = readSnapshot(hmem, manifests[0], request.investigation_id);
    return { reused: true, manifest_id: manifests[0].id, artifact_ids: snapshot.manifest.artifact_ids, artifact_hashes: hashes, artifact_paths: { ...FILES } };
  }
  const ids: Record<string, string> = {};
  for (const kind of Object.keys(FILES)) {
    const artifact = artifacts.find(a => a.kind === kind)!;
    const existing = hmem.store.all().filter(r => {
      const value = envelopeOf(r);
      return value?.schema === "nextwise.hmem.artifact.v1" && value.investigation_id === request.investigation_id &&
        value.kind === kind && value.sha256 === artifact.sha256;
    });
    requireCondition(existing.length <= 1, "duplicate_artifact", "Duplicate artifact versions require manual inspection.");
    if (existing.length) {
      const stored = parseObject(existing[0].content) as Envelope;
      decode(stored);
      requireCondition(stored.bytes_base64 === artifact.bytes_base64 && existing[0].chatId === request.investigation_id,
        "integrity_error", "An existing artifact version is inconsistent.");
      ids[kind] = existing[0].id;
    } else {
      const envelope = { schema: "nextwise.hmem.artifact.v1", investigation_id: request.investigation_id, ...artifact };
      ids[kind] = hmem.add({ content: JSON.stringify(envelope), type: "general", layer: "working",
        source: `nextwise:file:${artifact.path}`, chatId: request.investigation_id, missionId: request.investigation_id,
        tags: ["project:nextwise", `investigation:${request.investigation_id}`, `artifact:${kind}`, `sha256:${artifact.sha256}`],
        provenance: { origin: "document", learnedAt: Date.now(), label: `Exact saved Nextwise ${kind}; not independent verification`,
                      refs: [artifact.path, `sha256:${artifact.sha256}`] },
        ...(["evidence_review", "use_case", "evaluation_results", "evaluation_recommendation"].includes(kind) ? {
          derivedFrom: kind === "evidence_review" ? [ids.evidence_draft] : kind === "use_case" ? [ids.evidence_draft, ids.evidence_review] :
            kind === "evaluation_results" ? [ids.use_case, ids.evidence_draft, ids.evidence_review] : [ids.evaluation_results],
        } : {}),
      }).id;
    }
  }
  const manifest: Manifest = {
    schema: "nextwise.hmem.manifest.v1", investigation_id: request.investigation_id, upstream_commit: COMMIT,
    revision_key: revisionKey, artifact_ids: ids, artifact_hashes: hashes,
    artifact_paths: { ...FILES },
    review_to_draft: { review_id: ids.evidence_review, draft_id: ids.evidence_draft, reviewed_draft_sha256: hashes.evidence_draft },
    approval: documents.evidence_review.approval, decision: null,
  };
  // Publish the manifest last. Interrupted imports leave reusable artifact
  // records, never a manifest that claims to contain a completed snapshot.
  const record = hmem.add({ content: JSON.stringify(manifest), type: "general", layer: "working",
    source: "nextwise:investigation-import", chatId: request.investigation_id,
    tags: ["project:nextwise", `investigation:${request.investigation_id}`, "artifact:manifest"],
    provenance: { origin: "manual", learnedAt: Date.now(), label: "Imported artifact manifest; no user approval or decision",
                  refs: Object.values(ids) }, derivedFrom: Object.values(ids),
  });
  readSnapshot(hmem, record, request.investigation_id);
  return { reused: false, manifest_id: record.id, artifact_ids: ids, artifact_hashes: hashes, artifact_paths: { ...FILES } };
}
function resume(hmem: HMEM, investigationId: string) {
  const candidates = hmem.store.all().filter(r => {
    const value = envelopeOf(r);
    return value?.schema === "nextwise.hmem.manifest.v1" && value.investigation_id === investigationId;
  }).sort((a, b) => b.timestamp - a.timestamp || Number(b.id.slice(4)) - Number(a.id.slice(4)));
  requireCondition(candidates.length, "not_imported", "No completed import exists for this investigation.");
  const { manifest, documents } = readSnapshot(hmem, candidates[0], investigationId);
  const draft = documents.evidence_draft, review = documents.evidence_review;
  const claimKinds: Record<string, number> = Object.create(null);
  for (const claim of draft.accepted) claimKinds[claim.claim_kind] = (claimKinds[claim.claim_kind] ?? 0) + 1;
  return {
    manifest_id: candidates[0].id, artifact_ids: manifest.artifact_ids, artifact_hashes: manifest.artifact_hashes,
    artifact_paths: { ...FILES },
    review_to_draft: manifest.review_to_draft, artifacts: documents,
    question: documents.investigation.question,
    evidence: { status: draft.status, accepted_count: draft.accepted.length, claim_kind_counts: claimKinds },
    review: { status: review.status, approval: review.approval }, approval: review.approval, decision: null,
    analysis_observation: { scope: "Nextwise analysis only; not requirements-extraction performance",
      duration_seconds: draft.request_duration_seconds, token_usage: draft.token_usage, returned_model: draft.returned_model },
    unresolved_questions: documents.investigation.open_questions, unknowns: draft.unknowns,
    unresolved_evidence_gaps: review.unresolved_evidence_gaps.filter((g: any) => g.status === "unresolved"),
    readiness: review.readiness,
    use_case: documents.use_case ?? null,
    evaluation_results: documents.evaluation_results ?? null,
    evaluation_recommendation: documents.evaluation_recommendation ?? null,
  };
}
async function main() {
  const chunks: Buffer[] = [];
  let size = 0;
  for await (const chunk of process.stdin) {
    size += chunk.length;
    requireCondition(size <= 2_000_000, "input_too_large", "Bridge input exceeds the 2 MB demonstration limit.");
    chunks.push(Buffer.from(chunk));
  }
  const request = parseObject(Buffer.concat(chunks).toString("utf8")) as Request;
  requireCondition(["import", "resume", "decision_save", "decision_history", "decision_evidence"].includes(request.operation) && typeof request.investigation_id === "string" &&
    /^[a-z0-9][a-z0-9-]{0,119}$/.test(request.investigation_id) && typeof request.memory_root === "string" && request.memory_root.length > 0,
    "invalid_request", "Provide an operation, a safe investigation ID and a memory root.");
  if (request.operation === "import") {
    requireCondition(Array.isArray(request.artifacts), "invalid_artifacts", "Artifacts must be an array.");
    configureOptionalFiles(Object.fromEntries(request.artifacts.map(a => [a.kind, a.path])));
    validateArtifacts(request.artifacts!, request.investigation_id);
  }
  const directory = path.resolve(request.memory_root, request.investigation_id);
  if (request.operation !== "import") {
    requireCondition(fs.existsSync(path.join(directory, "state.json")), "not_imported", "This investigation has not been imported into H-MEM.");
  } else fs.mkdirSync(directory, { recursive: true });
  const lockPath = path.join(directory, "nextwise.lock");
  let lock: number;
  try { lock = fs.openSync(lockPath, "wx"); }
  catch (error: any) {
    if (error.code === "EEXIST") throw new BridgeError("memory_locked", "Another process holds the investigation lock, or a stale lock requires manual inspection.");
    throw error;
  }
  try {
    fs.writeFileSync(lock, JSON.stringify({ pid: process.pid, actor: ACTOR, created_at: new Date().toISOString() }));
    const hmem = new HMEM({ persistDir: directory, actor: ACTOR });
    const read = () => resume(hmem, request.investigation_id);
    const result = request.operation === "import" ? importArtifacts(hmem, request) : request.operation === "resume" ? read() :
      request.operation === "decision_save" ? saveDecision(hmem, request.investigation_id, request, read, directory) :
      request.operation === "decision_evidence" ? decisionEvidence(hmem, request.investigation_id, request.decision_id!, request.kind!) :
      decisionHistory(hmem, request.investigation_id, read);
    process.stdout.write(JSON.stringify({ ok: true, investigation_id: request.investigation_id, upstream_commit: COMMIT, ...result }) + "\n");
  } finally {
    fs.closeSync(lock);
    fs.unlinkSync(lockPath);
  }
}
main().catch((error: any) => {
  const known = error instanceof BridgeError || error instanceof DecisionError;
  process.stdout.write(JSON.stringify({ ok: false, error: {
    code: known ? error.code : "storage_error",
    message: known ? error.message : "H-MEM operation failed; inspect storage and runtime compatibility without exposing artifact contents.",
  } }) + "\n");
  process.exitCode = 1;
});
