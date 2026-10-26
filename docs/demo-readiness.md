# Demo readiness

## Opportunity workflow — offline implementation

The missing discovery-to-decision connection now has an offline implementation.
From a validated candidate choose **Prepare opportunity briefing**, review the
prominent **Your next opportunity** panel, explicitly choose Adopt/Test/Defer/Reject
and supply your rationale, then **Save my opportunity decision**. Reopen saved
discovery after restart to see the recommendation, decision and evidence history.
Briefing preparation, selection and decision saves send no model/source request.

Briefings preserve source observation kinds: an initial inventory or page baseline
is not presented as a new release. Practical value is copied only from the validated
assessment's labelled hypothesis; risks and evidence gaps remain explicit. A
conservative policy derives the recommendation: Test for potential relevance on
a new investigation, Defer for uncertainty or an existing-investigation
continuation, Reject for low relevance. Adopt remains a human option, never an
inferred endorsement. This policy is not a new Nemotron response.

New opportunity choices have their own versioned, hashed H-MEM history with exact
briefing/assessment/snapshot/context references. They do not amend the old pilot
manifest or genuine Defer Version 1. Stale evidence, changed context, invalid
quotes and rejected assessments block preparation/new decisions. Historical
briefings remain accessible; no new pilot, research or deployment is launched.

**Not yet a successful real product demonstration.** Offline fixtures exercise
the connections, not real project reasoning. Existing live relevant assessments
remain rejected. The minimum real test, requiring separate explicit authorization,
is one bounded request for the existing saved Nemotron source using the current
contract and complete selected paragraphs. It must pass unchanged validation
including its existing-investigation/pilot/Defer connection. Then prepare its
briefing in the actual app, inspect the real benefits/risks/quotes, let the user
explicitly decide, and verify its persisted history after restart. An unchanged
saved-source replay should produce no new discovery event or model request.
Rejection remains a failed test, not a reason to relax validation. A new public
fetch is only needed to demonstrate fresh discovery, and needs separate approval.

Offline verification commands:

```powershell
python -B -m unittest discover -s tests -p test_opportunity_workflow.py -v
python -B -m unittest discover -s tests -p test_semantic_discovery.py -v
python -B -m unittest discover -s tests -p test_update_discovery.py -v
python -B -m unittest discover -s tests -p test_decision_workflow.py -v
python scripts/check_discovery_browser.py
```

The browser check uses an isolated temporary official H-MEM store and synthetic
transport, starts only a temporary local fixture server, and blocks requests
outside that fixture origin. It does not query the real Zetaris/Nightshift services.

## Semantic proposals — current state, 26 October 2026

Nextwise now uses the existing Meterless/Nemotron path for semantic project
reasoning, with the approved profile/use case, existing investigation, original
pilot findings and genuine Defer Version 1. The rule policies described below
are historical. The user no longer writes the agent's rationale: validated
assessments with a bounded investigation question prepare persisted agent proposals, and the UI offers
**Review and select agent proposal** plus an **Optional user note**. Selection
is separate from approval and starts no investigation or trial.

The three-request live allowance is **exhausted**. All three calls returned
`nvidia/nemotron-3.5-lightning-30b-a3b`: 32,650 prompt tokens, 5,680 completion
tokens, 38,330 total. Two assessments validated, both low relevance, and produced
two agent proposals. Eleven remain uncertain because responses failed
validation; this is **partial live semantic validation**, not a successful
assessment of all thirteen candidates. Those are the original run's results.

A separately authorized one-request reassessment of the Nemotron blog and gaming
feed item has also completed: HTTP 200, the same returned Nemotron model, 8,612
prompt + 866 completion = 9,478 tokens. **Neither assessment validated**. Both
omitted `source_observation`; the blog also omitted its required existing-pilot/
Defer linkage, and the gaming quotation changed an ellipsis. Rejected drafts
remain uncertain and produce no new proposal. The separate allowance is now
exhausted; no retries or extra model calls were sent. Exact source/quote checks
were not relaxed to make the demonstration pass. See the
[controlled request and offline replay](../reports/update_discovery/controlled_reassessment/VERIFICATION.md).
The shared contract now explicitly supplies types/enums/limits; low relevance
may have no investigation question and creates no unnecessary proposal. The two
historical low-relevance proposals from the original run are preserved.

Expand a candidate for its project need, source observation and exact supporting
quote/provenance, untested application hypothesis when justified, limitations,
missing information, explained priority and proposed question/next step. Failed
candidates show their failure and source coverage rather than a rule-based
fallback. Existing-investigation sources link to the saved 1/4 pilot, its
limitations and Defer decision; no duplicate work is launched. Paragraphs come
from existing snapshots or available feed excerpts, not freshly fetched linked
articles. Limited coverage and unverified suitability remain explicit.

