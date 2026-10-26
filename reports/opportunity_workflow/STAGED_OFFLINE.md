# Opt-in staged opportunity path — offline only

No real model request, network request, source fetch or production-memory write.
No previous live response was repaired or accepted. All new accepted responses,
usage values and route receipts in verification are explicitly synthetic and
exist only in OS temporary H-MEM copies. Genuine Defer Version 1 is unchanged.

## Implementation

- **EXTRACT:** `scripts/staged_opportunity.py` ranks existing whole prepared
  paragraphs against saved objective/task terms and selects at most three within
  the unchanged quote/text bounds. Each candidate claim is the exact publisher
  paragraph with its original source/passage IDs. This verifies attribution, not
  independent factual truth. Term overlap selects exposure, not relevance.
- **CONNECT:** `--staged` opts the existing guarded single-candidate runner into a
  publisher-claim bank plus explicit connection instructions. One response must
  use the SAME existing 14-field assessment contract. Its factual observation
  must copy a bank passage verbatim and cite it; project reasoning is model work.
  Low and uncertain relevance remain permitted. All eight original supplied
  paragraphs remain available, preserving the recorded evidence coverage.
- **VALIDATE:** original batch parser and validator v3 run unchanged, followed by
  opt-in checks for exact extracted claims, distinct selected citations, named
  project requirements-extraction linkage, evaluator limitations/Defer Version 1,
  and conditional explicitly unverified benefits. Quantified gains and guaranteed
  future project outcomes are refused. No output is rewritten, trimmed, selected
  from duplicate assessments, merged, or filled with fabricated values.
- **RECOMMEND:** reuse `opportunity_workflow` unchanged conservative choice policy.
  Staged assessments undergo the additional checks again before preparing a
  briefing. An existing-investigation continuation yields Defer; it does not
  amend the original human decision or authorize a pilot/test.
- **PRESENT / MEMORY:** reuse the existing versioned briefing, official H-MEM,
  API and home cards. The extraction plan/policy is retained privately with the
  request and accepted assessment and included in staged cache identity.
  Assessment provenance is available in existing collapsed source details.
  Dates, snapshot hashes, context provenance and previous failed outcomes remain.

Default preparation, messages and response contract remain unchanged. Staged
mode is explicitly off unless requested. The flag does not create a new live
authorization or reset the consumed one. Replay uses its retained request mode;
adding the flag does not reinterpret a historical failed response as staged.
No Nightshift, semantic validator, decision logic or UI code was changed.

## Complexity and semantic limits

This is a partial reduction, **not a new smaller model-output contract**.
Extraction and conservative recommendation are deterministic. Citation/claim
choices are limited from eight supplied paragraphs to three; factual wording is
copied rather than drafted. The model still returns all 14 fields and performs
the project connection and uncertainty reasoning in one response.

For the genuine saved source/context fixture, default messages total **25,399
characters**, staged messages **28,847 characters**. The full evidence window
plus a separate claim bank deliberately adds input. There is no demonstrated
token/cost reduction, higher live compliance, or improved live reasoning quality.
The original semantic contract and shared prompt are unchanged; staged mode adds
instructions and stricter postconditions. Further removal of output fields would
require a separately approved response-contract change.

The added benefit checks are narrow language rules, not a general proof of
semantic entailment. They deliberately reject some otherwise permissible
conditional quantified hypotheses. Project-name/task/evaluator acknowledgements
are necessary checks, not sufficient proof of a meaningful connection. A real
accepted response must still be reviewed for substance and scope. No claim bank
or schema establishes real accuracy, integration suitability, pricing or savings.

## Verification

The genuine saved public NVIDIA snapshot and genuine project/pilot/Defer context
are copied into temporary official H-MEM. Model transport is synthetic. The actual
guarded runner, retention/replay, validation, briefing persistence, restart and API
handler are used. The API dispatch uses in-memory streams, not a socket/listener.
The browser uses file HTML, mocked API responses and blocked networking.

