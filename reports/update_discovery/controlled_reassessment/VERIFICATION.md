# Controlled semantic reassessment — 26 October 2026

Current stage: the single authorized request completed and its response was
replayed offline. **0 accepted, 2 rejected.** No retries or further model calls
were sent. The updated authenticated backend reopens the persisted rejection
records, and the source/history/allowance preservation audit passes.

## Actual request and observed outcomes

Request `1c245068-11ef-4036-95c7-d7c6024ea28f` returned HTTP 200,
`nvidia/nemotron-3.5-lightning-30b-a3b`, in 57.032 seconds, with finish reason
`stop`. Reported usage: **8,612 prompt + 866 completion = 9,478 total tokens**.
The separately authorized allowance is consumed (1/1). The original three
requests remain recorded under their original authorization, with their original
38,330-token usage. Combined historical usage is 47,808 tokens across four
requests; validation failures still count. Offline replay sends zero requests.

The batch envelope and both candidate identities passed. Each candidate was then
validated independently. Both failed with `assessment_schema`, specifically the
missing required `source_observation` field. The retained input contract lists
that exact field as required and specifies a string of 10–1,800 characters.
This is a generation/contract-compliance failure, not a missing schema declaration
or JSON decoding error. The returned JSON contains neither that field nor a
renamed/nested observation that a justified parser repair could recover.

Independent evidence auditing, without filling the missing fields, also found:

| Candidate | Exact support and additional failure | Persisted outcome |
| --- | --- | --- |
| Nemotron Lightning blog | All three source IDs, passage IDs and quotes (`p5`, `p7`, `p12`) match exactly. However, `existing_findings_connection` is null although the supplied source is explicitly part of the existing investigation. It does not acknowledge the 1/4 pilot/evaluator limitations or genuine Defer decision, and proposes no continuation. | Rejected/uncertain; no new proposal |
| Call of Duty / GeForce NOW | Source ID and passage ID match. The quote changes the publisher excerpt's `[…]` to `[...]`; the exact-substring check fails. The mandatory source observation is absent. | Rejected/uncertain; no new proposal |

Original fail-fast diagnostics are preserved. The separate protected
`independent-evidence-audit-v1.json` records the additional facts; the offline
`revalidation-grounded-discovery-validator-v3.json` preserves a separate replay
result. Both remain failed. No field was synthesized, no quote normalized or
fabricated, no missing linkage invented and no validation requirement dropped.
There is no supported offline parser/contract repair that makes these drafts
valid. The original captured response and original validation output are intact.

Offline prompt clarification `grounded-discovery-contract-v3.1` adds explicit
descriptions for the mandatory source observation and project need, and explains
that existing-investigation membership is a supplied registry fact independent
of relevance category. It warns against excluding transferable capabilities
merely because recipe-domain words are absent, while still requiring a concrete
project connection. This common clarification changes no evidence requirement
and has **not** been tested with another model request. The actual request used
v3, retained exactly; revalidation still uses validator v3 and rejects both
objects. No post-hoc field reconstruction or positive classification occurs.

## Project-relevance diagnostic summaries

These summaries record validation and reasoning findings without reproducing
private model-response excerpts. Full responses remain in protected, ignored
local storage.

**Nemotron blog:** The mandatory source observation was missing. All three
supporting quotations matched exactly, but the assessment omitted its required
connection to the existing investigation, saved 1/4 pilot, evaluator limitations
and genuine Defer Version 1. It supplied no bounded continuation question.
Its reasoning treated missing domain-specific wording as evidence against a
project connection, overlooking the established investigation relationship.
Neither suitability nor irrelevance was established; the assessment remains
rejected/uncertain and created no continuation proposal.

**Gaming feed item:** The mandatory source observation was missing, and an
altered ellipsis made its supporting quotation fail exact matching. Its task
mismatch reasoning did not invent a benefit or unnecessary investigation, but
its article-wide conclusion exceeded the limited feed excerpt. The assessment
remains rejected/uncertain rather than an accepted low-relevance conclusion.