Cache replay, reopening and selection make no model call. Source/content and
project-context changes invalidate the cache but do not reset authorization.
All original evidence, scores, prior assessments, raw snapshots, dates, source
events, old manifests, Defer Version 1 and registrations are preserved. Detailed
passed, failed and unrun checks:
[semantic verification](../reports/update_discovery/semantic_assessment/VERIFICATION.md).

## Earlier discovery verification

## Update-discovery milestone — 26 October 2026

Both observed blockers were corrected and verified against the authenticated
live application. Relevance now uses **`context-phrases-v2`**, with supporting
phrases rather than isolated keywords. All 13 saved candidates were reassessed:
**8 uncertain, 5 low relevance**. The ambiguous extraction/deployment candidate
has no claimed task connection. Earlier assessments remain in history; source
snapshots, first-seen dates, revisions, baselines and discovery events did not
change. Insufficient context is explicit; triage remains provisional.

The connection failure involved stopped Docker services, a driver startup mount
failure and multiple stale Nextwise processes sharing Windows port 8765.
Existing containers were restored and only stale app processes stopped. A single
authenticated instance now reconciles all six tables with H-MEM and displays
the genuine **Defer Version 1** without review warnings. New starts use exclusive
port binding. Credentials were privately re-entered and remain only in memory;
Docker volumes and registrations were not recreated.

Current verification: **26 backend tests**, **10 isolated discovery browser
checks**, **13 live browser checks**, migration preservation audit and saved-byte
unchanged-source replay passed. Proposal persistence and restart were exercised
in isolated storage; no real proposal was created. The original live source run
below was not repeated during this fix. See
[blocker-fix verification](../reports/update_discovery/blocker_fixes/VERIFICATION.md)
for passed, initial failed and unrun checks. The initial category counts below
record the superseded keyword policy, not current classifications.

The existing application now offers **Check for updates** and **Reopen saved
discovery**. Restart the local Python app to load the new backend, reopen its
local page, then choose **Check for updates**. Discovery works before private
Zetaris key entry; reconnect as usual to show the existing investigation.
Expand **Approved source scope and limits**, a saved candidate, its relevance
explanation and revision history. Enter a selection reason and choose **Create
investigation proposal**; reopen it under **Persisted investigation proposals**
after restarting. The original investigation and human decision remain separate.

The bounded live public check returned HTTP 200 for all three fixed pages and
the NVIDIA feed. The feed was verified in this environment as RSS with **18**
eligible items; the app retained the capped **10-item initial inventory** and
three monitored-page baselines. This is not an announcement of ten new releases.
There were six potential-relevance and seven low-relevance candidates, all
explicitly provisional keyword/rule matches. No real proposal was selected.

Discovery uses only the approved three fixed pages and NVIDIA feed, at most
10 recent items within 14 days, 2 MB/source, 8-second socket timeout, 20-second
read deadline (plus at most one blocked socket read) and three approval-checked
redirects. Linked articles are not downloaded. Only static readable HTML and
RSS titles/summaries are compared; no JavaScript rendering, factual verification,
semantic suitability assessment, scheduled monitoring or automatic investigation
is provided. Feed dates and publisher content are untrusted. Partial coverage
and storage errors are visible, and last successful baselines remain available.
Discovery is stored separately under `data/memory/hmem/update-discovery/`,
using the official H-MEM adapter and locks. Back up the entire directory privately
with the app stopped; history grows and the existing 2 MB bridge-input ceiling
can eventually prevent new checkpoints. H-MEM is not crash-atomic.

Verification evidence and exact commands:
[update discovery verification](../reports/update_discovery/VERIFICATION.md).
The original artifact/CSV hashes and genuine **Defer Version 1** are preserved.
The following readiness section records the earlier demo state; its statements
about being undecided predate the genuine human decision.

## Earlier demonstration verification

**READY for the bounded local demonstration on 26 October 2026.** Verified on
25 October: **14 backend tests, 19 isolated decision checks, 30 live interface
checks and 9 live read-only decision checks passed**. Saving, failed-save retry,
history and full process-restart recovery were tested in labelled temporary
H-MEM storage. The real investigation remains undecided.
Startup and recovery: [root README](../README.md).

## Blockers and limitations

**Blockers: none in the verified local setup.** Existing services, private H-MEM
state and your key entry are required. Loom and PowerPoint remain to be produced.

**Nonblocking limits:** one local investigation/user; CSV snapshots without
automatic sync; four synthetic cases with original quality **1/4**, not production
accuracy. Pricing and baseline remain unknown, thresholds unapproved, reviews
and corrections pending. Quote matching is not factual verification. H-MEM is
not crash-atomic; unsaved drafts disappear on reload. Publisher URLs are matched
to stored links, not fetched or independently verified during playback.

## Recovery reports reconciled

Earlier in-page failures remain in [the original report](../reports/nextwise_demo/VERIFICATION.md).
Their generic network errors do not establish one cause. Later passes established
full reload and isolated restart recovery, not recovery from every outage.

