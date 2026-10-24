# H-MEM integration validation

Date: 2026-10-24. Environment: Windows, Python 3.11.9, Node.js v24.22.1,
npm.cmd 11.19.1.

Official reference: Meterless/Meterless commit
`1742dec56a66e58eef9dda2d2b865823758ca8cd`,
`engines/hmem/reference/src/index.ts` (`HMEM`). All 24 vendored upstream files,
including licenses, implementation, tests and dependency lockfile, remain
byte-identical to the recorded pinned sources. See
`vendor/meterless/upstream.json` and `vendor/meterless/upstream-notes.md`.

## Executed checks

| Command | Working directory | Actual result |
| --- | --- | --- |
| `npm.cmd test` | `vendor/meterless/hmem/reference` | Official smoke suite: 10/10 passed, one test file |
| `npx.cmd tsx ..\conformance\runner.ts` | `vendor/meterless/hmem/reference` | Official conformance runner: 13/13 passed |
| `python -m unittest discover -s tests -v` | Project root | 31/31 passed in 39.633 seconds, including 8 new integration tests |
| `python -m py_compile scripts/investigation_memory.py tests/test_investigation_memory.py` | Project root | Passed |
| `python .\scripts\investigation_memory.py import` | Project root | Actual saved artifacts imported into official H-MEM |
| `python .\scripts\investigation_memory.py resume` | Project root | Exact artifacts recovered; all 10 recorded gaps and proposed actions displayed |

Conformance categories: record validation (2), feedback deltas (5), ranking
order (2), sleep guardrails (1), conflict gate (1), ledger audit (1), dream
boundary (1). No official smoke or conformance checks were blocked or skipped.

The eight new integration tests cover separate-process Python/Node round trips,
idempotent imports, investigation isolation, a lock owned by another live
process, corrupted artifact bytes, missing recorded IDs, review-to-draft hash
mismatch, refusal of approval/decision changes, invalid investigation IDs, and
vendored checksums. Original evidence, review, profile, investigation, source
registry and analyzer bytes are checked for preservation by test teardown.

The round-trip test observes six official create events and actual read events;
reimport creates no extra records. No approval or promotion events are added.
The real default import created manifest `mem-6`, draft `mem-4` and review
`mem-5` within the isolated investigation store. Pending user approval and the
null decision survived persistence and a new process. Analysis timing and token
counts remain labeled as Nextwise-only observations.

The official locked development dependencies were installed using
`npm.cmd ci --ignore-scripts --no-audit --no-fund`. Initial installation failed
certificate-chain verification; Node's `--use-system-ca` resolved it using the
Windows trust store. TLS validation was never disabled. The private reference
package was not installed from npm. No Python or runtime npm dependencies were
added.

## Limits of these results

This validates the pinned deterministic reference and this local Windows/Node
adapter. It does not establish semantic retrieval quality, workload extraction
accuracy, prices, quotas, integration effort, production scalability,
cross-platform support or crash recovery. Hash checks detect inconsistency;
they are not signatures or protection against an attacker who rewrites both
content and recorded hashes. The reference uses mock embeddings and
nontransactional synchronous persistence. Locking is cooperative; forced
termination can leave a stale lock requiring manual inspection.

Only the existing pending-review/null-decision lifecycle is supported. The
integration does not grant approval, choose a recommendation or run proposed
evaluation actions. No models, credentials or separate AI Raw Gourmet files
were accessed. Existing analyzer configuration and source artifacts were not
modified.
