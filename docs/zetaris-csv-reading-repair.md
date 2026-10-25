# Verified profile CSV reading repair — 2026-10-25

`nextwise.project_profiles` now passes the unchanged
`scripts/validate_zetaris_profile.py`: exit code 0, all 14 checks MATCH, one row,
nine columns in order, every exported value preserved, both JSON fields valid
and textually exact. See `reports/zetaris_project_profiles_validation.json`.
The previous failing report is preserved as
`reports/zetaris_project_profiles_validation_before_repair.json`.

## Dialect and first divergence

The unchanged export has SHA-256
`58a505f942c1e1f931aafedb68fea62f3d42ba0a7d3a5e50e32da2717425361f`.
It is UTF-8 without BOM, comma-delimited, header-bearing, CRLF, with double
quotes around fields containing commas and doubled double quotes inside them.
It contains two physical lines, one data row, nine fields, valid JSON, and no
null, empty or multiline cell. Python's strict CSV reader preserves it exactly.

The first five live values matched before the repair. The first divergence was
column 6, `constraints_json`, character offset 0: expected `[` but received `"`.
The array's first internal doubled quote was not decoded with the correct escape
convention. The parser retained CSV quoting, split at the array's internal commas,
and filled the nine-column schema with fragments rather than the intended fields.
Correct header alignment and one row therefore concealed incorrect cell alignment.

These are concrete pre-repair values, shown as JSON string literals so quotation
marks are unambiguous (the backslashes here are display encoding):

| Column | Expected | Actual before repair |
| --- | --- | --- |
| `constraints_json` | Complete JSON array, 148 characters | `"\"[\"\"limited development time\"\""` (30 characters) |
| `artifact_path` | `"data/project_profile.json"` | `"\"\"additional costs must be justified\"\""` |
| `artifact_sha256` | `"49c25b3b68b265eb120664e70c17205d9972d105baf20a0c82e0b7ae82c95651"` | `"\"\"evaluate compatibility and integration effort\"\""` |
| `record_json` | Complete JSON object, 572 characters | `"\"\"cloud services may be considered\"\"]\""` |

The source JSON was valid. The returned JSON fragments were malformed because
of CSV parsing; JSON normalization or repair would have hidden the actual
problem. CSV quotes were retained, not merely reformatted. Later fields shifted
into the wrong columns. Null conversion did not cause this failure: no source
cell was null and no returned profile value was SQL NULL.

## Installed implementation and justified correction

Read-only inspection identified Zetaris 2.4.3.1 hackathon images and the query
engine returned Spark `3.5.3 32232e9ed33bb16b93ad58cfde8b82e0f07c0970`.
The installed public UI bundle was
`/_next/static/chunks/app/(authenticated)/page-753454b780860ecd.js`.
Its file wizard's `ah()` builder emits each extra parameter as a double-quoted
SQL value without escaping embedded double quotes. Thus a literal `"` in its
escape input produces the invalid `escape """` reported by the user. That input
was not repeated.

Spark's [version 3.5.3 CSV option implementation](https://raw.githubusercontent.com/apache/spark/v3.5.3/sql/catalyst/src/main/scala/org/apache/spark/sql/catalyst/csv/CSVOptions.scala)
defaults `quote` to double quote and `escape` to backslash, and passes the latter
to the CSV parser as its quote-escape character. The export uses doubled quotes,
so the smallest justified change was `escape` set to one double-quote character.
No explicit `quote` override, null override, inference change or parameter sweep
was needed. The installed engine separately confirmed `SELECT '"', length('"')`
returns a double quote and length 1.

## Exact verified SQL and options

The original registration API returned storage type `NdpFs`, path
`dffs://nextwise/project_profiles.csv`, delimiter `,`, and parameters
`header=true`, `inferSchema=false`, `multiLine=true`, with no explicit escape.
The UI `/file-store/nextwise/project_profiles.csv` path was not assumed to be
the SQL filesystem path; the `dffs://` path came from the installed registration.

This exact temporary-table SQL executed successfully against the unchanged file:

```sql
CREATE FILESTORE SESSION TABLE nw_profile_csv_probe_20261025
FORMAT csv OPTIONS (
  path 'dffs://nextwise/project_profiles.csv',
  delimiter ',',
  header 'true',
  inferSchema 'false',
  multiLine 'true',
  escape '"'
);

SELECT * FROM SESSION.nw_profile_csv_probe_20261025;
```

The single quote characters delimit SQL string literals. In `escape '"'`, the
value between them is just one double quote; there is no backslash in this SQL
value. All 14 of the existing validator's comparisons passed on the temporary
table before any permanent option changed. The installed wizard uses this same
`CREATE FILESTORE SESSION TABLE` workflow for previews.

For subsequent registrations, reuse the verified option values and single-quoted
SQL syntax. The installed wizard's permanent statement shape is:

```sql
CREATE LIGHTNING FILESTORE TABLE <table_name> FROM nextwise
FORMAT csv OPTIONS (
  path 'dffs://nextwise/<uploaded_filename>.csv',
  delimiter ',',
  header 'true',
  inferSchema 'false',
  multiLine 'true',
  escape '"'
);
```

This is a template for future work, not an executed registration of the remaining
datasets. Only the temporary statement above was used to test SQL quoting here.
Do not put a raw double quote into the wizard's parameter input that emits
double-quoted SQL. Use the SQL editor with the verified literal syntax instead.

## Permanent repair and recovery

The installed UI bundle's module `65541` establishes the table-specific API:

```text
GET/PATCH /api/v1.0/lightning-database/databases/nextwise/file-store-tables/project_profiles
```

The original non-secret local registration definition was saved before changing
anything in `reports/zetaris_project_profiles_original_registration.json`.
The accompanying `.sql` file is a recovery CREATE definition reconstructed from
that metadata, not a server-provided SHOW CREATE result. SHOW CREATE failed;
DESCRIBE returned column types only and TBLPROPERTIES was empty. The installed
UI's actual metadata API supplied the original definition.

After the temporary comparison passed, the scoped PATCH preserved every original
editable field and added only `"escape": "\""` to `parameters` (JSON notation).
Reading the registration back confirmed all other fields and parameters were
unchanged. This avoids dropping/recreating the permanent table or touching the
uploaded file. To recover, PATCH the saved original definition's editable fields
(exclude `format`) to the same endpoint with the private authentication flow.
The original parameters omit `escape`. No recovery action was executed.

The unchanged validator's `main()` was then invoked with the same in-memory
private-key provider and its original `SELECT * FROM nextwise.project_profiles`.
It wrote the PASS report and returned 0. No comparison rule was relaxed. The
temporary session table was subsequently dropped with:

```sql
DROP TABLE SESSION.nw_profile_csv_probe_20261025;
```

`reports/zetaris_csv_repair_observations.json` records scoped parsed comparisons,
metadata, SQL and validator exit status; it contains no credentials or raw HTTP
bodies. The private-key process was closed after cleanup.

## Numeric typing and remaining import limits

`DESC nextwise.project_profiles` after repair confirms all nine columns are
`string`. `team_size` is the preserved CSV value `"1"`, not a registered BIGINT.
Value preservation passes; numeric schema work remains separate and was not
performed. The profile has no multiline or null cells, so it cannot verify the
remaining datasets' newline or nullable-number behavior. Keep JSON literal `null`
as text and separately verify the documented numeric `\N` to SQL NULL mapping
when that becomes applicable. No such option was guessed or changed here.

Source artifacts, exports, pending approvals and decisions remain unchanged.
No other permanent table, uploaded file or infrastructure was modified.
