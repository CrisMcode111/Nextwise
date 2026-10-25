# Evidence-led interface refinement — 2026-10-25

Implemented in the existing local interface, retaining its palette, typography,
navigation, live Zetaris client and official H-MEM integration.

The compact introduction now surfaces the current live question and a shorter
excerpt of the saved next-action proposal before the project section. The full
original recommendation and rationale remain expandable. Pending approval and
the unset decision are visible without expansion.

Each case now includes a comparison of fixture expectations, recorded facts
with original input evidence, and saved evaluator findings before the raw JSON.
Expectations come from the H-MEM fixture snapshot; recorded values/findings come
from the live pilot rows already reconciled against that snapshot. The helper
does not invoke the evaluator or calculate a replacement score.

The explicit case distinguishes omitted dinner, string `two` versus numeric
expectation 2 with the saved semantic-equivalence qualification, returned
`no nuts`, and extracted 20 minutes also listed as unknown. Additional unknowns
are shown relative to the saved required-category list. Their relevance is not
exhaustively established and no cause is asserted. Original output and original
evaluator JSON remain unchanged. The quality result remains 1/4.

Every publisher claim displays original draft wording alongside the existing
proposed review correction. Distribution versus NIM service access and
trial-service terms versus model licensing are visible before expanding the
quotation disclosure. Corrections remain pending, not verified or applied.

## Checks actually performed

- Eight focused backend tests passed, including comparison derivation, changed
  fixture values, protocol field aliases, unchanged raw output/findings/score,
  integrity rejection, authentication, empty and service errors.
- JavaScript syntax and Python compilation checks passed.
- The final real Chrome run passed all 30 checks, including live loading,
  earlier question/proposal, unchanged expandable recommendation, all case
  comparisons, the explicit-case distinctions, visible review qualifications,
  live figure reconciliation, exact quotation/output matching, internal anchors,
  source URL targets, persisted H-MEM retrieval, inert HTML rendering and mobile
  overflow at 390 × 844. Desktop was 1440 × 1000.
- Authentication, memory, empty, integrity and Zetaris error screens were tested
  using explicitly injected CDP HTTP fixtures. After interception was disabled,
  a fresh document reload completed a real live data recovery. No model or
  experiment was run. Publisher sites were not visited.
- All eight source-artifact hashes and six CSV hashes still match the export
  manifest. No registration SQL or registration writes were used.

Final machine-readable result: `final/browser_checks.json` (PASS, 30/30).
Screenshots are in `final/`; the initial refined desktop and comparison
screenshots in this directory were also visually inspected.

## Preserved failures and limitations

The first two browser attempts passed all 28 checks before final recovery, but
their in-page load after injected HTTP error fixtures displayed the generic
network failure screen. These failures are preserved in `browser_checks.json`
and `recheck/browser_checks.json`. The second records the displayed failure
state. They were not rewritten as passes.

A separate clean browser diagnostic completed two consecutive real live loads
successfully with no captured rendering exception; a direct fresh local request
also returned HTTP 200 and quality 1/4. The final check therefore disables CDP
interception and reloads the real page before checking recovery, rather than
reusing the fixture-tested document. That full reload passed. The reason the
earlier in-page recoveries failed remains unconfirmed; automatic in-page
recovery after every real service outage is not established by these checks.

Other scope limits remain: one local investigation, private console key entry,
no broader browser/accessibility audit, and no independent verification of
publisher statements or production accuracy. The exact original synthetic
pilot and saved evaluator remain authoritative for their recorded results.
