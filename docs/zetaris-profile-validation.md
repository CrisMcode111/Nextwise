# Read-only validation of the registered profile

The user registered `nextwise.project_profiles` from
`/file-store/nextwise/project_profiles.csv` with CSV/comma, `header=true`,
`inferSchema=false`, `multiLine=true`, and no explicit escape parameter. The
preview showed the project ID, name and stage. Preview alone is not full validation.

From an interactive PowerShell console in the Nextwise directory:

```powershell
python .\scripts\validate_zetaris_profile.py
```

The validator checks the pinned CSV against its manifest hash before prompting
once with `getpass`. It uses the existing localhost SQL-editor API format,
fresh UUIDs, the existing header names, and a 60-second timeout. The sole query
is `SELECT * FROM nextwise.project_profiles`, with result limit 100, allowing
unexpected extra rows to fail the expected count of one. No filters hide rows
or columns. Redirects and environment proxies are disabled for this local request.

It requires an explicit tabular response envelope, unique column names, exact
column order, correct row widths, one row, the expected project ID and exact
values for every exported cell. JSON text must match byte-for-byte as decoded
Unicode text and parse to the same value; reformatting JSON is a mismatch even
if its meaning is unchanged. This tests quote preservation in both JSON fields.
An unsupported response envelope fails closed; it does not search for a matching
scalar somewhere in the response.

With `inferSchema=false`, the CSV numeric text `1` is accepted without claiming
that Zetaris has a BIGINT column. A returned integer 1 is also lossless; floats,
booleans, trimming and case changes are rejected. The export's numeric null
token `\N` requires SQL NULL; JSON literal `null` stays text, distinct from SQL
NULL. This first table has no null measurements or embedded newlines, so it
cannot establish how those values will import in later tables.

The key is never written or displayed, and echoed input fallback is disabled.
Reports contain fixed check labels and MATCH/MISMATCH outcomes, not returned
cell contents, headers, arbitrary server strings or raw response/error bodies.
The latest sanitized observation is written to
`reports/zetaris_project_profiles_validation.json`; exit code 0 requires all
comparisons to pass. An HTTP success alone cannot produce PASS.

Offline tests:

```powershell
python -m unittest discover -s tests -p test_validate_zetaris_profile.py -v
```
