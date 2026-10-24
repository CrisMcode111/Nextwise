# Investigation memory with official H-MEM

## Confirmed use case

Nextwise helps a solo entrepreneur resume a technical investigation using saved
evidence, provenance and uncertainty. The current investigation asks whether AI
Raw Gourmet should test NVIDIA Nemotron 3.5 Lightning for extracting user
requirements into structured data. Its criteria are reliability, cost and speed,
and development effort.

The approved project profile describes an existing prototype, one developer,
Windows 11 with 16 GB RAM, limited development time, and additional costs that
must be justified. Cloud services may be considered. The current extraction
method, acceptance thresholds and budget are unknown. This integration does not
access the separate project folder or infer its implementation.

On resume, Nextwise must recover the exact evidence draft and AI-assisted review,
show their status and unresolved evidence gaps, and display the evaluation steps
already recorded in the review. Publisher claims, observations of Nextwise's
analysis, AI-assisted review, user approval and the investigation decision remain
distinct. The current review awaits user approval and the decision is null.

## Implementation boundary

Use the official `HMEM` class from Meterless/Meterless at commit
`1742dec56a66e58eef9dda2d2b865823758ca8cd`, through a TypeScript bridge invoked by
Python. Preserve upstream source and licensing. Do not install the private
reference package from npm or substitute a separate JSON database for H-MEM.

The smallest implementation stores exact source artifact bytes in official
working-layer records, with SHA-256 hashes and provenance. A manifest stored in
H-MEM records the returned artifact IDs and the review-to-draft relationship.
Each investigation has its own persistence directory. All bridge operations use
an exclusive process lock; repeated imports of identical artifacts reuse records.

Required artifacts are retrieved by their recorded IDs and checked against their
hashes before display. No model, memory mining, approval, recommendation, dreaming,
sleep, auto-resolution or automatic promotion is invoked. Existing evidence and
the successful analyzer configuration remain unchanged.

## Files and provenance

Unmodified upstream code, license files, tests and the original dependency
lockfile are in `vendor/meterless/`. `vendor/meterless/upstream.json` records the
commit and all imported file hashes. Local adaptations are described in
`vendor/meterless/upstream-notes.md`.

`scripts/investigation_memory.py` passes JSON over stdin to
`scripts/hmem_bridge.ts`. The bridge imports the official `HMEM`, with no model
hook. Node.js 24.22.1 executes TypeScript using
`--experimental-transform-types`. The existing Python interpreter is 3.11.9.

The importer reads exactly five files: the approved project profile,
investigation, source registry, evidence draft and evidence review. Each is
stored as a distinct H-MEM `working` record with an exact-byte base64 envelope,
SHA-256 hash, source path and explicit provenance. The review record has
`derivedFrom` pointing at the draft memory ID. Original JSON files are never
rewritten. No publisher claim is promoted into independently verified evidence.

The sixth record is a manifest containing the five returned IDs, hashes,
review-to-draft link, pending approval and null decision. The manifest is written
last and remains in H-MEM. There is no separate homegrown JSON index. Identical
imports reuse the existing manifest and artifact IDs. Changed, internally
consistent versions create new records, retaining previous snapshots. Resume
chooses the latest created complete manifest, never a similarity-ranked substitute.

## Commands

From `C:\Users\crist\Desktop\Nextwise`:

```powershell
python .\scripts\investigation_memory.py import
python .\scripts\investigation_memory.py resume
```

The default investigation is read from `data/investigation.json`. An explicit
resume command is:

```powershell
python .\scripts\investigation_memory.py resume --investigation-id nemotron-lightning-requirements-extraction
```

Use `--json` for structured results. Resume includes the full retrieved artifact
documents, original statuses, publisher-claim counts, Nextwise-only analysis
observations, open questions and the review's unresolved gaps and proposed next
actions. Actions are displayed, not executed. It also reports if current local
artifact files differ from the imported snapshot.

## Persistence and locking

Default state lives in `data/memory/hmem/<investigation-id>/`. The official
reference writes `state.json` and `ledger.jsonl`. Generated state and all
`node_modules` directories are gitignored. `--memory-root` selects a separate
root, useful for tests.

Every bridge import or resume acquires `nextwise.lock` using an exclusive file
create. A second process fails closed rather than writing concurrently. The
lock is removed in a finally block on normal completion and handled exceptions.
A forcibly killed process can leave a stale lock. Inspect its PID and confirm
the owner is no longer active before manually removing that specific lock.
Never automatically delete another process's lock. External tools that bypass
the bridge must also respect this locking protocol.

## Dependencies and checks

There are no added Python or H-MEM runtime packages. The reference's lockfile
pins the development toolchain, including `tsx` 4.23.0 and `vitest` 2.1.9.
Reproduce the official test environment from its local package folder:

```powershell
Push-Location .\vendor\meterless\hmem\reference
npm.cmd ci --ignore-scripts --no-audit --no-fund
npm.cmd test
npx.cmd tsx ..\conformance\runner.ts
Pop-Location
python -m unittest discover -s tests -v
```

On this machine the registry initially failed TLS certificate-chain validation.
Using Node's `--use-system-ca` enabled the normal Windows trust store and allowed
the locked installation. Certificate validation was not disabled. If needed,
set `$env:NODE_OPTIONS = '--use-system-ca'` only in the installation shell.

## Reference limitations

- This is an official deterministic reference, not a production database.
  Embeddings are hash-based mocks, not semantic model embeddings.
- Persistence is synchronous JSON plus a separate append-only JSONL ledger.
  There are no transactions or atomic multi-file commits. The wrapper lock
  prevents cooperating concurrent writers but does not make power loss safe.
  An interrupted write or malformed state requires manual recovery from a
  trusted copy. A manifest is published last, and incomplete artifact records
  can be reused, but storage corruption is not automatically repaired.
- The reference ranker does not enforce missionId/goalRunId isolation, and even
  chat filtering can include unscoped records. Separate persistence directories
  and exact-ID retrieval enforce the required boundary here.
- The canonical-memory examples in upstream prose and the concrete types differ.
  The bridge follows `reference/src/types.ts`, including string-array provenance
  refs and the `document` origin.
- H-MEM layers and confidence do not represent user approval. This adapter only
  supports the current pending-review/null-decision stage and refuses imports
  that assert approval or a decision. A future approval workflow needs a separate,
  explicit user action and artifact; it cannot be inferred from retrieval.
- Node TypeScript transformation is experimental. Only the inspected local
  Windows/Node environment is validated. No model, performance, cross-platform,
  crash-recovery or production-scale qualification is implied by these tests.

Actual test results are recorded in `reports/HMEM_INTEGRATION_VALIDATION.md`.