Both original rejection outcomes and their offline replay results are preserved.
No missing content was reconstructed, and no new proposal or approval resulted.

Authorization: `semantic-reassessment-20261026-two-candidates-v1`, at most **one**
additional request, no retries. The original authorization remains three used
requests and is neither reset nor expanded. Reservations count as consumed even
after interruption. A separate ignored local reservation and an official H-MEM
checkpoint guard against duplicate execution; cached authorization records are
also checked if a journal entry is missing.

Candidates are the existing Nemotron Lightning NVIDIA blog
(`9428cc2bc3c996d8505a0fdf`) and Call of Duty / GeForce NOW feed item
(`856d845adf1f95fea166c443`). Candidate identities specify the user's scope;
no article-specific relevance classification or exception is implemented.

## Prompt, contract and evidence preparation

The shared mechanism emits `grounded-discovery-contract-v3` from constants used
by `grounded-discovery-validator-v3`: exact required fields, enum values, string/
nullable types and character/item limits are supplied explicitly. The contract
keeps the existing assessment shape. Explanations/hypotheses/questions are
10–1,800 characters; gap lists have 1–8 entries of 5–1,200 characters; quotations
are 20–1,800 characters with at most three references. Exact source and passage
identity and verbatim substring checks remain mandatory. Available evidence
must be cited even for low or uncertain relevance. Positive relevance requires
a specific project need, evidence, an explicitly labelled hypothesis and a
bounded investigation question. Insufficient evidence must remain uncertain.

Low relevance may use a null investigation question and produces no new
investigation proposal. Its next step may simply retain the item without further
research. Existing historical proposals are preserved. Existing-investigation
sources must acknowledge the saved 1/4 pilot, evaluator limitations and genuine
Defer Version 1, with continuation questions rather than a duplicate pilot or
investigation. All claims must be scoped to the supplied material, not the
unfetched article. Source instructions remain untrusted data.

The blog exposes eight complete paragraphs selected from the full 7,988-character
saved readable text: `p5`, `p7`, `p11`, `p12`, `p13`, `p17`, `p20`, `p27`.
They total 2,967 characters and omit 30 other paragraphs. Selection ranks complete
paragraphs by project-context term overlap for exposure, not relevance
classification. This includes task specialization, model routing, deployment
and reported capabilities beyond the opening paragraphs. Publisher performance
claims remain unverified for this project.

The gaming input is only its 362-character publisher feed excerpt (`p1`),
explicitly labelled incomplete; no linked article was fetched. The prepared
prompt totals 25,155 characters. It includes approved profile/task/constraints,
the original investigation, saved pilot findings/limitations and genuine Defer.
Repeated synthetic fixture inputs are omitted from model context; the complete
approved context hash remains attached to preparation and cache provenance.

The existing Meterless endpoint, route, Nextwise headers, JSON mode and disabled
thinking setting are unchanged. The request cap is 4,000 output tokens, one MB
response bytes and the existing 180-second timeout; proxies and redirects remain
disabled. No probe/model test request was used to diagnose ports.

## Persistence, retention and pre-live checks

`scripts/reassess_discovery_once.py --live` requests the runtime token only through
an interactive hidden prompt. It reserves one request, captures the bounded
response before validation and validates candidates independently once the
batch envelope/identities pass. A credential echo anywhere in the response
envelope is rejected and never retained. Captured response, exact prepared
inputs, model/usage metadata and precise validation diagnostics stay under
ignored `data/memory/hmem/update-discovery/controlled-reassessments/`, with
Windows ACLs restricted to the current user and SYSTEM.

New assessments receive separate authorization/contract cache keys. Original
failed cache entries and semantic history are preserved; the active assessment
pointer can reopen the reassessment after restart. Source events, publication
dates, snapshots and baselines are not rewritten. Continuation proposals remain
unapproved and do not launch research. Low relevance does not create a proposal
or an enabled selection action.

