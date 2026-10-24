# Pinned upstream reference

- Repository: https://github.com/Meterless/Meterless
- Commit: `1742dec56a66e58eef9dda2d2b865823758ca8cd`
- Package: `@meterless/hmem-reference`, version `0.1.0`, private.
- Original location: `engines/hmem/reference/`.
- Local location: `vendor/meterless/hmem/reference/`.
- License files: `LICENSE` and `hmem/LICENSE`, both preserved Apache 2.0 text.
- Exact file provenance and SHA-256 values: `upstream.json`.

All 24 imported upstream files are byte-identical to the pinned sources. Their
relative reference/conformance layout is retained. There are no local changes to
the official implementation, package metadata, lockfile or tests. Git attributes
disable newline conversion for this vendored subtree so the checksums survive a
Windows checkout.

The original package-lock root metadata says MIT while package.json and the
license files say Apache-2.0. This upstream metadata discrepancy is preserved,
not silently rewritten or used to replace the supplied licenses.

Nextwise adaptations live outside this subtree:

- `scripts/hmem_bridge.ts` imports the official `HMEM` class. It adds artifact
  byte/hash envelopes, a manifest, investigation isolation and a cooperative
  exclusive process lock. It never reimplements memory storage or ranking.
- `scripts/investigation_memory.py` is a Python CLI and subprocess adapter.
- Pending review, user approval and decision remain separate from H-MEM's
  confidence, layer and retrieval score. No approval events are fabricated.
- Exact reads use `store.get(id)`. Because that method does not log reads or
  persist access touches, the bridge calls the official `store.touch`,
  `ledger.log(..., "read", ...)` and `store.persist` after successful integrity
  checks. These audit entries describe actual reads, not inferred approvals.

Runtime execution uses existing Node.js 24 TypeScript transformation. The only
installed packages are the reference's development dependencies from its own
lockfile, installed with `npm.cmd ci --ignore-scripts --no-audit --no-fund`.
No attempt was made to install the private package from the npm registry.
