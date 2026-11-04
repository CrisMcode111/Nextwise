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

Production transports are connected through `project_adapters.configured_services`.
They remain off until `NEXTWISE_PROJECT_PROVIDERS_ENABLED=true`. No configuration
was enabled and no actual credentials were changed during implementation.

For native Python, set protected `TAVILY_API_KEY_FILE` and
`NEXTWISE_METERLESS_TOKEN_FILE` paths. The files must contain the replacement
service key and runtime bearer token respectively, one line each. Do not put their
values in shell commands or Git. Provider keys remain inside Meterless; its runtime
token is a separate credential. Startup/list/reopen do not read either file.

Set `NEXTWISE_METERLESS_URL` to the origin (without `/v1`), using HTTPS or loopback
through a private tunnel, and `NEXTWISE_MODEL` to the approved model. Plain HTTP
to a remote hostname is rejected before the token is read. The existing bounded
`analyze_sources.request_claims` sends one schema-constrained completion, without
redirects, proxy discovery, tools, retries or format fallback. Incomplete/refused,
tool-bearing or credential-echoing answers are rejected. Existing source and
business validators still decide whether the result may be persisted.

The Tavily adapter reuses basic search (up to five leads) and `public_page` with
public-DNS pinning, redirect rejection and bounded downloads. It sends only the
reviewed query; the model receives the reviewed brief and saved evidence. The UI
discloses these transfers and requires confirmation on each external action.
API clients must supply `authorize_external_request: true` for discover/assess.

`NEXTWISE_PROJECT_SEARCH_LIMIT` defaults to 2 and
`NEXTWISE_PROJECT_ASSESSMENT_LIMIT` to 4 (each accepts 1..100). These bound lifetime
attempts per project, including failed/interrupted requests, across backend restarts.
They are not an account-wide monetary budget: set account/provider spending limits
before enabling. No background calls follow a briefing or decision. A successful
request replay returns its saved result without a new approval/call.

Tests can explicitly supply `Projects(..., searcher=..., fetcher=..., assessor=...)`
or `State(..., project_services=...)`; explicit `{}` disables transports. There is
no simulated default. Tests mock providers, not evidence validation or persistence.
Provider usefulness, model schema support, usage and cost remain unverified live.

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
python -B -m unittest discover -s tests -p test_project_adapters.py -v
python -B -m unittest discover -s tests -p test_runtime_process.py -v
```
