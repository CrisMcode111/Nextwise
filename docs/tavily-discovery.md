# Bounded Tavily tool discovery

The manual **Check for updates** action reuses the current API, UI, project
context, evidence extraction, saved decision snapshots and catalog fallback.
`scripts/tavily_discovery.py` is a standard-library adapter, not an SDK or new
service. `update_discovery.tool_preview()` selects it for the normal UI path.
Explicit feed/catalog callers retain their existing behavior.

## Setup and credentials

Provide `TAVILY_API_KEY` in the environment of the Nextwise server process before
starting it normally. No key is hardcoded, read from a file, requested by the
browser or returned in API responses. There is no automatic `.env` loading and
no new credential storage. The adapter reads the environment only during a
manual check. Do not put the key in a URL, UI field, source catalog, log or report.

Only `https://api.tavily.com/search` receives the Bearer authorization header.
Proxies and redirects are disabled for the API transport. Headers are removed
from the Request object after the call. Error responses and exception contents
are suppressed; echoed-key responses are rejected. No source-page fetch receives
the Tavily key. Query text is fixed public vocabulary chosen from need categories:
no profile text, original task text, decision rationale or proprietary data is sent.

## Exact request and credit budget

For the current AI Raw Gourmet profile, each successful manual check issues
exactly **two** POST requests, both with:

- `topic: general`, `search_depth: basic`, `max_results: 5`;
- `auto_parameters: false`, `include_answer: false`;
- `include_raw_content: false`, `include_images: false`, `include_usage: true`;
- no date window, no catalog-domain restriction and no automatic retries.

One query covers the saved structured-extraction/schema/evaluation task. The
other covers the saved recipe/meal-plan goal under dietary/user constraints.
If those needs do not exist in the profile, fewer queries or none are generated.
The same check cannot exceed two search attempts. Failures stop remaining
searches; there is no retry, advanced-depth upgrade or second search phase.

Tavily documents Basic Search at **1 credit/request**:
[Search API](https://docs.tavily.com/documentation/api-reference/endpoint/search),
[credit pricing](https://docs.tavily.com/documentation/api-credits).

| Situation | Expected Tavily credit consumption |
| --- | --- |
| Normal AI Raw Gourmet check, two successful basic searches | Exactly 2 credits |
| Missing/empty key, explicit catalog/feed mode or no matching needs | 0 credits |
| Provider/transport failure | Billing unconfirmed; budget 1 credit per attempted basic request, at most 2 |
| Direct source-page verification or catalog fallback | 0 additional Tavily credits |

No Tavily Extract, Map, Crawl, Research, generated answer or other model endpoint
is called. The runtime exposes request-attempt counts and expected credits, not
an asserted account balance or confirmed bill. A failed/timed-out request may
have reached the provider and must not be assumed free. Unexpected returned usage
is rejected and prevents further searches. Repeated manual checks each have
their own two-credit budget; there is no daily/account-wide persistent quota.
The app does not change billing settings or automatically retry a failed check.

API responses are capped at 1,000,000 bytes, an 8-second socket timeout and a
15-second read deadline (one blocked read may add a socket timeout). No response
body or raw provider diagnostics are logged. Only the first five results from
each response can enter the candidate pool, even if the provider returns more.

## Verification and fallback

Search results are leads, not evidence. Interleave the two result lists, drop
unsafe/malformed URLs, deduplicate product identities and exclude previously
seen/Reject/Defer identities before considering source-page verification.
Shared GitHub/Hugging Face identities include repository/model paths, so unrelated
products are not collapsed just because they share a hosting domain.

Attempt at most **four dynamic source pages**. A source must be HTTPS without
credentials, nonstandard ports or nontracking query parameters. Local/private
destinations are rejected, including private DNS answers. The HTTPS connection
pins a validated public numeric IP and verifies the original hostname's TLS
certificate. It never follows a discovered-page redirect. Each page has the
existing 2 MB, 8-second socket and 20-second read limits; there is no page retry.
DNS resolution itself uses the operating system resolver timeout.

Require an identifiable product and a positive capability passage from the
fetched HTML, matching an actual need. Search snippets, provider-generated answers
and marketing benefits are not used as evidence. Reject obvious roundups/reviews.
Present source text, URL, publisher hostname, retrieval date, hypothetical project
connection and limitations. Publisher ownership/official status remains explicitly
unverified for newly discovered pages. Official documentation is sought in query
phrases, not asserted solely because search returned a URL.

If fewer than three candidates qualify, fill remaining slots from the existing
catalog using its existing verification and decision-exclusion rules. Fallback
may check at most four configured catalog sources (currently three), under their
existing exact-URL/redirect bounds. They cost no Tavily credits. Display at most
three candidates total, including fewer or zero when evidence is insufficient.
Every card remains **Discovery candidate — not yet validated**. There is no path
from a card to approval, deployment or the strict semantic assessment workflow.

## Preservation and verification status

No new H-MEM read/write or model call is introduced. The existing app supplies
already-loaded candidate and human-decision snapshots. Zetaris, Nightshift,
NVIDIA paths, the original Defer Version 1, all saved decisions and ordinary
saved-discovery behavior are unchanged. Runtime results and counters remain
process-local. No files or reports are written by the adapter.

Offline tests use invented Tavily results and source pages, mocked transports,
and explicit socket/model/memory guards. They cover unknown products beyond the
catalog, exact two-credit success expectations, missing-key and error fallback,
invalid key/quota/timeouts, no retries, response/result/page caps, key suppression,
DNS/URL/TLS safeguards, source-grounded descriptions, shared-host deduplication,
saved decisions and actual UI/API execution.

No live Tavily API requests or new live discovery checks were made for this
integration. Authentication, provider response compatibility, account billing,
real search quality, redirect-heavy/JavaScript-only sources and actual product
benefits remain unverified. A normal server restart is needed to load the changed
Python code and inherit the server's environment. No packages were installed;
no services were restarted, and no commit or push was made.
