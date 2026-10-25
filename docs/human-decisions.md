# Human decisions in Nextwise

From `C:\Users\crist\Desktop\Nextwise`, start the app with:

```powershell
python .\scripts\nextwise_app.py
```

Open http://127.0.0.1:8765 and enter the Zetaris key privately in that
PowerShell window. The key remains in server memory. Restarting requires
entering it again; saved decision history can be retrieved without that key.
No new runtime dependencies are required; the existing Python, Node and
official H-MEM reference are used.

## Recording your choice

Load the live investigation. Beside the existing AI proposal, **Your decision**
offers Adopt, Test, Defer and Reject with no default. Select one and write your
rationale. You may add a next action or a condition for reconsideration.
Only **Save my decision** writes a record. Success appears after the official
store has persisted it and a new store instance has read back its ID and hash.

The saved panel shows your exact text, UTC timestamp, evidence links and version.
**Amend my decision** creates another version. Earlier versions and their
original evidence references remain accessible under **Decision history**.
If another tab saves while you are writing, refresh history and explicitly
acknowledge its latest version before retrying your amendment.

Your choice does not approve evidence reviews, verify publisher claims, authorize
model calls, experiments or deployment, or change the AI proposal. The historical
investigation/recommendation decision values remain null and the reviews remain
pending. The six Zetaris tables remain unchanged. The actor identifies the local
user; this is a single-user loopback app, not an authenticated multi-user audit
system.

## Persistence and integrity

`scripts/decision_records.ts` is app-owned and invoked by the existing bridge.
It calls the unmodified official `HMEM.add`. Records live alongside the imported
artifacts in:

```text
data/memory/hmem/nemotron-lightning-requirements-extraction/state.json
data/memory/hmem/nemotron-lightning-requirements-extraction/ledger.jsonl
```

Each `nextwise.human-decision.v1` record has a UUID, UTC timestamp, version,
series ID, project/investigation/run IDs, exact user choice/rationale/optional
action, request ID and digest, previous version ID/digest, and manifest ID/hash.
Its eight references include evidence draft, review and completed pilot, plus
the profile, investigation, sources, use case and recommendation. Each records
the official memory ID, original artifact path and exact-byte SHA-256. A sorted
JSON digest protects the decision envelope; manual provenance and official
`derivedFrom` links connect it to the manifest and artifacts. Amendments link
the previous decision and never replace its content.

The existing exclusive `nextwise.lock` covers reads and writes. Saves re-read
live Zetaris data and reconcile it with H-MEM, require the displayed manifest/
run/hashes and expected decision head, and verify the original allowlisted
artifact file hashes. Browser submit guards, request-ID deduplication and
identical-content detection prevent duplicate versions. A retry after a lost
acknowledgment returns the existing record. Changed text with the same request
ID fails. No key is sent to H-MEM.

History checks the record digest, version chain, provenance, original referenced
artifact bytes, current snapshot IDs/hashes, referenced manifest and current
allowlisted file hashes. Missing/changed evidence visibly marks the decision
**Needs review** without rewriting it. Known live reconciliation failures also
mark the displayed history for review. Referenced artifacts open through a
session-protected `text/plain` endpoint. Untrusted user/artifact text is rendered
with DOM text operations, never interpreted as HTML.

## Recovery and limits

If a save fails, the current page retains your choice, rationale and action for
retry. Keep that page open. Unsaved drafts are held only in browser memory and
are lost on a full reload; they are deliberately absent from browser storage.
Saved records survive page reload and full app/Node process restart. If success
was uncertain, refresh history before writing a different amendment.

If evidence is unavailable, history remains readable where the decision record
itself passes integrity checks. New saves require a fully reconciled live load.
If a decision envelope or version chain is damaged, the app reports an integrity
error rather than claiming the investigation is undecided or overwriting it.

The official reference persists JSON and an append-only ledger with synchronous
file writes; it is not a transactional, crash-atomic database. Read-back confirms
ordinary persistence, not protection against power loss or disk corruption.
Stop the app and other bridge processes before backing up the complete
investigation directory. Keep state and ledger together. For a stale lock,
inspect its PID and ensure no owning bridge is active before removing only that
lock. Do not delete state or re-import as a substitute for recovering history.
Recover corrupt storage from a consistent backup with the app stopped; retain
the damaged files for inspection. The app never automatically clears stale
locks or reconstructs decisions from the ledger.

## Reproducible checks

```powershell
python -m unittest discover -s tests -p test_decision_workflow.py -v
python -m unittest discover -s tests -p test_nextwise_app.py -v
python scripts/check_decision_browser.py
python scripts/check_decision_live_browser.py
```

The first and third commands import copies of the eight existing artifacts into
clearly marked OS temporary storage. Saves contain explicit fixture labels.
The browser checker runs an offline SQL fixture server on port 8767, installed
Chrome with an isolated profile on debugging port 9224, and the actual official
H-MEM bridge. It never saves to port 8765 or production memory. Test tools reuse
installed `websocket-client` and Chrome. Results are written to
`reports/decision_workflow/browser_checks.json`.

The fourth command checks the running real app and its live integrations without
typing or submitting a decision. Enter the key privately in the app console
first. It saves a separate sanitized report and desktop/mobile screenshots.
