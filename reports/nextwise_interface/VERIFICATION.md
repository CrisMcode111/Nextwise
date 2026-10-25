# Nextwise interface verification — 2026-10-25

The app launched at `http://127.0.0.1:8765` using the existing Python runtime.
The Zetaris key was entered privately through the server console, never in
the browser. The server remains available for local use until Ctrl+C.

Six backend tests passed (`tests/test_nextwise_app.py`). JavaScript syntax and
Python compilation checks passed. The backend tests included an actual call
through the official H-MEM bridge; API success/error fixtures were offline and
did not invoke models or experiments.

The installed Chrome browser was launched in headless mode using a clean
temporary profile, and 20 checks passed. The machine-readable observation is
`browser_checks.json`; successful content came from the running local app,
live Zetaris queries and official persisted H-MEM retrieval, not local reports.

Observed persisted manifest: `mem-10`. The bridge returned profile/investigation/
sources/draft/review/use-case/results/recommendation IDs
`mem-1`, `mem-2`, `mem-3`, `mem-4`, `mem-5`, `mem-7`, `mem-8`, `mem-9`.
Their exact hashes, upstream commit, run identity and live per-table checks
are recorded in the browser observation's `live_data.memory` field.

Live rows reconciled as 1 profile, 1 investigation, 3 sources, 6 claims, 1 review
and 4 cases. Displayed aggregate: 4 attempted, 4 schema-valid, 1 passing saved
quality checks, 10.378 seconds, 3200 reported tokens. These observations are
recorded test results, not constants used by the interface. Review and pilot
approvals remained pending and the investigation decision remained null.

Browser checks actually performed:

- Local page, console-authentication readiness, real loading indicator and
  disabled refresh during loading, all three connected sections.
- All four displayed headline metrics reconciled with the live SQL response.
- Every internal evidence anchor resolved. The first claim disclosure opened
  and its exact quotation matched the live data. The first pilot case opened
  and its synthetic input and original multiline output matched exactly.
- All three external source URL targets matched the live source registry;
  links were not followed and publisher-site availability was not tested.
- Persisted H-MEM manifest/artifact IDs were returned through the app.
- External-looking HTML was inserted as inert text by the actual DOM helper.
- At 390 × 844, the document had no horizontal overflow. Desktop was checked
  at 1440 × 1000. No broader device or accessibility audit is claimed.
- Authentication, memory unavailable, empty data, integrity failure and
  Zetaris-unavailable screens were exercised with explicitly injected browser
  HTTP fixtures. These were not claims of actual service outages.
- A fresh real live read restored the page after those fixtures. No uncaught
  JavaScript exception was observed.

Screenshots were captured and visually inspected:
`desktop.png`, `mobile.png`, `quotation.png`, `pilot_case.png`, and
`service_error.png` (the latter is an explicitly labeled test fixture).
`initial_state.png` records the first browser state, which may be loading
because the console key was already available when the browser opened.

All eight input artifact hashes and all six export hashes were rechecked after
verification and matched the original export manifest. Existing `.gitignore`
changes and `.gitattributes` were preserved. No original evidence, vendor code,
table registration, infrastructure or experiment was changed.

Limits: this is one local founder/investigation, with a console-entered key,
the existing pinned snapshot and experimental Node TypeScript runtime. It
does not edit or approve decisions. Network/service errors hide the content
and require retry rather than showing stale report data. Browser failure
fixtures supplement backend failure tests; they do not prove recovery from
every real Zetaris or storage failure. Startup and dependency details are in
`docs/nextwise-interface.md`.