Final results:

| Check | Passed |
| --- | ---: |
| `test_staged_opportunity.py` | 10/10 |
| Existing `test_semantic_output_contract.py` | 5/5 |
| Existing `test_opportunity_once.py`, final rerun | 5/5 |
| `check_business_presentation.py --staged-fixture --width 1440` | 49/49 |
| `check_business_presentation.py --staged-fixture --width 540` | 49/49 |
| Syntax for six changed Python files; whitespace checks | Passed |
| Original `semantic_discovery.py` compared to HEAD | Identical |

Final total: **20 backend tests and 98 browser assertions passed**, zero unresolved
failures. Coverage includes invented quotations/claims, missing named-project
connection, missing pilot/evaluator linkage, incomplete uncertainty, duplicate
assessments, unsupported quantified/guaranteed benefits, valid exact quotations
outside the selected bank, plan tampering, and allowed low/uncertain results.
The accepted synthetic staged result passes the original validator, persists a
Defer continuation, survives replay/restart, reaches the actual API handler and
renders in the existing UI. Original record contents and prior outcomes are
preserved; no human decision is generated. Default preparation and consumed
allowance guards are verified separately.

Initial verification exposed a default-mode variable-name collision introduced
by the new opt-in flag; the state-copy local was renamed and default-mode checks
rerun. The first two browser runs also expected an assessment audit label inside
the opportunity card; the existing UI keeps that label in collapsed source
details. The assertion was corrected to verify the actual preserved location.
Neither issue involved production memory or a real request.

Not run: a live model/provider request, authenticated production UI/Zetaris
verification, a public-source check, or production persistence. No claim is made
that staged mode produces a live accepted opportunity or improves live reasoning.

Files changed in this task: `scripts/staged_opportunity.py`,
`scripts/reassess_opportunity_once.py`, `scripts/opportunity_workflow.py`,
`tests/saved_source_opportunity_fixture.py`, `tests/test_staged_opportunity.py`,
`scripts/check_business_presentation.py`, and this report. Existing uncommitted
home-screen, browser-checker, report and Git-configuration changes were preserved.
No upstream code, original evidence, semantic contract, model response-format
default or human decision was edited. No commit or push was made.

## Live conditions — still blocked

There is no newly authorized allowance and no live request is proposed by this
offline verification. Before any separately authorized attempt:

1. Establish a strict upstream dispatch cap, if exactly one NVIDIA invocation is
   required. Current installed Nightshift retries provider dispatch twice on
   selected transient failures. Its automatic routing/post-generation paths have
   not been proven single-invocation. This staged path changes none of that.
2. Confirm an audited NVIDIA Nemotron Lightning route and absence of unwanted
   racing, fallback and extra generations. The unchanged helper requests
   `meterless/auto`; a returned winning-route check is not an invocation cap.
3. Use a separately explicit authorization/reservation without resetting consumed
   allowances. Scope to this one saved source/context, staged opt-in, no sources
   fetched, no client retry and the existing 4,000-token/1 MB/180-second bounds.
4. Agree on response mode. `json_object` is the unchanged default with historical
   transport compatibility but rejected semantic results. Hosted NVIDIA schema
   enforcement is unverified; there is no silent format fallback. No evidence
   shows that this staged prompt will cure duplicate output or other schema errors.
5. Authorize private request/response retention and failure journaling, with
   accepted assessment/proposal/briefing writes only after all checks and source/
   context revalidation. No human decision creation or amendment is included.
6. Accept uncertain cost: the staged input is larger, prices were not checked,
   and internal routing/retry usage is not bounded by one client attempt.

Until the one-invocation condition is resolved, stop rather than execute. Even
then, success would be a real saved-source continuation review, not proof that a
new development was discovered today. A rejected or substantively unhelpful
response remains failure; it grants no retry or permission to relax checks.
