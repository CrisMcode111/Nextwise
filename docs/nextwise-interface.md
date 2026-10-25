# Local Nextwise interface

From `C:\Users\crist\Desktop\Nextwise`, use this single Windows startup command:

```powershell
python .\scripts\nextwise_app.py
```

Open **http://127.0.0.1:8765**. Enter the Zetaris key at the masked prompt in
the same PowerShell window, then choose **I entered the key · Connect** in the
app. Refresh performs a fresh read. Disconnect releases the server key and
clears the displayed investigation; the console prompts privately again.
Ctrl+C stops the app and clears the key. No key is entered in the browser.

## Dependencies and scope

The app uses Python 3.11's standard library, browser-native JavaScript/CSS and
the repository's existing official H-MEM bridge. Node.js with
`--experimental-transform-types` is needed for that bridge (the existing
integration was validated on Node 24.22.1). There are no new npm or Python
runtime packages, build step, web framework, external fonts or asset services.
The existing local Zetaris service and six `nextwise` registrations must be
available, along with the already persisted complete H-MEM snapshot.

The browser checker uses the already installed `websocket-client` package and
installed Chrome only as test tools; neither is required to run the app. It
launches a separate headless browser with an isolated temporary profile.

This first interface is for one local founder and the pinned existing
investigation/run. It displays saved content and queries; it does not edit
evidence, create recommendations, approve reviews, register tables, trigger
experiments, call models or access the separate AI Raw Gourmet implementation.

## What the three sections show

**My project** shows the approved profile, objective, stage, team, environment,
constraints and the specific extraction task. Baseline and verified pricing
are explicitly unknown when absent.

**Investigated update** shows the question, technology, release date, original
criteria, source links, publication dates and retrieval dates. Pages are grouped
by publisher domain so multiple NVIDIA pages are not counted as independent
publishers. Unknown publication dates stay unknown.

**Evidence & decision** displays the exact saved next-step proposal and its
pending status. A null decision displays as “not set.” Links lead to the pilot,
source-backed claims and open questions. Each claim opens its exact quotation,
original limitation and separate, pending AI-assisted correction. Quotation
matching is explicitly distinguished from factual verification and approval.

Pilot cases show original synthetic inputs from the persisted fixture snapshots,
original model output and evaluator findings from live rows, associated saved
interpretation, per-request measurements and evaluator limitations. The earlier
review's gaps/actions are identified as historical because they predate the
pilot. Existing unknowns and proposals are displayed, never silently resolved.
Technical details and the separate source-analysis measurement appear only in
the provenance disclosure, not among the extraction figures.

## Data and integrity flow

Every refresh calls `investigation_memory.call_bridge` with operation `resume`.
This invokes the unmodified official H-MEM reference through the existing
TypeScript bridge, retrieving the persisted manifest and artifact IDs. There
is no import or substitute memory implementation. The bridge checks exact-byte
artifact hashes, investigation isolation, review/draft links, fixture snapshots,
schema hashes, recommendation lineage and lifecycle state.

The app requires the persisted complete pilot/recommendation, the expected
investigation and run, and agreement with the export manifest's exact hashes
and paths. The source JSON files and saved integration reports are not loaded
as display fallbacks.

Next, all six datasets are read through live `SELECT * FROM nextwise.<table>`
queries using the established authenticated API client. Every value, key, JSON
field, quote and newline is compared with the projection of the exact H-MEM
documents. Investigation/run IDs and artifact relationships must match before
any combined view is returned. The existing numeric SQL checks and grouped
investigation query run live too. Their returned values are reconciled with
the individual live rows before figures appear. No result figures are hardcoded.

Project, investigation, source metadata, claims, review and per-case outputs
are decoded from the live rows. Persisted memory supplies the traceable original
fixtures and context absent from the six projections. The recommendation itself
comes from the live `recommendation_json` field, already matched to H-MEM.
Quote-to-excerpt occurrence is checked, with no implication of truth.

The existing manifest and reusable SQL file are read as contracts. Python's
independent expected-result calculation is validation, not a substitute for the
live Zetaris result. The interface never reads `reports/` at runtime.

## Authentication and rendering

