# Project-driven tool discovery and catalog fallback

**Check for updates** now uses bounded Tavily web search when `TAVILY_API_KEY`
is available to the server, with the catalog described below as fallback. See
[Tavily discovery](tavily-discovery.md) for request limits, credit consumption
and mocked verification. No live Tavily request has been made for this integration.
Both modes include established tools without requiring a recent release date.

## Needs and source selection

The existing context loader reuses the approved profile and investigated task:
generate/adapt recipes and meal plans to user constraints, with an extraction
step that preserves explicit requirements and missing information. The prototype
is maintained by one developer with limited time; costs and integration effort
need justification. The application stack and extraction baseline remain unknown.
Discovery does not inspect proprietary code. Tavily receives fixed public search
phrases selected from project-need categories, not the project files, decisions,
rationales, proprietary recipes, credentials or original free-text context.

Local rules identify checks to investigate, not observed application defects:

| Need | Candidate source | Official page |
| --- | --- | --- |
| Structured requirement extraction | Instructor | https://python.useinstructor.com/ |
| Schema/type checks on extracted constraints | Pydantic | https://docs.pydantic.dev/latest/ |
| Evaluation of model-backed extraction | promptfoo | https://www.promptfoo.dev/docs/intro/ |

The catalog is `data/discovery_tools.json`: at most four source pages on reviewed
origins. Only sources matching project needs are fetched. Catalog entries are
starting points, not findings: the fetched page must support both the product
identity and a readable capability passage. An unrelated project task yields no
matches. Adding an origin requires reviewing the source allowlist in code.

## Manual workflow and boundaries

1. Load saved human decisions and saved discovery. Existing verified responses
   supply process-local exclusion snapshots. Missing history blocks discovery
   before any source request. Optional preview metadata never prevents readable
   historical decisions from being returned or a saved choice being acknowledged.
2. The button reuses the authenticated/origin-protected POST
   `/api/discovery/check?scope=tools`, discovery lock and progress polling through
   GET `/api/discovery?scope=tools`. These preview endpoints do not retrieve or
   write H-MEM, query Zetaris or invoke a model.
3. Catalog fallback reuses the bounded fetcher: 2 MB/source, 8-second socket timeout, 20-second read
   deadline, and at most three redirects restricted to exact selected source URLs.
   One fetch per selected source, no automatic retries, crawler or scheduler.
   An unavailable source produces no inferred candidate; successful results remain.
4. Reuse readable HTML extraction. Require a positive matching capability passage
   of 40-700 characters. Display the exact passage as description and evidence,
   with an untested project connection, source link, publisher, retrieval date
   and limitations. No publication date, performance, savings or safety is inferred.
   Web-discovered pages use the same passage criteria and reject redirects;
   they are labelled as source pages with publisher ownership unverified.
5. Exclude previously observed products using official-origin and configured-name
   matches. Reuse the latest cached human decision per subject; Reject/Defer
   records are matched through source URLs and names, including the original
   investigation technology. No automatic resurfacing: changed page bytes alone
   never count as meaningful new evidence. This version conservatively leaves
   reconsideration of deferred/rejected tools outside the preview.
6. Deduplicate URLs and tool identities; display at most three results in catalog
   project-need order. Fewer results, including zero, are valid.

Every card says **Discovery candidate — not yet validated**.
Cards have no adoption, approval or prepare-opportunity action.
They never enter the strict semantic validator or validated recommendation flow.
Source statements are publisher claims; project connections are hypotheses.

Pydantic is a validation technology, not an AI model or recipe app. Schema checks
cannot prove completeness or dietary safety. Instructor's LLM-backed extraction
would need separate model access, cost and accuracy review. promptfoo's testing
capabilities do not establish that the saved cases are integrated or sufficient.
Nothing is installed or executed by discovery.

## Preservation and limits

The official H-MEM adapter, saved human decisions, strict semantic validator,
Zetaris integration and Nightshift/NVIDIA request paths are unchanged. Existing
history/read/save workflows retain their behavior. New code caches their already
returned values; it adds no memory reads or writes. The preview itself reads
approved local project files and selected public documentation only.

The original persisted four-resource discovery and `Store.run()` remain intact.
The previous 14-day, 30-entry recent-feed preview is retained for explicit
`tool_preview(..., feeds=...)` callers and `recent_tool_preview()`. Its feed
config and filtering rules are unchanged. The button defaults to Tavily when
configured and falls back to the project catalog without a key or sufficient
web evidence. Dynamic product identities distinguish repositories/models on
shared GitHub and Hugging Face hosts.
Legacy persisted discovery retains its ten-entry cap.

Results are transient; restart loses them and reload does not reopen them as saved
opportunities. Unpersisted results can recur on another click. Exclusions reflect
this process's last loaded/saved snapshots; reopen history/discovery after
external changes. Alias matching is conservative, not general product resolution.
Fallback coverage is limited to the catalog; configured Tavily search can find
previously unknown products. Useful results are not guaranteed.

## Verification on 27 October 2026

Passed offline: 5 project-source tests, 7 recent-preview tests, 6 legacy discovery
tests, 9 app tests and 6 decision tests, plus JavaScript syntax checking. Tests
cover actual UI-script rendering with a DOM fixture, safe text, project needs,
source grounding, failed/unsupported sources, duplicate products, cached human
Reject/Defer records, missing context/history, and zero model/memory calls.
Fixtures make no external requests; legacy tests use isolated temporary H-MEM
and synthetic transports.

One bounded live check made three official documentation requests. It found
**Instructor** (structured data extraction) and **promptfoo** (testing AI models).
**Pydantic's page was unavailable or unreadable to the checker**; no candidate
was inferred and no retry was made. The result does not identify which transport
or content condition caused that source failure. An initial attempt stopped on
a history-shape error before any source request; this was fixed and covered by
an offline test before the live check.

See [actual source records](../reports/tool_discovery/project_source_check.json).
The check reused 13 saved candidates and the original human decision, with no
model or memory-bridge calls. Production memory hashes matched before/after.
The development report is outside memory storage; the runtime preview writes
neither reports nor H-MEM. No measured project benefit is established.

Unverified: extraction/test execution, AI Raw Gourmet integration, provider
costs/terms, application-stack compatibility, useful performance, and the new
screen in a real authenticated production browser. The running server was not
restarted; a normal restart is required to load new server code. No containers,
model routes, decisions or registrations were changed. No commit or push.
