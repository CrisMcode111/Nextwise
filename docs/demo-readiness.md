# Demo readiness — scope frozen

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
