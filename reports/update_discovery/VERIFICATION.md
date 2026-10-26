# Update-discovery milestone verification — 26 October 2026

Implemented the manual application workflow from `docs/update-discovery-handoff.md`.
Discovery and persisted investigation proposals use an app-owned adapter to the
unchanged official H-MEM implementation, in the separate `update-discovery`
namespace. The original investigation, human choices, collector registry and
analyzer draft destinations are not discovery write targets.

## Actual bounded public run

Run `ef992d6e-30a0-4596-8775-647f85c76f6c`, started **10:30:17 UTC**:

| Source | HTTP | Result |
| --- | --- | --- |
| NVIDIA Nemotron blog fixed page | 200 | Readable baseline |
| NVIDIA Build model card fixed page | 200 | Readable baseline; publication date unknown |
| Meterless engines fixed page | 200 | Readable baseline; publication date unknown |
| NVIDIA blog feed | 200 | Valid RSS, 18 eligible unique items; capped at 10 |

Exactly four resources fetched, with no linked-article retrievals. Saved three
page baselines and ten **initial inventory** observations, not newly detected
releases. Six candidates had potential keyword relevance; seven had low
relevance. No live proposal selection, model request, extraction run, project
access or investigation replacement occurred. Public-source metadata/hashes:
[live_run.json](live_run.json). Raw snapshots remain in ignored runtime storage.

## Verification performed

| Check | Actual outcome |
| --- | --- |
| `python -m unittest discover -s tests -p test_update_discovery.py -v` | 6 passed |
| `python -m unittest discover -s tests -p test_nextwise_app.py -v` | 8 passed |
| `python -m unittest discover -s tests -p test_decision_workflow.py -v` | 6 passed |
| `python -m unittest discover -s tests -p test_investigation_memory.py -v` | 8 passed, including pinned upstream bytes |
| `python -m unittest discover -s tests -p test_extraction_memory.py -v` | 1 passed; persisted fixtures only, no extraction execution |
| `node --check web/app.js`, Python compilation and `git diff --check` | Passed |
| `python scripts/check_discovery_browser.py` | 10 real Chrome checks passed; isolated HTTP and official H-MEM |
| Existing `check_decision_browser.main()` with output redirected to this milestone directory | All 19 behavioral assertions passed; command then failed during temporary Chrome-profile cleanup because a cache file remained open on Windows |
| `python scripts/verify_discovery_preservation.py` | Original artifact/CSV hashes, both old manifests' artifact identities and genuine Defer Version 1 hash verified |

Fixtures cover first inventory, unchanged and markup-only content, duplicate
GUIDs/canonical links, item caps/lookback, meaningful page differences and
old/new hashes, explained relevance including low relevance, malformed RSS,
partial failures retaining baselines, raw snapshots, candidate selection,
idempotent retry and process restart. They also check unapproved URL/redirect
rejection, redirects/counts, byte limits, transport timeouts, session/origin
protection, overlap rejection and polling during persistence.
Proposal saves reject a revision that changed after it was displayed, so a
selection reason cannot silently attach to another tab's newer source revision.

Real browser checks verify existing investigation preservation, progress and
disabled action, server-side overlap rejection, first inventory/low relevance,
explicit persisted proposal with untrusted text rendered safely, unchanged
repeat check, invalid selection, full Python/Node restart, mobile layout and no
uncaught JavaScript errors. See [browser_checks.json](browser_checks.json) and
[decision regression assertions](decision_regression/browser_checks.json).

Earlier browser attempts exposed and led to fixes for polling colliding with
the bridge write lock and clicking before the initial history read completed.
A test polling expression was also corrected to tolerate a new document's
initialization during restart. The final discovery browser run exited cleanly.
The first sandboxed Chrome connection was reset; browser checks subsequently
ran with the required execution permission. Busy selection requests now consume
their bounded JSON body before rejecting overlap, avoiding Windows connection
resets caused by unread request bytes.

## Preservation and limits

[preservation.json](preservation.json) records eight original input hashes, six
CSV snapshot hashes, old H-MEM manifest identities and the existing genuine
**Defer Version 1** without exposing its rationale. Upstream vendor files,
original evidence, pilot scores, pending reviews, manifests and registrations
were not edited. No import, registration, upload, analyzer or pilot write path
was invoked. Pre-existing `.gitignore` and `.gitattributes` changes were retained.

Authenticated live Zetaris browser checks were **not run**: the existing app on
port 8765 was unavailable, and no private key was requested or accessed. The
historical live decision script also assumes an undecided investigation and
must not be used to erase or replace the genuine Defer decision. Integration
regressions used saved H-MEM and isolated SQL fixtures; six live registration
definitions were not independently re-queried. The 19-assertion decision browser
command's Windows cleanup error remains reported above; it was not a behavioral
assertion failure. Unrelated historical/model-execution suites were not run.

This is manual, bounded discovery only. Static readable page content can include
navigation noise and omit JavaScript-rendered content. Feed summary changes do
not establish full article changes. Missing/invalid/future dates are excluded;
the top-ten/recent window can omit items. Source dates and claims are unverified.
Deterministic relevance is provisional keyword/rule matching, never Nemotron
reasoning or verified suitability. Selection persists a **proposal**, not a
completed investigation, and launches nothing. No scheduled monitoring exists.

History is append-only through H-MEM checkpoints and immutable run snapshots.
The existing bridge's 2 MB input ceiling can eventually prevent another save;
the UI reports a failure and keeps the last confirmed baseline. There is no
automatic retention cleanup, transactional crash recovery or infrastructure
installation. No commit or push was performed.