Pre-live verification: **31 tests passed** — controlled reassessment 4, semantic
assessment/diagnostics 12, discovery 6, existing app 9. These use isolated storage
and synthetic transports, never the runtime. They cover full-text paragraph
selection, limited feed coverage, contract alignment, a positive continuation,
low relevance without a proposal, independent quotation rejection, response
retention/offline replay, original failed-cache preservation, restart/selection,
interruption/transport failure and refusal to retry. An initial test exposed a
remaining selection-path comparison against the old cache key; that common
path was corrected and the final four controlled tests passed.

Preparation preview, Python compilation, JavaScript syntax and `git diff --check`
passed. Git-ignore coverage for the protected response path was verified.
`baseline.json` preserves hashes of source fields, old caches, the three original
request records and earlier proposals for the post-request audit.

Existing services were identified without model calls: Nextwise PID 23668 on
8765, with an authenticated in-memory key, and Nightshift Node PID 23680 on 8088.
Both were reused for the request. The user subsequently restarted only Nextwise
to load the new cache-pointer handling; the authenticated replacement is PID
2732. Nightshift was not restarted or probed with a model prompt.

After inspecting the real response, a fifth controlled regression was added for
the observed omitted field, null existing-investigation linkage and changed
ellipsis. All **5 controlled tests passed**, including the four prior tests.
These tests use synthetic neutral source data reproducing the failure shapes,
not a title-specific classification or a public copy of the protected response.
Offline replay confirmed both original rejections and made no model request.

The token was privately entered by the user in the dedicated CLI and never
printed, saved or sent to the UI. The sandbox cannot read the user-only response
folder; authorized read-only inspection/replay used the current user's access
without broadening its ACL. The user was asked to reload the existing app once
to load the new cache-pointer handling; no further runtime-token entry or model
execution is requested.

## Final verification

- **38 distinct tests passed:** shared semantic/diagnostic 12, controlled 5,
  discovery 6, app 9, decision workflow 6. The controlled tests were rerun after
  the offline prompt clarification and passed. They use synthetic transports;
  no test made an extra live model request.
- `verify_controlled_reassessment.py` passed after backend reload: exactly one
  controlled response and three original requests, unique usage per request,
  original cache/request/proposal hashes unchanged, source fields/publication
  dates/baselines/events unchanged, and genuine Defer Version 1 preserved. Its
  read-only before/after comparison found all memory files unchanged by the
  audit. The initial attempt before backend reload correctly failed because the
  stale process had restored the old active cached assessments. Reload applied
  the already persisted new pointers; no result was fabricated or retried.
- Authenticated Chrome checks passed for the six reconciled Zetaris tables,
  eight original memory artifacts, original 1/4 pilot, pending evidence review,
  genuine Defer without integrity warnings, separate request allowances,
  persisted failure/history records, limited coverage and disabled selection,
  and exact state preservation on page reload with no uncaught JavaScript errors.
  The UI also names `source_observation` as the missing required field beside
  the rejection. Final detailed checks are in `live_browser_checks.json`.
- Python compilation, JavaScript syntax and `git diff --check` passed.

Protected full-response replay still rejects both candidates. Positive live
continuation rendering/selection remains **unrun because no live result
validated**; its mechanism passed isolated preparation, persistence, restart and
selection tests. No live human proposal selection or decision write was used
for verification. No publisher fetch, extraction pilot, original-evidence write,
registration write, upstream change, infrastructure install, commit or push was
performed. The original two historical low-relevance proposals remain intact;
this reassessment created none.

Evidence: `summary.json`, `baseline.json`, `preservation_and_replay_audit.json`
and `live_browser_checks.json`. Full response/inputs/original diagnostics and
separate versioned revalidation/evidence audit stay in the user-only ignored
directory. The one-request authorization remains permanently consumed by its
reservation and persisted request ID. No new authorization is being requested.