This readiness run reproduced a concrete **409 / already loading** failure:
after reload, the new page could overlap the old page's H-MEM history read.
[The failing run](../reports/delivery_readiness/interface/browser_checks.json)
preserves its 28 passing checks and failed final recovery. The only application
change adds up to ten read attempts, one second apart, for that explicit busy
response. It does not retry decision writes or change evidence. The affected
[full rerun passed 30/30](../reports/delivery_readiness/interface_after_recovery_fix/browser_checks.json).
For recording, use full document reload after restoring a service; preserve any
unsaved text first. Universal unattended recovery is not claimed.

Evidence: [19 isolated decision checks](../reports/delivery_readiness/decisions/browser_checks.json),
[live read-only decision checks](../reports/delivery_readiness/live/live_browser_checks.json),
and [Git/integrity audit](../reports/delivery_readiness/git_and_integrity_audit.json).
No candidate secret literals or private runtime paths were found in current Git
candidates. Eight artifact hashes, six CSV hashes and 24 upstream files match.
The scan excludes Git history and cannot guarantee future files. Earlier reports
were preserved.

## Short recording sequence (about five minutes)

1. **Project (30 seconds):** show the approved objective, stage, constraints and
   requirements-extraction task. Explain: saved results, queried live; no model call.
2. **Question and sources (40 seconds):** show the investigation question,
   criteria, publication/retrieval dates and unknown dates. Two NVIDIA pages and
   one Meterless page are not three independent publishers or independent
   replication of NVIDIA claims.
3. **Evidence (45 seconds):** open one exact quotation. Compare original draft
   wording with pending corrections: distribution versus NIM access; trial terms
   versus model licensing. These are not human-approved facts.
4. **Saved pilot (60 seconds):** open the explicit synthetic case. Show requested
   dinner missing; `two` preserving meaning despite the numeric expectation;
   preserved `no nuts`; and 20 minutes both extracted and marked unknown. Open
   unchanged model output and evaluator findings. Explain evaluator limitations
   and the original **1/4**, keeping source-analysis metrics separate.
5. **Proposal (30 seconds):** expand the saved recommendation and rationale;
   show limiting evidence and unknowns. Its proposed follow-up is not executed.
6. **Your choice (40 seconds):** only if you genuinely decide, select Adopt,
   Test, Defer or Reject, enter your own rationale and optional action, then
   explicitly save. Show the H-MEM confirmation, date, evidence links and history.
   Otherwise show the empty panel and isolated test evidence. Never stage approval.
7. **Resume (40 seconds):** after a genuine successful save, reload and show the
   same record. Pause recording; stop Nextwise with Ctrl+C, restart using the
   README and enter the key off-camera. Resume recording, reload and show the
   same rationale, version and references. The isolated test already proved this
   path without writing a real decision.

## What the integrations actually do

| Integration | Demonstrated role |
| --- | --- |
| Zetaris | Live SQL over the six already uploaded CSV tables, numeric conversions, joins and aggregates; values reconcile with persisted evidence. No new registrations or automatic ingestion. |
| Meterless / Nightshift | The earlier source analysis and four-case pilot used the local OpenAI-compatible provider at port 8088, with the saved routing settings. This provider is separate from playback; Nightshift job queues or overnight autonomy are not wired into this interface. |
| Nemotron | The historical returned model is `nvidia/nemotron-3.5-lightning-30b-a3b`. Its saved analysis and extraction outputs are displayed; the demo makes no fresh inference calls. |
| Official H-MEM | Unmodified pinned reference used through the local Node bridge for exact artifact retrieval and versioned human decisions, with hashes, provenance, locking and restart recovery. Retrieval/confidence does not approve evidence. |

**Demonstrated:** traceable investigation playback, live data reconciliation,
saved comparisons, qualified interpretation and explicit durable human choice.
**Unimplemented:** continuous update monitoring, scheduled research, autonomous
triage/decisions, new experiment execution from the UI, production deployment,
automatic CSV sync and automatic evidence approval. No engines, UI redesign or
extraction-protocol changes are part of completion tomorrow.

## Manual actions before delivery

- Start the existing Zetaris group and Nextwise in the README order; enter the
  key in its masked console off-camera. Refresh the browser to receive the
  recovery fix. Keep the console and Docker running during recording.
- Back up the full H-MEM directory privately with the app stopped; a clone omits
  runtime state and human decisions. Preserve the file store/registrations too.
- Enter your real decision only when ready. Do not erase a saved decision or
  amend pending evidence merely to match an undecided-state test.
- Record only the browser in Loom. Build PowerPoint around project/problem,
  integration roles, evidence/pilot limits, human decision/recovery and future
  scope. Use sanitized screenshots, exclude credentials and review Git changes
  yourself, including the existing `.gitignore` and `.gitattributes` protections.
