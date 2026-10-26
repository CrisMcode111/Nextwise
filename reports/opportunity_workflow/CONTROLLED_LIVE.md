# Single-candidate opportunity test — actual result

**Completed: ONE live attempt, rejected. The authorization is consumed. No retry.**
No accepted assessment, opportunity briefing or human decision was created. The
private response and original diagnostics are retained; offline replay returns the
same rejection. No model execution was performed during replay or inspection.

| Observation | Actual result |
| --- | --- |
| Request ID | `48b155d0-24cc-4d69-b885-5abfc6e90df0` |
| Started / captured | 26 October 2026, 17:46:02 / 17:46:56 UTC |
| Provider / returned model | `nvidia` / `nvidia/nemotron-3.5-lightning-30b-a3b` |
| Nightshift receipt | `rcpt_req_yv2aeedt` |
| Transport | HTTP 200, cache miss, finish reason `stop`, 51.041 seconds |
| Reported usage | 7,211 prompt + 1,524 completion = **8,735 tokens** |
| Original validation | `batch_identity`, duplicate candidate ID count 1 |
| Persistence | Failed-attempt journal confirmed in H-MEM; assessment/briefing not persisted |

The request supplied one candidate, but the response returned **two different
assessment objects with that same candidate ID**. The unchanged batch validator
rejects the entire envelope. Diagnostic-only independent checks also reject both:
the first contains **eight evidence entries**, above the maximum of three; the
second has **empty limitations and missing-information lists** (each requires
1–8 entries), and no supporting evidence despite supplied passages. These are
generation/contract-compliance failures. JSON decoding succeeded. Neither object
was selected, merged, truncated, repaired or accepted. No project suitability or
relevance conclusion is established by this rejected response.

Post-attempt comparison passed for all **16 prior checkpoint contents, 11 original
investigation record contents, 15 earlier cache entries, four earlier request
records, 13 source observation histories and existing proposals**. Human opportunity
decisions remain empty. Genuine Defer Version 1 and its evidence are unchanged.
The selected source snapshot and retained response content still match their hashes.
Official-store access metadata may change during verified reads; record contents
and original evidence were compared separately.

Nextwise was not restarted: its existing process was checked, but no valid new
briefing exists to render. Live opportunity rendering and the new human-decision
path therefore remain unverified with real accepted evidence. No human decision
was requested or made. No source fetch, pilot rerun, commit or push occurred.

## Preparation record (before the attempt)

The following records the completed preparation; it is not an unused allowance.

- Authorization: `opportunity-e2e-nemotron-20261026-v1`, exactly one attempt, no retries.
- Runner: `python -B scripts/reassess_opportunity_once.py --live`; interactive hidden
  runtime-token entry only. Neither earlier assessment runner is appropriate.
- Candidate: saved NVIDIA blog `9428cc2bc3c996d8505a0fdf`; no fetch or other candidate.
- Production preview: 24,579 input characters, contract
  `grounded-discovery-contract-v3.1`, validator `grounded-discovery-validator-v3`.
  Context SHA-256:
  `f761e59eb549561c702e09fecd828924932dde4987b73c7274dea138a6a6a199`.
- Maximum output: 4,000 tokens; response bound 1 MB; socket timeout 180 seconds.
- Required route: NVIDIA `nvidia/nemotron-3.5-lightning-30b-a3b`, explicit cache miss,
  normal stop, then unchanged semantic validation. Unexpected route, malformed or
  rejected response consumes the attempt and produces no accepted assessment/briefing.
- Response, input, reservation and diagnostics are retained under the protected,
  ignored `data/memory/hmem/update-discovery/controlled-reassessments/` namespace.
  Full response text is never copied into this report or terminal output.
- Only a validated assessment is appended under a new cache key; previous rejected
  entries/allowances remain intact. A separate evidence/context recheck precedes
  persistence, then the existing opportunity workflow prepares a briefing. No human
  decision is created or amended. Persistence errors are reported, never retried
  through another model call.

Isolated verification: **5 new tests passed**, covering one candidate/attempt,
strict route/cache/schema checks, accepted briefing persistence/restart, private
retention/replay, credential echoes, malformed envelopes, interruption, changed
context and preservation of old outcomes. **5 existing controlled-reassessment
regressions passed**. Syntax and whitespace checks passed. All transports in these
tests were synthetic; all H-MEM stores were temporary. Initial fixture-ID mismatch
and a fixture token substring matching its synthetic receipt were corrected without
relaxing production checks. The production preview made no model request.

Preservation baseline: 16 discovery checkpoints, 15 old cache entries, four old
requests and zero opportunity decisions. Original Defer Version 1 envelope digest:
`1ebe18051f77a0a385cd625f3a2b24c394f5b11e7de65eacb5d2c415b4a01a59`.
Content-hash baselines for existing records/cache/source observations are also held
in the active tool session for post-attempt comparison.

Existing app process checked: Python PID 2732, started 14:22:28 UTC, predates the
updated backend (17:09:22 UTC). Existing Nightshift Node PID 23680 listens on 8088.
No process was stopped or restarted. If a valid briefing is produced, the app must
be restarted safely in its existing console, with the Zetaris key entered only at
its hidden prompt. No key or runtime token belongs in chat or files.
