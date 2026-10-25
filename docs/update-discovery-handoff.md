# Update discovery: tomorrow’s handoff

## Existing implementation

- `scripts/collect_sources.py`: `main()` reads `data/investigation.json.initial_source_urls`; `collect_one()` uses `fetch_url()`, `stable_source_id()` and `publication_date_from()`. It saves timestamped snapshots/text under `data/collected/`, raw-byte SHA-256, URLs, retrieval/publication dates and failure status. `main()` replaces `data/sources.json`; do not reuse that write path for discovery.
- `data/sources.json` holds three fixed pages, not a discovery catalog. Their saved snapshots exist. `data/project_profile.json` supplies the approved objective and constraints.
- `scripts/analyze_sources.py`: `load_prepared_sources()` checks snapshot hashes against a manually selected excerpt plan; `build_messages()`, `request_claims()` and `validate_claim()` extract/check claims for an already chosen investigation. They do not select investigations.
- `scripts/nextwise_app.py::load_investigation()` reconciles live Zetaris with persisted H-MEM; `web/app.js::load()` refreshes that existing investigation only.
- `scripts/investigation_memory.py::call_bridge()` invokes `scripts/hmem_bridge.ts::importArtifacts()/resume()/readSnapshot()` with locking and integrity checks. `scripts/decision_records.ts::saveDecision()/decisionHistory()` preserves separate versioned human choices.

## Missing behavior

No approved monitoring configuration, comparison history, item deduplication, relevance queue or investigation-selection action exists. Comparing fixed-page versions detects edits; it cannot discover separate newly published articles. Feeds/indexes need item enumeration, stable identity and subsequent approval-bounded article retrieval. Existing redirects also need destination allowlist enforcement before following.

## Smallest user-triggered workflow

1. Add one protected “Check for updates” action using the existing application architecture. Seed an explicitly approved allowlist from the three `initial_source_urls`; record approval separately from retrieval status.
2. Reuse collector helpers with separate, immutable discovery-run storage. Fetch bounded sources; preserve raw hashes and compare extracted-text hashes/diffs to suppress markup-only noise. Keep the last successful baseline when a source fails.
3. Parse one approved feed; deduplicate by feed GUID/canonical URL and content hash. Maintain per-item first-seen, publication, retrieval and revision history. Display new/changed candidates with exact source differences.
4. Deterministically match project-task/constraint terms; show matched reasons and low-relevance items, labeling matches provisional. Semantic relevance, if requested, uses one separately authorized, capped Nemotron request over changed excerpts and approved project context. Reuse request/validation helpers, not analyzer `main()` or its evidence-draft destination. Model failure leaves candidates unassessed. User selection opens a proposed investigation; nothing launches automatically.

## URLs and input blocker

Candidate NVIDIA RSS: `https://blogs.nvidia.com/feed/` — **UNVERIFIED; requires approval and verification** of availability, format and article destinations. No feed was checked tonight. Confirm the ongoing three-page allowlist and approve the feed, lookback/item cap and any model budget. Without an approved enumeration source, scope remains fixed-page monitoring.

## Acceptance and preservation

First run establishes baselines, not “new releases.” Unchanged content yields no candidates; duplicate items collapse; meaningful page edits retain old/new hashes. Relevant/low-relevance fixtures produce explained provisional categories. Partial failures retain successful results and visibly report incomplete coverage; failure never means “nothing new.” Preserve original evidence, pending reviews, pilot scores, dates/unknowns and genuine **Defer Version 1**. Persist discovery separately through an app-owned H-MEM adapter under existing locks; do not alter old manifests, six registrations or human decisions.

**Recommended path:** one project, three approved pages, one verified/approved feed, deterministic detection first, optional bounded Nemotron assessment, explicit human selection.
