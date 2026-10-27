# Business-brief semantic assessment (opt-in, offline verified)

The existing Meterless/Nemotron assessment contract remains the same 14 fields.
The original strict semantic validator runs first, followed by the existing
staged exact-publisher-claim and conditional-benefit checks. The only staged
project-connection change is to accept the named business and its own brief
instead of requiring every business to discuss requirements extraction.
Legacy prompts, investigation checks and saved decisions retain their defaults.

## Input and use

`semantic_discovery.prepare_business_assessment(store, item, brief, name=...,
input_kind='text', sanitized=True)` prepares one saved, source-backed product.
It reuses hash-verified saved-source preparation, the unchanged response contract
and the staged quotation bank. The input brief must be the entrepreneur's current,
reviewed text or the extracted text from the existing PDF/TXT upload flow.
There is no default project lookup, industry whitelist or hardcoded food profile.
`sanitized=True` records caller review, not automatic detection/removal of secrets.
Do not pass confidential files or unreviewed extraction output to a provider.

The existing public upload/project flow is unchanged. This change does not send
its contents to a backend or enable semantic evaluation in the public demo.
An authorized caller can pass the same reviewed text to this opt-in local pipeline.

`evaluate_business_response(content, prepared_request)` parses exactly one
assessment, checks source/context identity and runs the strict/staged validators.
It maps the existing fields to business need, publisher capability, conditional
benefit, evidence/source URL, uncertainty and one next step. Low/uncertain matches
cannot contain positive application hypotheses. All output is labelled unvalidated.
Neither helper makes requests, retries, writes memory or records decisions.
Use the existing discovery decision/deduplication gates before selecting a product;
these helpers assess one supplied product and do not resurface or override decisions.

## What offline tests establish

`tests/test_business_assessment.py` uses the saved user project objective and
constraints from `data/project_profile.json` for AI Raw Gourmet, and a clearly
synthetic nontechnical bicycle repair shop brief. Four hand-authored model outputs
cover potential and low relevance for both businesses:

| Business | Instructor | Lyro |
| --- | --- | --- |
| AI Raw Gourmet prototype | Conditional extraction support | Customer-support mismatch |
| Nontechnical repair shop | Programming-library mismatch | Conditional customer-question support |

Instructor's real official-documentation excerpt comes from the retained
`reports/tool_discovery/project_source_check.json`, not a new request. Lyro's short
publisher excerpt was read from the official Tidio page on 2026-10-27 and is stored
in `tests/fixtures/business_product_source.json`. Excerpts are publisher claims,
not full page coverage, measured benefits or product trials. Temporary test HTML
contains only those excerpts. No network requests or model calls occur in tests.

Tests also cover arbitrary-industry text, text/PDF/TXT origin metadata, no fallback
profile, changed context identity, tampered evidence, invented claims/quotes,
guarantees, missing gaps and duplicate/unknown candidate IDs. Existing public input
and upload regression tests exercise the unchanged frontend separately.

The expected classifications are MOCKED, not demonstrated model reasoning.
Validation cannot prove that a plausible fit explanation is true or that the
suggested action is economically worthwhile. No real provider output has been
accepted for this new business mode; source freshness, pricing, integration,
real-world performance and arbitrary-industry reasoning remain unverified.

## One safe live evaluation (not enabled or executed)

Obtain explicit authorization for one sanitized brief, one reviewed public product
snapshot and a provider/spend ceiling. Pass the actual reviewed input, not a fixture.
Use the existing private Meterless/Nightshift transport and provider credentials
server-side. Confirm the provider route, maximum input/output tokens, timeout and
actual underlying retry/fallback settings before sending: one client call may
otherwise cause multiple provider attempts. Existing consumed allowances must not
be reset or reused as new permission. Do not enable the public endpoint.

Send the prepared messages once (no retries), retain the bounded response and usage
in an approved isolated evaluation location, recheck source snapshot hashes, then
run `evaluate_business_response`. Report validation failure rather than repairing
or replacing rejected output. Human-review relevance and evidence even if validation
passes. Do not call the memory-writing discovery runner or save a human decision.
No credit estimate is asserted: actual cost depends on the authorized provider,
route, token usage and pricing. This change contains no live request command.
