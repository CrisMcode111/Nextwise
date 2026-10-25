# Nextwise CSV integration and investigation query

This workflow uses the six unchanged CSVs in snapshot
`20261024T151413Z-fdf0c15b-csv-5fa0db458643`, uploaded by the user under
`/file-store/nextwise`. The installed SQL path is
`dffs://nextwise/<table_name>.csv`. The source namespace is `nextwise`.

The milestone completed successfully on 2026-10-25. The actual live run is
`reports/zetaris_integration/20261025T133959Z-a8230266/`. Its
`validation.json` is PASS: 16 rows, 271 exact cell comparisons, 60 JSON cells,
16 literal JSON null cells, 44 cells containing quotation marks, and all four
original multiline outputs. All 29 SQL numeric conversions passed. The five
missing tables were created; the existing profile definition remained identical.
The saved three-row joined result matches all 31 columns per row. Review,
pilot and recommendation approvals remain pending; decisions and cost remain
unknown. No source-analysis measurement was included in the pilot aggregate.

Run in an interactive PowerShell console from the Nextwise directory:

```powershell
python .\scripts\integrate_zetaris.py --register-missing
```

Enter the Zetaris API key once at the hidden `getpass` prompt. The key stays in
that process's memory and is cleared when the run ends. It is not passed in
arguments, environment variables, files or logs. Echoed input fallback, proxies
and redirects are disabled. The existing SQL-editor request contract is retained:
localhost port 8888, fresh query/request UUIDs, source `SqlEditor`, limit 100,
the same header names, and a 60-second timeout. No models or pilot requests run.

To repeat all validation and execute the reusable query with no registrations:

```powershell
python .\scripts\integrate_zetaris.py
```

Every run creates a separate directory under `reports/zetaris_integration/`.
`validation.json` records each completed stage, original/current scoped
registration definitions, source/export hashes, script/query hashes, exact-cell
statistics, numeric checks, reference checks and overall status. `query_results.json`
contains only the parsed and validated query columns/rows, not a raw HTTP body.
The directory also contains the executed `investigation.sql`, numeric validation
queries, and SQL for any CREATE that was needed. Failures record the precise
table/key/column comparison or transport status, suppress response bodies,
and stop before any subsequent registration or query stage.

## Registration rules

The script first validates local input/export hashes and reproduces the export
in memory without rewriting it. It lists installed registrations using the
installed UI's `SHOW LIGHTNING TABLES nextwise`, then inspects each existing
allowlisted table through the table-specific metadata API established in
`zetaris-csv-reading-repair.md`. All existing definitions are inspected before
the first CREATE. Different paths, formats, storage types, delimiters or parameter
maps are conflicts, and stop the run. Unknown scan/filter options also stop it.

`project_profiles` must exist and is never created, dropped or patched. Only
the five requested missing tables may be created, and their absence is checked
again immediately beforehand. Existing matching registrations are reused.
The CREATE statements contain exactly the repaired CSV options:

```sql
CREATE LIGHTNING FILESTORE TABLE investigations FROM nextwise FORMAT csv OPTIONS (
  path 'dffs://nextwise/investigations.csv', delimiter ',', header 'true',
  inferSchema 'false', multiLine 'true', escape '"'
);
```

Replace only the allowlisted table name and filename for the other four tables.
The double quote is inside single-quoted SQL text; do not use the malformed UI
input that generates `escape """`. The default CSV quote remains double quote.
No null override, schema inference experiment or parameter sweep is performed.

## Exact validation and lineage

All six tables are compared against their CSV, including the existing profile.
Expected counts are 1 profile, 1 investigation, 3 sources, 6 claims, 1 review and
4 evaluation cases. Column names and order must match; row order may differ.
Rows are paired by the manifest's composite primary keys. Duplicate, missing
or additional keys stop the run. Every cell must match the exported string
exactly; no trimming, case folding, JSON reformatting or newline normalization
is accepted. JSON text is additionally parsed and compared. Quotes, multiline
outputs, JSON null literals and optional numeric nulls receive separate counters.

With `inferSchema=false`, every registered physical column must be STRING.
An expected numeric `\N` must read as SQL NULL to pass exact raw validation;
literal JSON `null` must remain STRING `null`. No current numeric measurement
is missing, so this run does not claim to establish a future nullable numeric
import configuration. Existing JSON nulls are exercised by the current snapshot.

Live relationships are checked after cell validation: project/investigation IDs,
claim sources, reviewed draft hashes, pilot/review lineage and fixture hashes.
Local snapshot validation also checks exact-byte evidence references, saved
fixture snapshots, review context and recommendation lineage. Original claim
kinds, pending review/pilot/recommendation approvals and null decisions must
remain unchanged.

## Numeric conversions and query meaning

The source SQL is `scripts/sql/nextwise_investigation.sql`. It executes in
Zetaris, not in the exporter. Python computes a separate expected answer only
to validate every returned result cell; it is not used as the query result.

Before joining, dedicated SQL projections cast `team_size`, HTTP status, flags
and token counts to BIGINT and duration to DECIMAL(20,6). Every converted row
is compared using Python Decimal against its exact exported value. Missing
values, truncation, non-integral counts, negative/nonfinite measurements or
flags outside 0/1 fail validation. Registered raw types remain STRING; the
validated calculations use explicit numeric types in SQL.

Claims are grouped by investigation/source/draft before joining. Cases are
typed and grouped by investigation/run/draft/model/lifecycle before joining.
SUM is returned only when every case has a known measurement; otherwise the
aggregate stays SQL NULL. The query's numeric `\N` guard uses the SQL literal
`'\\N'` (two backslashes in SQL source, representing one in Spark's string).
No absent measurement is defaulted to zero. COALESCE is used only for a known
absence of accepted claims for a registered source.

The project, investigation, source URLs/dates, review state, null decisions and
pilot state are returned together. Expected source counts are 4 blog claims,
2 model-card claims, 0 Meterless claims. Each of the three rows repeats the
same independently aggregated extraction-pilot totals: 4 cases, 4 schema-valid,
1 passing the saved quality checks, 10.378 seconds and 3200 reported tokens
(2562 prompt plus 638 completion). Do not sum pilot totals across source rows.

These are four synthetic extraction requests, not source-analysis measurements,
production accuracy, monetary cost or independent verification of publisher
claims. The query never aggregates the source-analysis observation embedded in
the review. The saved scorer and its `two` versus `2` representation caveat are
unchanged; recommendation text remains a pending proposal in the validated CSV.
Prices, baseline, acceptance thresholds and production suitability remain unknown.

## Offline checks

```powershell
python -m unittest discover -s tests -p test_integrate_zetaris.py -v
```

These tests read only approved artifacts/exports and exercise all tables, row
reordering, corruption of every column, duplicates, orphan references, changed
approvals, quote/newline/null preservation, invalid numeric conversions,
unknown-preserving totals, conflict rejection and prevention of profile CREATE.
Infrastructure, service restarts and upload persistence are outside this run.
