# Project workflow V1

The existing Python backend now exposes a separate project workspace at `/projects`.
Start it without requiring a pilot, Zetaris credentials, or an existing memory store:

```powershell
python -B scripts/serve_runtime.py --projects
```

For verification, set `NEXTWISE_MEMORY_ROOT` to a temporary copy of the existing
H-MEM root first. Startup checks Python, Node and pinned H-MEM files only. It does
not create memory, launch Meterless, load credentials, or contact services. Normal
pilot startup without `--projects` retains its existing behavior. `/projects` is
also available from the normal backend. Project mode blocks the pilot routes.

The working sequence is:

1. Save a named, reviewed project brief. V1 accepts text or already extracted TXT/PDF
   text; it does not upload or extract PDF files.
2. Submit reviewed public search terms. One search returns at most five leads;
   at most four distinct public HTTPS pages are fetched and saved. Search snippets
   never become supporting evidence. Publication dates remain unknown.
3. Request an assessment for a saved page. Existing business-context preparation,
   staged claim extraction, strict response validation and exact source quotations
   are reused. A rejected response cannot produce an accepted assessment or briefing.
4. Prepare a provisional briefing from the latest validated assessment. Validation
   establishes response structure and source attribution, not business suitability.
5. Explicitly save Adopt, Test, Defer or Reject with a rationale. The decision cites
   the exact briefing hash. Reopen after restart to retrieve its history.

Each project uses `projects/project-<UUID>/update-discovery` under the configured
memory root. Existing discovery checkpoint persistence and the official H-MEM bridge
store the project, attempts, assessments, briefings and decisions. Source bytes live
in that project's `runs/` directory. Neither pilot namespace is reused or overwritten.
Project reads do not touch access counters or append ledger entries. Project input is
immutable in V1; create a separate project for a revised brief.

Transports are disabled by default. `Projects(memory_root, searcher=..., fetcher=...,
assessor=...)` or `State(..., project_services=...)` supplies explicit adapters:

- `searcher(reviewed_query)` returns the existing Tavily search result list. A future
  authorized adapter can call `tavily_discovery.search` with its protected key.
- `fetcher(public_https_url)` returns the existing `public_page` shape: raw bytes and
  an error indicator. The production adapter must retain that function's public-DNS
  pinning, redirect rejection and size limits.
- `assessor(prepared_request)` receives the project, verified source passages, staged
  claim bank and messages, and returns the assessment JSON text. The existing model
  transport can be supplied only after explicit authorization and budget configuration.

No live adapter or simulated default is automatically selected. The UI disables
unconfigured search/assessment actions; saved briefing review and human decisions
remain available. Tests inject clearly mocked providers. Provider usefulness,
quality, credits and costs are not measured by those tests.

API: POST `/api/projects` creates a project; GET lists projects; GET
`/api/projects/<id>` reopens one. POST `/api/projects/<id>/discover`, `/assess`,
`/brief` and `/decide` advance it. Mutations require a UUID `request_id` and
`expected_version`; creation also requires `name`, `brief`, and
`reviewed_sanitized: true`. Decisions require `explicit_action:
record_project_decision`, a briefing ID/hash, `expected_head`, choice and rationale.
Requests use the backend's existing session-cookie and origin protections.

An attempt is journaled before calling an injected provider. Failed/interrupted
attempts do not silently retry; successful request IDs are idempotent. A different
payload cannot reuse an ID. A new assessment or changed source makes older briefings
stale. Concurrent amendments require the current project version and decision head.
Recording a decision authorizes no additional research, AI calls, spending or deployment.

Offline end-to-end tests use real H-MEM on temporary copies, mock search and AI,
block sockets, and compare both pilot namespaces and original memory before/after:

```powershell
python -B -m unittest discover -s tests -p test_project_workflow.py -v
python -B -m unittest discover -s tests -p test_runtime_process.py -v
```
