# Semantic discovery and agent proposals — 26 October 2026

Implemented semantic project reasoning through the existing Meterless/Nemotron
configuration and automatically persisted agent proposals. Human rationale is
no longer mandatory: the interface offers an optional note and explicit review/
selection, separate from approval or launching an investigation.

**Live semantic verification is partial:** three authorized requests were sent,
two candidate assessments validated and eleven failed validation. Failed
candidates are visibly uncertain, not presented as useful technology or replaced
with deterministic reasoning. The three-request allowance is exhausted. No
additional requests or automatic retries were sent.

## Actual live requests

All returned HTTP 200 and model **`nvidia/nemotron-3.5-lightning-30b-a3b`** through
the unchanged `meterless/auto` route at `127.0.0.1:8088`. JSON mode,
`enable_thinking:false`, the existing Nextwise headers and tier-split setting
were retained. The runtime token was entered privately at a hidden prompt,
remained in that process, and was not read from a file, printed, saved or sent to
the browser.

| Request | Candidates | Prompt tokens | Completion tokens | Total tokens | Duration | Validated |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 5 | 12,994 | 2,686 | 15,680 | 100.324 s | 0 |
| 2 | 5 | 10,384 | 1,806 | 12,190 | 95.504 s | 0 |
| 3 | 3 | 9,272 | 1,188 | 10,460 | 64.102 s | 2 |
| Total | 13 | **32,650** | **5,680** | **38,330** | | **2** |

The two validated assessments are low relevance and generated two persisted,
unapproved agent proposals. No positive application was forced. Their source IDs
and exact supporting quotations passed validation against the actual prepared
paragraphs. The other eleven outcomes remain failed/uncertain, including the
ambiguous extraction-mode candidate and the three existing-investigation sources.

The first two batches did not pass response parsing/batch-identity validation.
One third-batch assessment failed the per-candidate contract/quotation/linkage
checks. The first implementation discarded those unvalidated raw contents, so
the precise original field mismatch cannot be established offline. These are
not successful semantic assessments and were not retried. Future requests retain
bounded untrusted responses in ignored discovery storage after rejecting any
credential echo, and expose specific fixed validation-error categories; that
hardening did not consume another request or reclassify failed outputs.

The initial request journal also held a stale Python list after H-MEM read-back,
which let later batch metadata overwrite its first entry. Fixed that adapter
bug and added a three-batch/restart/quota regression. All three actual request
IDs, per-candidate model metadata and usage remained persisted in the semantic
cache. Reconstructed the journal from those records, preserving the earlier
journal in history. Unknown second/third reservation start times remain null.
Request allowance checks count the union of journal and cached request IDs, so
lost or interrupted journal entries cannot permit another call.

Evidence: [requests.json](requests.json),
[preservation and zero-call cache audit](preservation_and_cache_audit.json).
Reported usage is provider metadata, not verified monetary cost.

## Grounding, context and proposals

The verified H-MEM context includes the approved project profile, use case,
existing investigation, registered sources, saved pilot validations and
recommendation/evaluator limitations, plus genuine Defer Version 1 and its exact
record hash. The cache includes the project-context hash and source/content/
passage/provenance hash under `nemotron-grounded-discovery-v1`.

Three existing pages contribute 2,967, 3,941 and 4,499 characters respectively
from complete readable paragraphs in hash-verified saved snapshots. Each source
is limited to eight complete paragraph blocks and 4,500 characters; paragraphs
are ranked for exposure, not classified for relevance. All ten feed candidates
use their existing publisher excerpts, verified against the raw feed snapshot.
These excerpts may be incomplete; full linked articles were **not fetched**.
Coverage, omissions, publication/retrieval dates, snapshot paths and hashes are
visible. Titles, URLs and all source instructions are untrusted data.

The model is asked for a specific approved need, grounded source observation,
exact supporting quote/source/passage IDs, a conditional application hypothesis,
limitations, missing information, explained priority, question and bounded next
step. No tool execution, private project access, verified suitability claim or
automatic action is allowed. Validation rejects unknown candidate/source/passage
IDs, non-exact quotes, missing grounded positive hypotheses, unsupported result
fields and invalid existing-investigation links. This checks structure and
textual grounding, not independent semantic truth or factual correctness.

Existing-investigation membership is resolved from registered canonical URLs,
not titles. Valid follow-ups must acknowledge the saved 1/4 pilot and Defer
decision; proposals are tagged as follow-ups rather than new investigations.
Failed existing-source assessments still show the registered relationship,
original findings/decision and failure; no duplicate proposal is manufactured.
There are no article-specific exceptions, gaming blacklist or forced positive
classifications.