The app binds to loopback only. The key is read with `getpass`; echoed stdin
fallback is refused. It remains in server process memory. It is absent from
HTML, JavaScript, browser storage, browser request bodies, cookies, URLs, files,
reports and logs. The app logs no HTTP requests, headers or response bodies.
No key is passed to the H-MEM subprocess. Temporary API client references are
cleared after each load. A rejected key is discarded and privately requested
again in the console.

A random HttpOnly/SameSite cookie identifies the local page; it is not the
Zetaris key. Host and Origin checks reject foreign requests. API and static
responses use `no-store`, a restrictive Content Security Policy, no-referrer,
and nosniff. Only three fixed frontend assets can be served; no arbitrary file
paths are exposed. Concurrent loads fail with a clear retry state rather than
competing for the H-MEM lock. Disconnect is serialized with loading.

Artifact text is inserted with DOM `textContent`, not HTML. External URLs are
restricted to HTTP/HTTPS and open with `noopener noreferrer`. Empty results,
authentication, loading, unavailable memory, integrity failure and service
failure have distinct states. Errors do not display stack traces, external
response bodies or cached reports.

This is a loopback development app, not shared hosting: credentials and TLS,
multiple-user isolation and deployment authentication would require a separate
design. Browser content is sensitive approved investigation material even
though the key never reaches the browser.

## Verification commands and artifacts

```powershell
python -m unittest discover -s tests -p test_nextwise_app.py -v
node --check .\web\app.js
python .\scripts\check_nextwise_browser.py
```

The backend tests use actual official persisted H-MEM retrieval and clearly
isolated offline API fixtures. They exercise matching and mismatched identities,
tampered quotations, empty data, authentication, cross-origin rejection,
disconnect, missing memory and service failures. No model is invoked.

The browser checker uses the running app and its real private-console key for
successful reads. It compares rendered figures with the live API response,
opens quotation/case anchors and compares their text, checks source URL targets,
checks an isolated mobile viewport, and captures screenshots. Browser failure
states are explicitly injected HTTP fixtures via CDP, not claimed service
outages. It then restores the page with a fresh real live read. It does not
follow publisher links or establish their availability or factual correctness.
Results and screenshots are under `reports/nextwise_interface/`.

## Evidence-led demonstration refinement

The compact introduction now places the live investigation question and the
first clause of the existing recommendation before the project section. This
short excerpt is a summary of the saved proposal, not a new recommendation.
The complete original recommendation and rationale remain expandable, with
pending approval and the unset decision visible without expansion.

Each pilot case now has a comparison table before the original JSON. Requested
facts/values come from the persisted fixture's `expected_explicit_facts`;
recorded values and verbatim input evidence come from its saved parsed output;
missing/changed/incorrect-unknown labels come from saved validation findings.
No scoring function is called. Field aliases are read from the saved scoring
protocol. Existing evaluator qualifications are shown with the affected field.
The time-limit category correspondence follows the existing evaluator's
`known_categories` mapping and only surfaces already recorded flags.

The explicit case separates omitted dinner, numeric expectation versus the
string `two` (with the saved semantic-equivalence caveat), returned `no nuts`,
and the extracted time limit also marked unknown. Additional unknown categories
are computed as a difference from the fixture's saved required list. The UI
does not claim that every extra is irrelevant or infer why it appeared.
Original model output, evaluator findings and the original quality result are
unchanged.

Publisher claims now show original draft wording next to the existing proposed
review correction before disclosure expansion. This makes distribution versus
NIM access and trial-service terms versus model licensing immediately visible.
All corrections remain labeled pending; exact quotations and detailed review
basis are still expandable.

The refinement passed 8 backend tests. Its separate browser evidence is saved
under `reports/nextwise_demo/`, preserving the original interface verification
artifacts. Browser error-state checks use explicit fixtures; the final live
recovery result is recorded separately in the verification report.
The final isolated browser run passed all 30 checks with recovery via full page
reload. Two earlier in-page recovery failures after injected HTTP fixtures are
preserved and documented in `reports/nextwise_demo/VERIFICATION.md`; their cause
remains unconfirmed. A clean two-load browser diagnostic also succeeded.
