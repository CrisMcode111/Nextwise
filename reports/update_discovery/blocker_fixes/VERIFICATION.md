# Discovery blocker fixes — 26 October 2026

Both blockers are corrected. The authenticated application is running with one
listener on `127.0.0.1:8765`, live Zetaris/H-MEM reconciliation, revised discovery
assessments and the genuine **Defer Version 1**.

## Conservative relevance and migration

The former policy accepted individual words as evidence of a connection. That
incorrectly treated an ambiguous “extraction mode” and generic “deployment” as
requirements-extraction and integration signals.

Policy **`context-phrases-v2`** requires supporting phrases within a sentence
and a bounded proximity window. It recognizes structured-output capabilities
with a language-model or explicit user-requirement extraction context; concrete
language-model API/cost/resource integration questions; and constrained recipe
generation/adaptation capabilities. Generic words and product names do not
qualify by themselves. No article, title, URL or gaming blacklist is embedded in
the policy. Negated, excessively distant and overly long contexts are declined.
These conservative rules can miss useful candidates; they are provisional
triage, not semantic understanding or verified suitability.

All **13** saved candidates were reassessed: **8 uncertain relevance**, **5 low
relevance**. The observed ambiguous candidate now has no relevance matches and
an explicit insufficient-context explanation. No candidate was forced into a
positive classification. Positive structured-output and model-integration
fixtures establish that supported capabilities still qualify.

Original assessments remain byte-for-value identical in assessment history,
tagged `legacy-keywords-v1`; unknown original assessment times remain unknown.
New history entries include the policy, assessment time, approved context and
source revision hash. Reopening discovery migrates stale policies once; repeat
reads do not create further checkpoints. Source changes can add a new assessment
without dropping prior ones. A separate reclassification banner identifies the
policy-only change. Publication dates, first-seen dates, raw snapshots, source
fields/revisions, baselines, discovery runs/events and existing proposals were
not altered. Proposals retain their selection-time assessment.

Audit: [migration_audit.json](migration_audit.json). It compares the original
official H-MEM discovery checkpoint with the current one and validates actual
raw snapshot hashes. An isolated copy replayed the actual saved source bytes at
the original retrieval time: **zero new/changed-source events**, unchanged
assessment history and proposals, with production discovery state unchanged.

## Connection diagnosis and restoration

Initial `/api/status` reported an in-memory credential, while `/api/load`
returned **503 / zetaris**. Docker Desktop was stopped; its engine pipe was
absent. Started the existing per-user Docker Desktop installation. The existing
driver initially exited with a WSL bind-mount “not a directory” startup error;
starting that same container succeeded. Restarted the existing API after driver
recovery. API, driver, UI and PostgreSQL became healthy; completed init/bootstrap
containers were left intact.

The remaining stale failures exposed **multiple Nextwise Python processes
listening on the identical Windows loopback port**. Windows address reuse had
allowed requests to reach an older instance after a restart. Verified process
identities using script-name booleans (no command arguments exposed), stopped
only the older Nextwise instances and retained the latest privately
authenticated instance. Its `/api/load` returned **200** and reconciled all six
tables with the eight original H-MEM artifacts.

New application starts use an exclusive listener. A production-start attempt
while the authenticated app was running refused the occupied port cleanly,
requested no credential and left the single existing listener intact. Safe SQL
failure diagnostics now expose only fixed categories or HTTP status, never raw
exception text, API response contents or credentials.

Private credential entry occurred only at the console's hidden prompt. No
credential was printed, saved, read from a file or extracted from another
process. Docker volumes, existing containers and six registrations were not
recreated; no registration/import/upload/write workflow was invoked.

## Actual verification outcomes

| Check | Final outcome |
| --- | --- |
| `python -m unittest discover -s tests -p test_relevance_policy.py -v` | **5 passed**: ambiguous contexts, supporting structured outputs, concrete model integration, constrained recipes, preserved migration/history/proposals/restart/dedup |
| `python -m unittest discover -s tests -p test_update_discovery.py -v` | **6 passed** |
| `python -m unittest discover -s tests -p test_nextwise_app.py -v` | **9 passed**, including exclusive/legacy duplicate-bind rejection |
| `python -m unittest discover -s tests -p test_decision_workflow.py -v` | **6 passed** |
| Existing discovery browser checker with `OUT` redirected to `blocker_fixes/isolated` | **10 passed**, real Chrome/HTTP and isolated official H-MEM, including explicit proposal persistence, unchanged checks and full process restart |
| `python scripts/check_discovery_live_browser.py` | **13 passed**, real authenticated application and live Zetaris |
| `python scripts/verify_relevance_migration.py` | Passed: original checkpoints/snapshots preserved, migration idempotent, actual-source replay produces zero events |
| `python scripts/verify_discovery_preservation.py` | Passed: original artifact/CSV hashes, both old manifests' artifact identities and genuine Defer Version 1 hash |
| `node --check web/app.js`, Python compilation, `git diff --check` | Passed |
| `python scripts/nextwise_app.py` while live app occupies port | Clean refusal, no credential prompt, original authenticated listener retained |

Browser evidence: [isolated checks](isolated/browser_checks.json),
[live checks](live_browser_checks.json). The live checks verify the combined
discovery/investigation view, “Live data · Memory linked”, all six reconciled
tables, original 1/4 pilot score and pending review, genuine Defer Version 1
without review warnings, versioned uncertainty/history, reload consistency,
mobile layout and absence of uncaught JavaScript errors.

Initial failures were real and are described above: unavailable Docker engine,
driver startup mount error and repeated generic application 503s while stale
listeners remained. A default system-wide Docker executable path did not exist;
the actual per-user installation was located and used. Some initial restricted
Docker/process-inspection calls required execution permission. One ad hoc
no-credential probe had a shell-quoting syntax error; its corrected version
confirmed the API's expected unauthorized response. Final checks listed above
passed; no unresolved behavioral test failure remains.

No new public-source fetch was run during these fixes: migration used saved
content, and unchanged-source behavior was tested with exact saved-byte replay
and fixtures. The live discovery store has **zero proposals**; persistence of a
created proposal and full restart were tested in isolated storage, not by
creating a fictitious real selection. Live proposal-list reopening was checked
without changes. Registration definitions were not independently re-queried;
all six live table contents and H-MEM lineage were reconciled, and no definition
write was performed. Unrelated historical browser/model-execution suites were
not rerun.

No models, extraction pilot, private AI Raw Gourmet access, original evidence
edits, upstream edits, infrastructure installation, commit or push occurred.
Earlier reports and pre-existing workspace changes were retained.