Successful assessments automatically persist `agent_prepared_pending_human_review`
proposals through the existing app-owned official H-MEM adapter. Optional notes
and selection records are separate; `human_approval` remains null. A proposal
contains the source, dates, assessment, question/next step, context/source cache
identity and provenance. Original rule assessments and earlier semantic outcomes
remain available in history. Publication/source events are not invented for a
policy, model or presentation change.

## Bounds, caching and failure behavior

At most three requests total for this authorization; five candidates/batch;
6,000 maximum output tokens/request; 180-second socket timeout; 1 MB maximum
response; 100,000 maximum prompt characters. Proxies and redirects are disabled
for bounded model transport. No test prompt, retry, extraction experiment or
fourth request was sent. Transport failure stops further automatic batch sends.
A durable pre-send reservation consumes budget even if the process is interrupted.

Successes and failures are cached. Unchanged replay via
`python scripts/assess_discovery.py --live` returned from cache without asking
for a token or sending a model request. The audit additionally used a requester
trap that would fail on any model invocation and confirmed unchanged H-MEM
state. New content/context does not reset the allowance; new work remains
pending/budget-exhausted until separately authorized. Review, reopen, source
comparison and restart do not themselves call a model. There is no scheduled
monitoring or automatic investigation.

## Verification outcomes

| Check | Actual outcome |
| --- | --- |
| `test_semantic_discovery.py` | **7 passed**: grounded hypotheses/unsupported benefits, ambiguous source instructions, exact identities/quotes, existing investigation, automatic proposals/optional notes, persistence/cache/context changes, failures, interruption and three-batch quota, bounded transport |
| `test_update_discovery.py` | 6 passed |
| `test_relevance_policy.py` | 5 passed; historical-rule behavior and preservation only, not current semantic reasoning |
| `test_analyze_sources.py` | 21 passed; existing helper/configuration regressions |
| `test_nextwise_app.py` | 9 passed |
| `test_decision_workflow.py` | 6 passed |
| Real Chrome + isolated HTTP/H-MEM + explicit synthetic model fixtures | **13 passed**, including proposals prepared before selection, optional empty note, persisted review, unchanged checks and full process restart |
| Real Chrome + authenticated live Zetaris/H-MEM | **18 passed**, including actual cached outcomes/failures, exact quotations, automatic proposals, optional notes, existing-investigation links, usage/quota, all six reconciled tables and genuine Defer Version 1 |
| `verify_semantic_discovery.py` | Passed: original source fields, snapshots, first-seen dates, revisions, baselines/events and prior assessments unchanged; validated source quotes/context cache checked; zero-call replay |
| `verify_discovery_preservation.py` | Passed: original input/CSV hashes, old manifest artifact identities, genuine Defer Version 1 hash |
| Node syntax, Python compilation, `git diff --check` | Passed |

Browser evidence: [isolated checks](isolated/browser_checks.json),
[live checks](live_browser_checks.json). Fixture model responses are explicitly
synthetic; they are not counted as live model calls or evidence of real model
semantic accuracy. The positive grounded path and existing-source follow-up
generation passed in fixtures; they did not validate live for the failed sources.

Initial live UI checks exposed discovery context reads monopolizing the shared
investigation lock until the original ten-read retry limit expired. Sequenced
initial discovery after investigation/decision reads, delayed discovery while
those reads run, and bounded retries for explicit decision-history busy reads.
The final 18-check live run passed after that correction. These are local read
retries, not model retries. A stale server prevented the first backend restart;
verified and stopped only that Nextwise process, then the user privately
re-entered the Zetaris key. The exclusive listener prevented a duplicate server.

No new public-source discovery fetch or linked-article retrieval was performed
during semantic preparation. No real human proposal was selected for a test:
selection/restart persistence was exercised in isolated storage, and live
reopening verified the two unapproved proposals. Registration definitions were
not independently re-queried; all six table contents and lineage were reconciled,
and no registration write was issued. Unrelated historical model/pilot suites
and additional model attempts were not run.

Original evidence, pilot scores, pending reviews, genuine Defer Version 1, source
snapshots, old H-MEM manifests, six registrations and upstream code remain intact.
No AI Raw Gourmet implementation, recipes, private prompts or data were accessed.
No credentials were printed/saved, no infrastructure installed, and no commit or
push was performed. H-MEM remains non-transactional; history grows within the
existing bridge's per-checkpoint input limit without automatic pruning.
