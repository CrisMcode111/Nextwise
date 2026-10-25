# Local CSV export milestone

Run from the Nextwise directory in PowerShell:

```powershell
python .\scripts\export_zetaris.py
python -m unittest discover -s tests -p test_export_zetaris.py -v
```

The standard-library exporter reads only the eight JSON paths explicitly listed
in `scripts/export_zetaris.py`. The selected evaluation run is pinned to
`20261024T151413Z-fdf0c15b`. It performs no network requests or pilot execution.
It writes six CSVs and `manifest.json` under `data/zetaris_exports/<snapshot-id>/`.
The snapshot ID includes a digest of input hashes and exporter bytes. Identical
inputs and exporter bytes reproduce identical output bytes; an existing snapshot
is verified rather than overwritten. Source artifacts remain authoritative.

Each manifest records exact-byte SHA-256 input/output hashes, filenames, row
counts, primary keys, ordered column types, run ID, CSV dialect and validation
results. It also records the exporter hash. Expected rows are respectively
1 profile, 1 investigation, 3 sources, 6 claims, 1 review and 4 evaluation cases.
No joined query results are computed here.

CSV encoding is UTF-8 without BOM, with headers, comma delimiters, CRLF record
terminators and standard double-quote escaping. Embedded newlines must be read
as part of quoted fields. Python writes/reads with `newline=''`. Every CSV field
is compared after round trip; a separate in-memory probe checks commas, quotes,
CRLF/LF, Unicode, empty text and a literal backslash. Serialized `_json` fields
are parsed and reserialized to check preservation.

Column types are recorded individually in the manifest. IDs, URLs, exact text,
hashes, paths, dates and all JSON columns are `STRING`. Dates remain in their
original format and timezone. `team_size`, `http_status`, token counts and the
1/0 `schema_valid` and `quality_pass` flags are `BIGINT`; `duration_seconds` is
`DOUBLE`. These are intended import types, not a claim about Zetaris inference.

JSON values use compact Unicode JSON. Explicit unknowns remain literal `null`
in JSON columns; empty strings remain empty strings. Required missing keys abort
instead of supplying values. Optional numeric nulls use the CSV token `\N`,
with original values retained in `duration_seconds_json` and `token_usage_json`.
All current pilot measurements are populated. Before using any future nullable
numeric export, verify Zetaris maps `\N` to SQL NULL (or initially import that
column as STRING). Never convert absent measurements to zero.

The six projections follow the integration plan, with additional preservation
columns: each row has `record_json` containing its original profile, investigation,
source item, accepted claim, review or case. Claims include their draft creation
date. Cases include the original multiline `output`, its JSON encoding, the
validation, scoring protocol, run creation date, approval/decision/cost values,
and a separately named `recommendation_json` with its own artifact path and hash.
The recommendation is an AI-assisted proposal pending approval. Original claims
retain `claim_kind=publisher_claim`; review corrections remain in review JSON.
Measured cases and proposed recommendations are never substituted for claims.
No approvals or decisions are created. The scorer's `two` versus `2` caveat is
preserved in the recommendation, alongside the original case findings.

Validation rejects changed review/draft/pilot lineage, unknown reference paths,
duplicate keys, orphan claims, changed profile context, non-null decisions,
changed approval status, incorrect fixture snapshots/hashes, wrong run or row
counts, and invalid CSV/JSON round trips. Input hashes are rechecked before
writing; physical output bytes are checked after writing. Hashes identify
artifacts; they do not independently verify publisher statements.

The user has opened NDP File System and created the empty `file-store/nextwise`
folder. No Nextwise upload or registration is part of this milestone. Upload
`project_profiles.csv` first and verify its single row, header and numeric
`team_size` before registering the other five tables. Configure quoted multiline
CSV handling when importing evaluation cases. Preserve JSON columns as STRING.
UI import options, inferred types and query behavior still need verification in
the running Zetaris edition, as described in `zetaris-integration-plan.md`.
