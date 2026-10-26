# Offline semantic diagnosis — 26 October 2026

**Recovered: 0. Revalidated accepted fragments: 2. Remaining failed/uncertain:
11. New model requests: 0.** No full original model responses exist in the
discovery response directory or checkpoints. Rejected assessment objects were
also discarded. The two accepted assessment objects and all 13 prepared source
inputs survive in H-MEM. The inspection covers these app-owned local artifacts,
the existing verification report, request report and implementation; runtime
credential/configuration files were not inspected.

## Per-candidate diagnosis

The following are the *actual retained messages*, not reconstructed errors:

- **A:** `Model request or response failed; this attempt is not retried automatically.`
  Shared batch response-processing failure. HTTP 200, a Nemotron model identity
  and usage survive, but no exception, response envelope, final text, finish
  reason or batch ID list survives. Generation, content extraction, JSON parsing
  and batch-schema/identity validation cannot be distinguished. No individual
  assessment in either batch can be recovered or judged malformed. The earlier
  verification report's parsing/batch-identity attribution is an inference,
  not an exact captured exception.
- **B:** `Assessment rejected: invalid identity, unsupported fields, quotation, hypothesis or investigation linkage.`
  The third batch passed the batch gate, then this candidate failed its
  per-assessment contract. The offending object and exact exception are missing;
  identity, fields/types, exact quote, hypothesis and existing-findings checks
  cannot be distinguished. This establishes the validation stage, not whether
  generation or an overly restrictive contract caused the mismatch.
- **C:** No original validation failure. The accepted fragment revalidates under
  `grounded-discovery-validator-v2`, including exact source/passage/quotation
  identity. This does not certify semantic completeness or project suitability.

| Candidate (ID) | Batch | Retained result / attributable origin |
| --- | ---: | --- |
| Nemotron Lightning / NeMo Switchyard (`9428cc2bc3c996d8505a0fdf`) | 1 | A; response-processing stage, exact cause unknown |
| NVIDIA NIM model card (`c0320c9fae8313e8af4d7601`) | 1 | A; response-processing stage, exact cause unknown |
| Meterless (`daf677f0f296925e50c0d739`) | 1 | A; response-processing stage, exact cause unknown |
| Kazakhstan compute (`90e35913e5ba3eb8b4a92f72`) | 1 | A; response-processing stage, exact cause unknown |
| Minerva observability (`2c1c1d0b09d0e274e1a661fd`) | 1 | A; response-processing stage, exact cause unknown |
| Call of Duty / GeForce NOW (`856d845adf1f95fea166c443`) | 2 | A; response-processing stage, exact cause unknown; no semantic conclusion recovered |
| European financial services (`f22a63cc12b9be5044807d05`) | 2 | A; response-processing stage, exact cause unknown |
| Cosmos world models (`36ee8fe7cab29f5dfbb84b94`) | 2 | A; response-processing stage, exact cause unknown |
| DSX power bottleneck (`7d13ce0e971c17c77553a630`) | 2 | A; response-processing stage, exact cause unknown |
| European retail (`898575ccc2fcbfd5eae1b581`) | 2 | A; response-processing stage, exact cause unknown |
| Earth-2 weather (`89a4e6d4e0e5bb84c8c4a864`) | 3 | C; accepted low relevance; reasoning limitations below |
| European public sector (`bc7e4740517cd6fe1e42dac4`) | 3 | C; accepted low relevance; reasoning limitations below |
| Local intelligence / Spark (`6822fece1c79cc899786a2c2`) | 3 | B; per-candidate validation, exact cause unknown |

Every snapshot hash, prepared source identity, selected passage, coverage record,
cache key and complete project-context hash reproduces exactly. **No source
preparation mismatch was found.** This does not show that the passage selection
was optimal. Pages exposed eight selected paragraphs each; the NVIDIA blog
omitted 30 readable paragraphs, NIM omitted 361. Feed inputs contain only short,
often truncated publisher excerpts; articles were never fetched. Those limits
can prevent useful reasoning, but cannot explain the specific rejected outputs
without the missing responses. Original requests used fewer than 6,000 reported
completion tokens each; truncation cannot be diagnosed without finish reasons.

## Request accounting

| Batch / request ID | Candidates | Prompt | Completion | Total | Accepted |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 / `b7deced9-0d3a-42bb-8552-29a298019405` | 5 | 12,994 | 2,686 | 15,680 | 0 |
| 2 / `6977a2d0-3858-4bf9-a82a-0224896869bf` | 5 | 10,384 | 1,806 | 12,190 | 0 |
| 3 / `062b9ff2-0c28-4ba7-94ba-9b67bfc40a8c` | 3 | 9,272 | 1,188 | 10,460 | 2 |
| Total | 13 | **32,650** | **5,680** | **38,330** | **2** |

All three returned HTTP 200 and `nvidia/nemotron-3.5-lightning-30b-a3b`.
Per-candidate copies of usage are grouped by request ID and counted once, even
for failed validations. Journal and cache metadata agree; no usage conflicts or
unconfirmed reservations remain for this run. Provider usage is not a billing
verification. Second and third start timestamps remain unknown.

