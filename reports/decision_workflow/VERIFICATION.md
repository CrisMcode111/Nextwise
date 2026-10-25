# Human decision workflow verification

Verified on Windows with the installed Python 3.11, Node 24 and headless Chrome.
No new dependencies were installed. Test decisions were saved only to clearly
labelled temporary H-MEM stores. No decision or approval was fabricated in the
real investigation.

## Backend

`python -m unittest discover -s tests -p test_decision_workflow.py -v`
passed **6/6** tests. They exercise the actual official H-MEM bridge in fresh
Node processes and check exact Unicode/multiline rationale persistence, stable
IDs, UTC timestamps, project/run identity, all eight evidence references,
duplicate retries, changed-content retry rejection, stale-head rejection,
identical amendment deduplication, version chains, original content preservation,
required fields and explicit action, changed run context, failed-save lock
recovery, exact referenced artifact retrieval, missing/tampered evidence flags,
corrupt-decision failure, Origin/session protections and sanitized HTTP errors.

`python -m unittest discover -s tests -p test_nextwise_app.py -v`
passed **8/8** existing tests. These reconcile all live-table-shaped offline
fixtures with official persisted H-MEM, preserve the original pilot outputs and
1/4 result, reject mixed investigation/run/hash identities, and check existing
authentication, service, integrity, empty and disconnect states.

JavaScript syntax, Python compilation and `git diff --check` also passed.

## Real browser checks with isolated storage

`python scripts/check_decision_browser.py` passed **19/19** checks.
See [machine-readable results](browser_checks.json).

These use the real local HTTP handler, browser UI and official H-MEM persistence,
with explicitly labelled offline SQL fixtures on port 8767. They cover no default
choice, required rationale, no save on typing, explicit save, disabled concurrent
editing, real lock-induced save failure with exact draft preservation, successful
retry, double submission, plain-text markup/quotes/newlines/Unicode, eight evidence
links, reload recovery, amendments/history, full Python/Node server restart,
mobile overflow, missing-evidence warnings and blocked saves, and browser errors.
Two additional clean reloads check response-body preservation.

Earlier runs exposed a startup lock race between loading and history retrieval,
and intermittent failure while Chrome read an initial response body. History now
loads sequentially after the investigation request. The server uses HTTP/1.1
with explicit Content-Length responses. The final run passed all checks,
including repeated clean loads, reload after saving and full process restart.
Fixture mutation uses explicit UTF-8 on Windows; no source artifacts are edited.

## Live read-only check

`python scripts/check_decision_live_browser.py` passed **9/9** checks on the real running app,
live Zetaris rows/aggregates and existing official H-MEM artifacts. See
[live results](live_browser_checks.json), [desktop](live_desktop.png) and
[mobile](live_mobile.png).

The live check confirms all three sections, the separate human panel beside the
pending AI proposal, all six table reconciliations, eight memory links, unchanged
pending review and historical null decision, original 1/4 pilot result, resolved
internal evidence links and mobile layout. It never fills or submits the form.
The real decision history was empty during verification.

## Remaining limits

Official reference JSON/ledger persistence is synchronous but not transactional
or crash-atomic. Tests demonstrate ordinary restart recovery, not power-loss or
disk-corruption recovery. Corrupt record/chain storage fails closed and needs a
consistent backup; stale locks are never automatically removed. Unsaved drafts
survive a failed request in the current page, but not a full reload. The actor
is the local user, not a separately authenticated person. See
[startup, persistence and recovery](../../docs/human-decisions.md).

Original artifacts, upstream H-MEM code, exported CSVs and Zetaris registrations
were not changed. Existing `.gitignore` and `.gitattributes` changes were preserved.
No models, experiments, deployment, Git commit or push were performed.
