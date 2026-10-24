# Zetaris integration plan: one provenance-aware investigation query

Prepared on 2026-10-24 for 2026-10-25 (Europe/Paris).
Status: documentation-only investigation; implementation and runtime verification
remain pending. No credentials, environment files, application APIs, models or
Docker APIs were accessed. No application code or infrastructure changed.

## Chosen minimal approach

Prepare six small, versioned CSV projections of the approved Nextwise JSON
artifacts on Windows. Upload them through the existing Zetaris UI into its file
store, register six virtual file tables, and run the joins and aggregations in
Zetaris SQL. Nextwise will subsequently submit that same SQL using the working
Python request contract. Python only flattens individual artifact structures;
it does not compute the joined answer.

This is a bounded snapshot integration: Zetaris is the actual query layer over
the uploaded files. Source JSON remains authoritative and unchanged. Updates
require a new versioned export/upload. This does not yet provide automatic sync,
live virtualization of Windows paths, or a production data pipeline.

The official [local JSON/CSV connection tutorial](https://kbase.zetaris.com/knowledge/how-to-ccnnect-to-json-from-local-machine)
documents desktop file upload and virtual file registration. The
[connection overview](https://kbase.zetaris.com/knowledge/connect) identifies
file sources as supported inputs. These establish the supported approach;
the installed Docker edition's UI and import options still need verification.

## Confirmed local inputs

Inspected `test_zetaris.py` without executing it. It uses Python's standard
library, hidden `getpass`, POST to
`http://localhost:8888/api/v1.0/sql-editor/sqls/run`, a 60-second timeout and
payload keys `queryId`, `sql`, `source`, `limit`. Header names are
`Authorization`, `Content-Type`, `X-Org-ID`, `X-Request-ID`.
The existing test query is `SELECT 1 AS one`. Its previously successful result
is reported project history, not a fresh connection test tonight.

The UI address `http://localhost:3000` and Docker deployment are established
project context; current reachability and container topology were not probed.

| Local artifact | Confirmed content relevant to this plan |
| --- | --- |
| `data/project_profile.json` | Project `ai-raw-gourmet`; one developer; existing prototype; approved objective and constraints |
| `data/investigation.json` | Investigation `nemotron-lightning-requirements-extraction`, project ID, question; decision null |
| `data/sources.json` | Three source records with existing IDs and retrieval/publication metadata |
| `data/evidence_draft.json` | Six accepted publisher claims linked to source IDs; original criteria and exact quotes |
| `data/evidence_review.json` | AI-assisted review pending user approval, exact reviewed-draft hash, gaps and proposed corrections |
| `data/use_case.json` | Synthetic fixtures and proposed evaluation scope; Zetaris is the planned data layer |
| `data/evaluations/20261024T151413Z-fdf0c15b/results.json` | Four actual pilot cases, schema/quality findings, actual model, durations and token usage |
| Sibling `recommendation.json` | AI-assisted next-step proposal pending approval; null decision; evaluator caveats |

All existing files, H-MEM state and successful Meterless settings stay unchanged.
Only approved Nextwise data is exposed; the separate AI Raw Gourmet folder,
HTML snapshots, credential files and private implementation are outside scope.

## Export contract to implement tomorrow

Proposed host directory:
`C:\Users\crist\Desktop\Nextwise\data\zetaris_exports\<snapshot-id>\`.
It does not exist as a result of this plan. The snapshot ID and namespace below
are proposed names, not registered resources. Use the same snapshot for all
tables. Create a local manifest recording every input/output path, exact-byte
SHA-256, row count, column types and selected evaluation run ID.

Use UTF-8 CSV with a header and standard quoting for commas, quotes and newlines.
Write with Python `csv` using `newline=''`; verify by reading it back. Preserve
raw IDs, text, dates and hashes. Fields ending `_json` hold JSON text serialized
from the original value; an unknown decision is the literal JSON text `null`,
not approval, an empty string or a default decision. This explicit encoding
avoids assuming how this Zetaris build interprets empty CSV cells. For optional
numeric measurements, retain a JSON value alongside the query projection and
verify SQL NULL import behavior before publishing nullable numeric columns.
Never replace absent measurements with zero.

Proposed namespace: `nextwise_demo`. Every table includes `artifact_path` and
`artifact_sha256` pointing to its original input artifact; the export manifest
also hashes the physical CSV. These are integrity/provenance fields, not
independent verification labels.

| Table / expected rows | Exact projection and key mapping |
| --- | --- |
| `project_profiles` / 1 | Profile `id` -> `project_id`; `name` -> `project_name`; `stage`, `objective`, `team_size`; full approved `constraints` -> `constraints_json` |
| `investigations` / 1 | Root `id` -> `investigation_id`; `project_id`, `question`, `status`; `decision` -> `decision_json` |
| `sources` / 3 | One root `sources[]` item per row: root `investigation_id`; item `id` -> `source_id`; `title`, `requested_url`, `final_url`, `retrieved_at_utc`; `publication_date` -> `publication_date_json` |
| `evidence_claims` / 6 | One root `accepted[]` entry per row: root `investigation_id`; exact draft SHA -> `draft_sha256`; `/accepted/<zero-based-index>` -> `claim_pointer`; original `source_id`, `claim`, `exact_supporting_quote`, `claim_kind`, `relevance_to_criterion`, `limitations`; root status -> `draft_status` |
| `evidence_reviews` / 1 | Root `investigation_id`, `project_id`, status -> `review_status`; `reviewed_draft.sha256` -> `reviewed_draft_sha256`; `approval.status` -> `approval_status`; `decision` -> `decision_json`; `readiness.status` -> `readiness_status`; gaps and claim reviews -> JSON text columns |
| `evaluation_cases` / 4 | One `cases[]` entry per row: root `investigation_id`, `run_id`, status -> `evaluation_status`; draft hash from this run's `evidence_references` -> `draft_sha256`; `use_case_reference.sha256`; case `fixture_id`, `fixture_sha256`, `actual_model`, `http_status`, `duration_seconds`; `validation.well_formed` -> `schema_valid` (1/0); `validation.quality_pass` -> `quality_pass` (1/0); token counts -> `prompt_tokens`, `completion_tokens`, `total_tokens`; original output and validation -> JSON text columns; approval/decision and absent cost -> JSON text columns |

Keys are `(project_id)`, `(investigation_id)`,
`(investigation_id, source_id)`, `(draft_sha256, claim_pointer)`,
`(investigation_id, artifact_sha256)` for reviews, and
`(investigation_id, run_id, fixture_id)` for cases. Claim pointers identify
positions within the exact hashed draft; no new authoritative claim IDs are
invented. Preserve all three source IDs exactly:

- `blogs-nvidia-com-a8ba0b0ace91`
- `build-nvidia-com-c0320c9fae83`
- `meterless-ai-daf677f0f296`

The current pilot has all three token counts and duration populated for each
case, so no imputation is needed for this demonstration. Validate before export:
the review targets the exact draft bytes; the pilot's evidence references match
that draft and review; its fixture hashes match its saved fixture snapshots;
IDs are unique; every accepted claim has a registered source ID. Abort export
on any mismatch. Original criteria and review corrections remain separate.

## Prerequisites and implementation steps for tomorrow

1. Open the existing Zetaris UI and check that this installed edition exposes
   the documented upload and virtual-file workflow and that the account can
   upload, register and SELECT files. Record the UI/build version and query
   engine if available without inspecting secrets. Do not change infrastructure
   to make the tutorial fit. This is the first compatibility gate.
2. Implement a small standard-library, allowlisted exporter for the six tables
   above. Pin the run `20261024T151413Z-fdf0c15b`; validate provenance before
   writing to a new snapshot directory. Do not auto-select a different run.
3. Check CSV round trips, keys, input/output hashes, null JSON values and row
   counts locally. The query joins must not be precomputed in the exporter.
4. Following the official tutorial, navigate to **NDP File System**, open
   **file-store**, create a snapshot-specific folder, then use **Upload** and
   **Browse Files** to select only the six exported CSVs.
5. In **SQL Workspace**, add a container under **Virtual File Sources** named
   `nextwise_demo` if available; otherwise record the actual namespace and use
   it consistently in the query. Add each uploaded file using **File Store**,
   assign its table name from the contract, and create the registration.
   Register one table first (`project_profiles`) and preview it before the rest.
6. Check the import configuration and registered schema. Require header parsing,
   numeric `team_size`, 1/0 flag columns, numeric durations and token counts,
   correctly quoted JSON/text, and unchanged IDs. The SQL manual documents CSV
   `header` and `inferSchema` options; their exact UI controls, defaults and
   this build's inferred types are unverified. If configuration is unavailable
   or values change, stop and record the mismatch rather than guessing options.
7. In the SQL editor, run the sanity queries below and then the verification
   join. Inspect actual rows, column names and types. Save SQL and the returned
   result as a dated integration observation, including input/export hashes;
   keep the investigation decision and approval unchanged.
8. Only after the UI query works, add a separate Nextwise query command reusing
   the request structure from `test_zetaris.py`: new UUIDs, `source` `SqlEditor`,
   this SQL string and a result `limit` of 100, retaining the endpoint, headers,
   timeout and hidden credential entry. Leave the original connection test
   unchanged. Require exact returned rows/IDs, not just `contains_one()`.
9. Repeat that read-only query in a new Python process. Record that the query
   was executed by Zetaris. Check whether uploaded files/registrations survive
   an ordinary service restart only when separately in scope; container
   recreation persistence is not established by the documentation inspected.

Steps 2-9 are future work, not actions executed tonight. If step 1 fails, report
the installed-feature/documentation mismatch before building another connector.
No JDBC driver, database service, npm package or Postman installation is needed
for this chosen route.

## Windows and Docker boundary

Windows browser -> existing published UI port -> Zetaris upload/file store;
Windows Python -> existing published SQL API port -> Zetaris query engine.
Docker Desktop forwards published host ports into the container environment,
as described in its [networking documentation](https://docs.docker.com/desktop/features/networking/).

An uploaded file is selected from Windows by the browser and stored on the
server. Zetaris does not open a Windows `C:\...` path directly. Therefore this
approach needs neither a new bind mount nor a container-to-Windows callback.
The file-store path must come from the UI; no Linux path or container name has
been assumed. Visibility to all query workers and durable backing storage are
prerequisites to verify in this deployment. Existing port publishing and
firewall configuration have not been inspected or changed tonight.

`localhost` is appropriate for the Windows client accessing the already
published host ports. Inside a container it refers to that container, not the
Windows application. No reverse connection is part of this plan.

## SQL verification (proposed; not executed against Zetaris)

Start with:

```sql
SELECT project_id, project_name, team_size
FROM nextwise_demo.project_profiles;

SELECT investigation_id, source_id
FROM nextwise_demo.sources;

SELECT run_id, fixture_id, schema_valid, quality_pass,
       duration_seconds, total_tokens
FROM nextwise_demo.evaluation_cases;
```

The useful query asks: for this project's investigation, which source pages
support the reviewed draft, and what did the linked synthetic pilot actually
show? Aggregate claims and cases separately to avoid multiplying six claims
by four cases before counting. The draft-hash join enforces actual artifact
lineage rather than merely assuming that any run under the same investigation
used the reviewed draft.

```sql
WITH claim_counts AS (
    SELECT investigation_id, source_id, draft_sha256,
           COUNT(*) AS accepted_claim_count
    FROM nextwise_demo.evidence_claims
    GROUP BY investigation_id, source_id, draft_sha256
), pilot AS (
    SELECT investigation_id, run_id, draft_sha256,
           COUNT(*) AS attempted_cases,
           SUM(schema_valid) AS schema_valid_cases,
           SUM(quality_pass) AS quality_pass_cases,
           SUM(duration_seconds) AS request_seconds,
           SUM(total_tokens) AS reported_total_tokens
    FROM nextwise_demo.evaluation_cases
    GROUP BY investigation_id, run_id, draft_sha256
)
SELECT p.project_id, p.project_name, p.stage, p.team_size,
       p.constraints_json, i.investigation_id, i.question,
       r.review_status, r.approval_status, r.decision_json,
       r.readiness_status, s.source_id, s.requested_url,
       COALESCE(c.accepted_claim_count, 0) AS accepted_claim_count,
       e.run_id, e.attempted_cases, e.schema_valid_cases,
       e.quality_pass_cases, e.request_seconds, e.reported_total_tokens
FROM nextwise_demo.project_profiles p
JOIN nextwise_demo.investigations i
  ON i.project_id = p.project_id
JOIN nextwise_demo.evidence_reviews r
  ON r.investigation_id = i.investigation_id
JOIN nextwise_demo.sources s
  ON s.investigation_id = i.investigation_id
LEFT JOIN claim_counts c
  ON c.investigation_id = i.investigation_id
 AND c.source_id = s.source_id
 AND c.draft_sha256 = r.reviewed_draft_sha256
JOIN pilot e
  ON e.investigation_id = i.investigation_id
 AND e.draft_sha256 = r.reviewed_draft_sha256
WHERE i.investigation_id = 'nemotron-lightning-requirements-extraction'
  AND e.run_id = '20261024T151413Z-fdf0c15b'
ORDER BY s.source_id;
```

Expected from the inspected artifacts, not a claimed Zetaris query result:
three rows (one per source), claim counts 4/2/0 for blog/model card/Meterless.
Each row repeats the same pilot totals: 4 attempted, 4 schema-valid, 1 passing
local quality checks, approximately 10.378 summed request seconds and 3200
reported tokens. Do not sum repeated pilot totals across the three source rows.
Two NVIDIA pages are not two independent publishers, and the pilot does not
validate each publisher claim. The review stays pending, `decision_json` is
the JSON text `null`, and production adoption is not supported. The saved
recommendation qualifies the scorer's `two` versus `2` representation mismatch;
1/4 is a local-check result, not an independently established accuracy rate.

## Syntax confidence and remaining verification gates

| Item | Basis / status |
| --- | --- |
| Desktop CSV upload and virtual file registration | Confirmed in official Zetaris tutorial; availability/labels in this installed edition unverified |
| File registration namespace and two-part SELECT names | Documented by the [Zetaris SQL guide](https://kbase.zetaris.com/knowledge/sql-guide); actual registered names still to verify |
| CSV `header` / `inferSchema` options | Documented in the local-files section of the [SQL manual](https://kbase.zetaris.com/knowledge/sql-manual); UI mapping and resulting column types unverified |
| WITH, JOIN, GROUP BY, aggregates and SQL expressions | Documented in [Spark SQL syntax](https://spark.apache.org/docs/latest/sql-ref-syntax.html), linked by Zetaris; query above is project-authored and unexecuted, and this deployment's engine/version remains unverified |
| SQL API route and payload keys | Confirmed in existing working local test; not independently exercised tonight |
| General bearer/header API access | Supported by [official Zetaris API guidance](https://kbase.zetaris.com/knowledge/accessing-zetaris-using-api); no login or API request performed |
| Public REST query example | The [older REST tutorial](https://kbase.zetaris.com/knowledge/rest-api) describes a different `select`/`pageLimit` contract; verify the installed API reference before implementation and retain the locally tested SQL-editor contract |
| CSV JSON-text quoting, NULL policy, worker visibility, restart durability | Still require local verification; no undocumented defaults assumed |

The SQL guide explicitly says it is under revision. No CREATE registration
commands, upload API endpoints, Docker mount commands, container paths or
Spark version settings have been invented. Public documentation is available;
the outstanding gate is compatibility with the installed Zetaris build.
