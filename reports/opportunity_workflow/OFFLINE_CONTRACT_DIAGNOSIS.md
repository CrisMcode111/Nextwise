# Offline diagnosis of the single-candidate response

26 October 2026. **Recovered assessments: 0. New live requests: 0.** The original
failed result, retained request/response and consumed allowance remain unchanged.
No production-memory write was requested by this work, and no human decision or
source snapshot was modified. Concurrent read-audit activity is qualified below.

## Established facts

The protected artifacts for request `48b155d0-24cc-4d69-b885-5abfc6e90df0` retain
the exact request, complete response envelope and original validation. Request
scope was one source/candidate. Saved contract v3.1 required exactly one assessment,
each candidate ID once, at most three evidence entries, 1–8 limitations and
missing-information entries, and an existing-investigation connection.

The response envelope contains one choice whose message content is a string.
That raw string is identical to the captured content and already contains two
assessment objects with the same candidate ID. JSON decoding succeeds. Therefore
local content extraction/parsing did not create the duplicate, and there was no
second source/candidate in the request.

The objects differ only in three fields: evidence, limitations and missing
information. The second repeats the first object's remaining values but empties
those three arrays. This resembles a full result followed by a stripped duplicate;
it is not a second independent candidate assessment. Its internal cause cannot be
reconstructed from the saved final text. There is no independent unmodified
upstream-provider response capture to distinguish model generation from any
upstream response shaping inside Nightshift.

The first object quotes **all eight supplied paragraphs**, once each. All eight
source IDs, passage IDs and quotations match the supplied evidence exactly. Thus
the evidence-count failure is not fabricated quotation text or a source-preparation
identity mismatch: it is failure to select within the three-citation budget. The
second object has zero evidence and empty mandatory gap lists. Both objects also
omit the existing-investigation connection despite supplied registry membership,
pilot findings and genuine Defer Version 1. Low relevance does not waive these
requirements. No accepted relevance or suitability conclusion follows.

The original request was explicit and internally sufficient to reject this output.
Its numeric citation cap and gap-list bounds were embedded in the JSON Schema,
whereas the short prose requested at least one quotation. This may have made the
bounds less salient, but causality cannot be established from one response. The
existing transport uses `response_format: json_object`; it does not send a native
schema-constrained decoding contract. Valid JSON therefore does not establish
schema compliance. Provider support for enforced schema decoding was not assumed
or tested, and the transport was not changed.

## Small safe change

`scripts/semantic_discovery.py` advances the future request contract to
`grounded-discovery-contract-v3.2`. The shared prompt now states the total result
count directly from batch size, prohibits alternative/summary/placeholder copies,
states the citation cap from `EVIDENCE_CAP`, explains that all supplied paragraphs
are a pool from which to select evidence, and repeats the mandatory gap-list
bounds from `GAP_CAP`, including for low relevance. The quotation threshold in prose
now references `QUOTE_MIN` rather than repeating its numeric value independently.

This is an unambiguous restatement of existing requirements, not a demonstrated
repair of model behavior. All supplied paragraphs remain available. No output is
deduplicated, merged, truncated or assigned missing content. The JSON schema,
parser, validator, classification rules, persistence and authorizations are
unchanged. No source-, title- or candidate-specific exception was added. Parser
and validator source text was compared with HEAD and is identical.

No deterministic repair of the saved response is safe: selecting either duplicate
would discard another generated object, and reducing eight citations or supplying
the missing context/gaps would change the model's output. Neither object passes
the existing contract independently. The response remains rejected as a whole.

## Verification

- Five new `test_semantic_output_contract.py` regressions passed: dynamic counts
  for one/multiple candidates; distinct and identical duplicate rejection; eight
  exact quotes rejected without mutation while a separate three-quote fixture
  passes; empty gap/evidence lists and missing registry connection rejected even
  at low relevance; valid low/uncertain/positive fixtures retain strict source,
  passage and quotation checks. All complete input paragraphs are preserved.
- Five existing `test_controlled_reassessment.py` regressions passed.
- Five existing `test_opportunity_once.py` regressions passed, including guard,
  private retention/replay, failure preservation and accepted fixture persistence.
- **15 tests passed.** All model transports were synthetic and stores temporary.
  Test messages saying request 1/1 are fixture output, not live calls.
- Pure offline replay of the retained v3.1 input/output still fails under unchanged
  `grounded-discovery-validator-v3` with `batch_identity`, duplicate count 1.
  Replay changed none of the protected artifacts; original validation was not
  rewritten. Future prompt v3.2 is not substituted into historical inputs.
- The discovery state and ledger are byte-identical to their pre-investigation
  hashes. The original investigation's state/ledger changed during the observation
  window: its ledger contains verified `read` events from actor
  `nextwise:artifact-memory`. All 11 original record contents are unchanged and no
  original record was added. This is consistent with verified reads by the still
  running app, but the ledger does not identify the caller process. No production
  bridge/API operation was invoked by this offline investigation. These audit
  updates were preserved rather than removed; whole-store byte identity cannot be
  claimed. Syntax/whitespace verification passed.

Changed for this task: the common prompt/version, the new focused test file, and
this diagnostic report. Earlier runner/report/test files and pre-existing
`.gitignore`/`.gitattributes` changes remain untouched. There were no source fetches,
service operations, credentials, model calls, requested production-memory writes,
commits or pushes.

**Remaining blocker:** no evidence establishes that prompt v3.2 will make the live
model obey the contract or produce meaningful project reasoning. The original
allowance is consumed. No new live test or retry is authorized by this offline work.