The original terminal's `requests_used: 1` is preserved as a historical
observation. A stale Python list survived `store.save()` replacing `state` with
the official H-MEM readback. Later batch metadata overwrote the first entry.
The earlier repair reconstructed three entries from distinct cached request IDs
and preserved the malformed journal in `semantic_journal_history`. This patch
also fixes the remaining summary bug: the CLI now uses the union of journal and
cache IDs, reports unique-request usage and separates cumulative allowance from
`new_requests_sent` and `cache_replay`. An unchanged replay reports **3 used,
0 newly sent**, not three new requests. Interrupted reservations remain counted
even during journal reconciliation. Conflicting usage is explicitly flagged.

The separate [diagnosis.json](diagnosis.json) records the corrected summary,
original errors/statuses, preserved journal history and versioned offline
revalidation outcomes. The previous request report and H-MEM outcomes were not
rewritten to claim success.

## Review of the two accepted assessments

**Earth-2:** The exact quotation describes weather forecasts for energy,
insurance and transport. The assessment connects its low priority to the
approved task of preserving free-text user constraints in structured
requirements for recipes and meal plans. It leaves the application hypothesis
null and invents no benefit. This is meaningful negative project reasoning,
though elementary. Its claims about what the *article* does not contain exceed
the excerpt, and “No action required” is stronger than the evidence supports.
A defensible reading is “no task connection established by the available
excerpt”; it is not proof that the full article has no useful content.

**European public sector:** The exact quotation supports the observation about
controlled infrastructure, safeguards and sensitive data. It does not describe
requirements extraction or demonstrate compatibility, costs or integration
effort. Low immediate priority for the approved extraction task is reasonable.
However, “unrelated” overlooks the possible general connection to the profile's
confidential-information boundary; no *concrete integration solution* follows
from that generic connection. Its question “None” and no-action next step do
not prepare a useful investigation. A better bounded question would ask whether
the existing excerpt identifies an actual interface, structured-output capability
or confidentiality mechanism applicable to the approved task; presently it does
not establish one. This review proposes no positive classification or benefit.

Both therefore retain their historical **structurally validated, provisional low
relevance** status, with a separately recorded reasoning-quality limitation.
Neither establishes a positive application. No model rewrite, fabricated quote,
proposal approval or replacement assessment was persisted. The two unapproved
agent proposals remain unchanged.

## Minimal supported repairs and replay

- Versioned validation diagnostics now distinguish malformed JSON, batch schema,
  missing/duplicate/unknown IDs, field contracts, source identity, passage identity,
  exact quotation, hypothesis and investigation linkage. Safe field paths/codes
  replace the lost generic exception; model text is not interpolated into errors.
- Type-invalid passage/candidate IDs are diagnosed explicitly. Duplicate JSON
  object keys are rejected. Required fields, exact quotations, grounded positive
  need/hypothesis requirements, uncertainty rules and original-investigation
  linkage remain enforced. No malformed JSON or missing ID is repaired by guess.
- Future bounded response artifacts retain content/hash, request/model/usage,
  recognized finish reason, prepared evidence inputs, context hash and validator
  version in ignored discovery storage after the credential-echo check. Invalid
  response content remains untrusted. Existing retained-content support had been
  added after the live run; this patch supplies the inputs needed for strict
  offline replay and more precise diagnostics.
- `python scripts/diagnose_semantic_discovery.py` reads local immutable artifact
  and decision envelopes, verifies their original bytes/hashes and reproduces
  the exact cached context. It never invokes a model, a public source or a
  credentials prompt. Original accepted fragments revalidate **2/2** under v2;
  rejected fragments/full responses are missing, so **0/11** are recoverable.
  The JSON report keeps revalidation separate from original outcomes and records
  original assessment/cache/context hashes.

The first diagnostic attempt used the normal official context-resume reader;
that reader records H-MEM retrieval access events. Those audit events are
preserved. It did not change artifact contents, assessments or Defer. The final
offline reader avoids those touches, and its complete before/after H-MEM file
hash comparison passes. No upstream adapter code was changed.

## Verification and limits

Final checks: **54 tests passed** — semantic assessment/diagnostics 12 (including
five new focused tests), discovery 6, analyzer helper 21, app 9, decision workflow
6. New tests cover distinguishable JSON/batch/field/source/quote failures,
three-batch failed/partial retention and offline replay, missing-response limits,
unchanged cache behavior, duplicate-key/identity rejection, exhausted or
interrupted allowance, unique usage accounting and credential-echo rejection.
The final local diagnosis also passes exact source/context reproduction and a
complete before/after memory-file hash comparison. Python compilation and
`git diff --check` pass.

One initial synthetic test failed because its short fixture contained no quote
to mutate; the fixture was corrected to contain a supporting paragraph, then
the final suite passed. An initial all-memory-file immutability assertion also
detected normal retrieval audit events; the offline reader correction described
above resolved it without erasing history.

Synthetic transports only exercise the failure classes; they are not
reconstructed live responses. Live
generation, public-source checks, authenticated UI checks and pilot execution
are intentionally unrun in this offline task. No credentials were requested,
no original evidence or scores changed, and no commits or pushes were made.

Another live run cannot recover discarded text. It would be useful only with
**new explicit authorization** and a deliberately scoped reassessment mechanism
that preserves failed cache/history rather than silently retrying unchanged
inputs. First deploy the versioned diagnostics/response retention and test their
replay; specify the exact schema/field limits and require excerpt-scoped claims
and useful evidence-gap questions even for low relevance. Target a small failed
batch, then inspect its captured errors before considering any further call.
Do not blindly increase token limits, change models, relax quote/identity checks
or rerun all 13. The existing allowance is exhausted, and unchanged `--live`
inputs remain cache hits. No further authorization was requested in this task.
