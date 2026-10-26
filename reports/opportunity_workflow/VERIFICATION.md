# Opportunity workflow — offline verification, 26 October 2026

Implemented and verified offline. **Not yet a successful live discovery-to-decision
demonstration.** All new source/assessment examples are explicitly synthetic;
official H-MEM persistence and the browser/HTTP implementation are real, isolated
in OS temporary directories. No external requests, live model calls, production
memory writes, pilot reruns, commits or pushes were performed.

## Implemented connection

- `scripts/opportunity_workflow.py`: current accepted semantic assessment ->
  sealed, versioned opportunity recommendation -> explicit human decision,
  versioned history and evidence references. Reuses the unchanged validator,
  source snapshot preparation and existing locked official discovery checkpoints
  with disk read-back. Source/context changes block new decisions; retries and
  identical saves do not duplicate them. Earlier records are retained.
- `scripts/nextwise_app.py`: session/origin-protected bounded JSON endpoints
  `/api/discovery/recommend` and `/api/discovery/decision`; saved discovery reads
  expose briefing/history availability. New choices reference the opportunity's
  evidence instead of requiring the original completed-pilot decision manifest.
  The existing original-investigation decision endpoint is unchanged.
- `web/index.html`, `web/app.js`: prominent opportunity briefings, project need,
  hypothetical value, risks, uncertainty, source quotes and next action; explicit
  choice and rationale, no default. Histories/provenance remain collapsed.
  In-page drafts survive redraw/failure; newer evidence/history requires review.
  Older choices are explicitly not approval of newer briefings. Existing
  investigation, original decision and proposal-selection actions remain available.
- `tests/test_opportunity_workflow.py`, `tests/semantic_fixture.py`,
  `scripts/check_discovery_browser.py`: isolated backend/browser coverage.
- `README.md`, `docs/demo-readiness.md`: exact usage, policy and verification limits.

The conservative recommendation policy is distinct from the saved semantic
reasoning. Potential relevance on a new opportunity yields Test (consider a bounded
plan, not authorization to execute); uncertainty or an existing-investigation
continuation yields Defer; low relevance yields Reject for this opportunity only.
No provisional assessment yields an agent Adopt recommendation. Humans retain all
four choices. No benefits or quotations are invented; no rejected output is repaired
or promoted. First observations remain labelled inventories/baselines, not releases
or detected edits. Preparing a briefing is a separate manual action and makes no call.

## Final checks

| Check | Passed |
| --- | ---: |
| `test_opportunity_workflow.py` | 6 |
| `test_semantic_discovery.py` | 7 |
| `test_update_discovery.py` | 6 |
| `test_decision_workflow.py` | 6 |
| `test_nextwise_app.py` | 9 |
| `test_semantic_diagnostics.py` | 5 |
| `test_controlled_reassessment.py` | 5 |
| Installed Chrome, isolated discovery browser assertions | 30 |

All **44 backend tests and 30 browser assertions passed**. Python AST parsing,
`node --check web/app.js` and `git diff --check` passed. Git reports existing
LF/CRLF normalization warnings, not whitespace errors.

Coverage includes exact-quote rejection, failed assessment promotion prevention,
stale source revision/context/snapshot, changed recommendation hashes, duplicate
requests and content, conflicting human decisions, amendments, integrity failures,
locks, HTTP session/origin protection, unchanged-source deduplication, full process
restart, mobile layout, escaped user text, and pending-versus-recorded status.
Original-investigation records remain byte-identical during the isolated opportunity
workflow test, including its separately created fixture Defer Version 1. No real
human decision was created or amended. Browser requests were restricted to the
fixture origin; no uncaught JavaScript errors occurred. Browser-generated reports
were redirected to temporary storage rather than overwriting earlier reports.

Initial test attempts failed on a too-short synthetic feed quotation and a Windows
connection reset while testing rejected authentication requests with unread bodies.
The fixtures were corrected without changing production validation/security rules.
The first sandboxed Chrome attempt reset its debug connection; the permissioned
fixture-only run passed, as did the final rerun after the older-decision label fix.
No unresolved failures remain in these checks.

## Unverified and minimum live test

No live Zetaris/Nightshift service was contacted and no existing real relevant
assessment became accepted. Both controlled Nemotron/gaming reassessments remain
rejected; the two original accepted low-relevance fragments are not evidence of
this product succeeding on a relevant opportunity. Fixture passes demonstrate
connections, not useful real reasoning or production accuracy.

With separate explicit authorization, obtain one bounded semantic assessment of
the saved Nemotron source under the current contract, with complete selected
paragraphs and the existing pilot/evaluator/Defer context. It must pass the unchanged
validator and human inspection for meaningful, grounded reasoning. In the actual
authenticated app, prepare its briefing, let the user explicitly choose and save,
then restart/reopen and verify the exact recommendation, decision and source links.
Replay unchanged saved sources to confirm no new event or model request. A fresh
public-source check needs separate authorization if fresh detection is to be shown.
Failure at any stage remains failure; it does not authorize a retry or weaker checks.

Limits remain: one approved project, provisional semantic reasoning, no automatic
execution, browser-memory drafts lost on reload, and the existing H-MEM checkpoint
size/non-transactional persistence limits. Existing `.gitignore`/`.gitattributes`
changes were left untouched; upstream code, registrations and original evidence
were not modified.
