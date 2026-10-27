# Nextwise

A local prototype that helps a solo founder inspect whether a technical update
deserves further testing. It connects approved project context, dated sources,
qualified claims, a saved four-case pilot, an existing AI-assisted proposal and
an explicit human decision with evidence links.

This demonstration resumes existing
results through live Zetaris queries and official H-MEM retrieval. Refresh,
decision save and restart do **not** call a model or rerun an experiment.
See [demo readiness and recording sequence](docs/demo-readiness.md).

## Manual update discovery

**Project-driven tool preview:** **Check for updates** uses Tavily Search when
the server environment contains `TAVILY_API_KEY`, searching beyond the catalog
for existing or new tools and checking source-page evidence. The existing
`data/discovery_tools.json` catalog remains the fallback when the key is missing,
search fails or fewer than three web candidates qualify. No additional package
is required. A normal AI Raw Gourmet check uses two basic searches: **2 Tavily
credits**, at most five results per search, four dynamic source-page attempts
and zero retries. No Tavily Extract, Crawl, Research or generated answers are used.
It shows at most three **Discovery candidate — not yet validated** records in a
separate Tools to investigate for your project section. This is a transient preview, not an
opportunity or a semantic assessment; it makes no model calls or memory writes.
First load saved decisions and reopen saved discovery so previously seen,
rejected or deferred products can be excluded. A changed page alone never
overrides a human decision.
The legacy persisted discovery API/scripts and saved opportunity workflow below
retain their existing behavior. The button no longer invokes the persisted
fixed-page check. See [Tavily limits and setup](docs/tavily-discovery.md) and
[catalog fallback scope](docs/tool-discovery-preview.md).

### From a validated candidate to your decision

Reopen saved discovery, expand a candidate and choose **Prepare opportunity
briefing**. This action rechecks its saved snapshot, exact quotations, current
project context and existing semantic validator. Failed or stale assessments
cannot become briefings. No source fetch or model call occurs.

The **Your next opportunity** panel shows what was observed, its project
connection, hypothetical value, risks, unknowns and next action. A versioned
conservative policy recommends Test for a potentially relevant new opportunity,
Defer for uncertainty or an existing-investigation continuation, and Reject for
low relevance. It never recommends Adopt from these provisional assessments.
This policy is distinct from the saved model analysis; it establishes no measured
benefit and does not override a human decision.

Choose Adopt, Test, Defer or Reject, write your rationale, and press **Save my
opportunity decision**. No choice is preselected. Amendments preserve earlier
versions. The briefing and decision reference the exact assessment, source
snapshot, project context and prior history in the existing official H-MEM
discovery checkpoints under existing locks, with disk read-back. They do not
require the old pilot manifest or modify the original investigation/Defer Version
1. Technical provenance and histories remain collapsed and accessible. A saved
choice authorizes no execution, spending, model request or deployment.

Unsaved drafts survive in-page discovery redraws, but not a full page reload.
If a save acknowledgment is lost, reopen history before changing the draft;
unchanged retries are deduplicated. Stale context/source revisions block new
decisions; historical records stay readable and marked stale. H-MEM retains its
existing non-transactional storage and checkpoint-size limits.

**Verification scope:** this connection is verified with isolated synthetic
sources/assessments and real temporary H-MEM only. There is still no accepted
project-relevant live discovery assessment; the original two accepted low-relevance
assessments and later rejected reassessments are not evidence of live end-to-end
success. No model allowance is expanded by preparing a briefing.

The legacy persisted discovery check (`python scripts/update_discovery.py`)
preserves the existing investigation while checking approved sources. The existing
investigation stays visible while progress is shown. Discovery can run before
Zetaris key entry: it uses the approved local project context, public sources
and a separate official H-MEM namespace, not live SQL or a model.

The approved scope is the three `investigation.initial_source_urls` plus
`https://blogs.nvidia.com/feed/`. The source-scope disclosure lists all four URLs.
Only these four resources are fetched. Feed article links are enumerated, not
downloaded. At most **10** unique recent items within **14 days** are retained per
check, newest first; missing/invalid/future publication dates are excluded.
Responses are limited to **2,000,000 bytes**, an **8-second** socket timeout,
**20-second** read deadline (a blocked read can add one socket timeout), and
**3** redirects. Every redirect must target an exact approved HTTPS URL.
Feed candidate links must be HTTPS NVIDIA `/blog/` URLs; tracking parameters
and fragments do not establish separate identities.

First feed success shows an **initial inventory of recently published items**.
Later checks distinguish newly discovered articles, feed title/summary edits
and monitored-page edits. Unchanged readable content produces no new event;
script/style and whitespace/markup changes are suppressed. Publisher dates may
be wrong, and changes outside the capped window are not covered. Partial failure
means incomplete coverage; successful-source results persist and failed-source
baselines remain. Fetch success never verifies publisher claims.

Project reasoning uses **`nemotron-grounded-discovery-v1`** through the existing
Meterless endpoint and routing configuration. Deterministic rules handle source
comparison, identity and evidence selection; earlier rule assessments remain
historical and are not a substitute for semantic relevance. The approved profile,
use case, existing investigation, saved pilot findings (including evaluator
limitations) and genuine Defer Version 1 supply the project context through H-MEM.

Expand a candidate to see the specific project need, source observation, exact
supporting passage/provenance, a possible application labelled **hypothesis,
untested**, limitations, missing information, explained priority, investigation
question and proposed next step. No positive relevance or application is forced.
Complete paragraphs are selected from verified saved pages; feed excerpts have
explicitly limited coverage, and linked articles are not fetched. Quotations
must match the supplied source and passage IDs exactly. Quote validation proves
textual grounding, not truth, measured benefits or suitability. Sources already
registered to the investigation are linked to its 1/4 pilot and Defer decision;
they produce follow-up proposals rather than duplicate investigations.

Validated assessments **automatically prepare and persist agent proposals**.
Use **Review and select agent proposal** with an **Optional user note**; you do
not have to invent its rationale. Selection is persisted separately from human
approval and launches no research, model call, test or pilot. Reopen proposals
and assessment/cache history after restart with **Reopen saved discovery**.
Failed assessments remain visibly uncertain and cannot be selected as validated
agent proposals. Earlier assessments, source revisions and existing proposals
are retained. A classification change never becomes a source-publication event.

For the explicitly authorized live milestone, start the existing Nightshift/
Meterless runtime on port 8088 with the working Nemotron route, then use an
interactive PowerShell console:

```powershell
python scripts/assess_discovery.py
python scripts/assess_discovery.py --live
```

The first command is a no-model preview. The second requests the runtime token
only at a hidden prompt when uncached work and authorization remain. Tokens stay
in that process and are never written to files, URLs or the browser. At most
**three requests total**, batches of at most five candidates, **6,000 output
tokens/request**, **180-second socket timeout**, **1 MB response**, **100,000
prompt characters**, and **no automatic retries** are allowed. Model transport
uses the existing headers/endpoint, with proxies/redirects disabled. A durable
request reservation prevents a crash or restart from resetting the allowance.

Successes and failures are cached by selected content/provenance, policy and
approved project-context hashes. Unchanged inputs cause no model request, even
when the previous response failed. Once the three-request allowance is spent,
new inputs remain pending/uncertain and need separate authorization; the app
never silently spends another request. Refresh, reopen and human selection use
only saved data. There is no scheduled monitoring or automatic investigation.

**Actual live result:** all three allowed calls returned
`nvidia/nemotron-3.5-lightning-30b-a3b` (38,330 reported tokens total).
**Two** assessments validated and produced agent proposals; **eleven** failed
response validation and remain explicitly uncertain. No fourth request or retry
was made. See [semantic verification](reports/update_discovery/semantic_assessment/VERIFICATION.md).

For local diagnosis without model calls, source retrieval or credentials, run
`python scripts/diagnose_semantic_discovery.py`. It verifies saved source/context
hashes and writes separate validator-versioned results under
`reports/update_discovery/semantic_assessment/offline_diagnosis/`; it preserves
cached outcomes and proposals. The original failed responses were not retained:
zero failed assessments can be recovered, and two accepted fragments revalidate.
The corrected summary counts all three distinct requests and their usage once;
cache replay sends zero requests. See the [per-candidate diagnosis](reports/update_discovery/semantic_assessment/offline_diagnosis/DIAGNOSIS.md).

The separately authorized two-candidate reassessment uses
`python scripts/reassess_discovery_once.py --live` with hidden runtime-token
entry and a durable **one-request** cap. It never resets the original allowance
or retries an interrupted attempt. Its preview (omit `--live`) and offline replay
(`--replay`) send no requests. This command is for the explicitly authorized
reassessment only, not routine startup or automatic monitoring. See the
[controlled reassessment record](reports/update_discovery/controlled_reassessment/VERIFICATION.md)
for its current stage and actual results. Responses remain in protected, ignored
local memory storage. Previous failed outcomes remain in history; low relevance
can have no investigation question and prepares no new proposal.
The authorized attempt is now consumed: one request, 9,478 reported tokens,
zero accepted and two rejected assessments. Both omitted a required observation;
the blog also omitted its existing-investigation linkage, and the gaming quote
was not exact. Offline replay preserves these failures. Do not rerun the live
command expecting another attempt; its durable guard refuses one.

Discovery state, first-seen dates, revisions and proposals live through the
app-owned official H-MEM adapter in `data/memory/hmem/update-discovery/`.
Immutable run directories retain raw snapshots, hashes, errors and source
metadata. Back up this entire directory privately with the app stopped.
Concurrent checks/selections are refused by process and exclusive file locks;
inspect a stale `discovery-run.lock` only after confirming no process owns it.
The bridge also uses its existing `nextwise.lock`. H-MEM is not crash-atomic;
history grows without automatic pruning and the bridge's existing 2 MB input
ceiling can eventually block additional saves. A persistence failure is reported
without replacing the last confirmed baseline; no automatic cleanup occurs.
This milestone provides **manual checks**, with no scheduled monitoring or
automatic investigation.

Discovery verification (isolated fixtures; browser requires installed Chrome):

```powershell
python -m unittest discover -s tests -p test_update_discovery.py -v
python -m unittest discover -s tests -p test_semantic_discovery.py -v
python scripts/check_discovery_browser.py
```

`python scripts/update_discovery.py` performs a real bounded public-source check
and persists only discovery state. It is optional; the UI uses the same path.
Actual milestone verification is recorded in
[update-discovery verification](reports/update_discovery/VERIFICATION.md).
`python scripts/verify_semantic_discovery.py` audits exact grounding,
preservation and zero-call cache replay. `python scripts/check_discovery_live_browser.py`
checks the real authenticated view without model calls or real selections.

## Existing dependencies

| Component | Existing requirement |
| --- | --- |
| Application | Windows PowerShell, Python **3.11.9**; standard library only |
| Memory bridge | Node.js **24.22.1**, using `--experimental-transform-types`; pinned official H-MEM in `vendor/meterless/` |
| Browser | A current local browser; installed Chrome used for verification |
| Query service | Existing Docker Desktop Zetaris deployment; SQL API at `http://localhost:8888`, admin UI at `http://localhost:3000` |
| Browser tests only | Installed Chrome and Python `websocket-client`; no new installation needed on this machine |

There is no frontend build, npm server or separate H-MEM service to start.
Nightshift/Meterless at port 8088 and access to Nemotron are **not required for
displaying the saved investigation or recording a human decision**. Historical
model-execution scripts are separate from the application.

## Exact Windows startup order

1. Start Docker Desktop. In its Containers view, start the **existing Zetaris
   application group** if stopped; leave its volumes, file store and registrations
   intact. The existing API container is `zetaris-api-1`, exposing loopback ports
   8888–8889. Start the whole existing group, not just that container. The admin
   UI is `http://localhost:3000`; application SQL reads use port 8888.
2. Keep the six uploaded files at `/file-store/nextwise` and their existing
   `nextwise` registrations. Expected table rows are: `project_profiles` **1**,
   `investigations` **1**, `sources` **3**, `evidence_claims` **6**,
   `evidence_reviews` **1**, `evaluation_cases` **4**. Startup does not upload,
   create, repair or replace tables.
3. Keep the existing complete H-MEM investigation directory at
   `data\memory\hmem\nemotron-lightning-requirements-extraction\`, including
   `state.json` and `ledger.jsonl`. It holds the eight imported artifacts and
   any later human decisions. It is intentionally excluded from Git. The approved
   source artifacts, CSV snapshot and pinned vendor files must remain in place.
4. In an ordinary **interactive PowerShell window**, run:

   ```powershell
   Set-Location -LiteralPath 'C:\Users\crist\Desktop\Nextwise'
   python .\scripts\nextwise_app.py
   ```

5. At `Zetaris API key (hidden):`, enter your existing key privately. Nothing is
   echoed. Do not paste it into a command, environment variable, browser, chat,
   file or recording. The app refuses an echoed-input fallback. Keep this console
   open; the key stays only in server memory and must be re-entered after restart.
6. Open **http://127.0.0.1:8765**. If the page was opened before key entry, choose
   **I entered the key · Connect**. Otherwise it loads automatically. Wait for
   **Live data · Memory linked**. The app reads all six tables, verifies their
   values and lineage against H-MEM, and reconciles the SQL aggregates before
   showing figures. It does not substitute local reports when a service fails.

If port 8765 is already serving Nextwise, use that app rather than starting a
second process. To replace a running instance, press Ctrl+C in its own console
before launching again. No infrastructure recreation is required.
New starts use exclusive port binding so Windows cannot route requests to
multiple app instances. If startup says the port is occupied, use the existing
instance or stop it in its own console; no key is requested by the failed start.
If connection needs attention, check that Docker Desktop and the existing
Zetaris API, driver, UI and PostgreSQL containers are running. Restore those
existing services rather than recreating volumes or registrations. SQL failures
show only a safe HTTP status or failure category, never response contents.

## Recording a real human decision

Beside the AI proposal, **Your decision** offers Adopt, Test, Defer and Reject
with no preselected choice. Write a rationale and optionally a next action or
reconsideration condition. Only **Save my decision** writes anything. Success
requires H-MEM persistence and read-back; no demonstration fixture is written to
the real investigation.

Saved decisions show UTC time, version and exact evidence references. **Amend my
decision** adds a version; **Decision history** retains earlier versions. A human
choice does not approve pending reviews, verify publisher claims or authorize
models, experiments or deployment. Original artifact decision fields stay null;
the human choice is a separate linked record. See [decision persistence](docs/human-decisions.md).

## Stop, resume and recover

- **Normal restart:** wait for any save to finish, press Ctrl+C, run the startup
  command again, enter the key privately and reload the page. Saved decisions
  return from H-MEM. Decision history can also be retrieved before reconnecting
  Zetaris; saving a new version requires reconciled live evidence.
- **Failed save:** keep the page open and retain your draft. Correct the service
  or lock issue and retry. The retry ID prevents duplicate versions. If success
  was uncertain, refresh decision history before making a different amendment.
  Unsaved drafts are only in page memory and disappear on full reload.
- **Load or authentication error:** restore the existing service or enter the
  correct key in the console, then retry. For the demonstrated recovery path,
  reload the document after the service is available. Reload discards unsaved
  drafts, so preserve them privately first. Automatic in-page recovery from every
  outage has not been established. A brief `already loading` response is retried
  automatically for at most ten read attempts; a longer busy period gives a retry
  error. This never automatically retries a decision write. Disconnect clears
  the key and prompts again.
- **Evidence changed / Needs review:** inspect the referenced record and its
  hashes; do not force a save, change evidence to suppress the warning or present
  the stored decision as newly approved. Missing or inconsistent evidence blocks
  new saves; readable historical decisions retain their original text.
- **Lock or corrupt storage:** stop the app and ensure no bridge process owns
  `nextwise.lock` before removing only a confirmed stale lock. Never remove a
  live lock. Do not delete state or re-import to hide an error. Restore a trusted,
  consistent backup of the complete investigation directory with the app stopped.
  Official JSON/ledger persistence is not transactional or power-loss safe.
- **Private backup / another checkout:** with the app and bridge stopped, keep a
  private copy of that complete directory outside Git. A fresh clone does not
  contain runtime memory or human decisions. Restore the private copy before
  resuming. The artifact import described in [H-MEM integration](docs/hmem-integration.md)
  can seed an initial snapshot, but cannot reconstruct lost human decision history.

## Delivery verification

Run only these focused checks for the frozen demonstration; they use existing
data and do not call models:

```powershell
python -m unittest discover -s tests -p test_nextwise_app.py -v
python -m unittest discover -s tests -p test_decision_workflow.py -v
node --check .\web\app.js
python .\scripts\check_nextwise_browser.py
python .\scripts\check_decision_browser.py
python .\scripts\check_decision_live_browser.py
```

Run browser commands sequentially. The first and last require the authenticated
running app; the middle browser command writes clearly labelled decisions only
to isolated temporary storage and tests full process restart. The live decision
check expects an undecided investigation. The genuine **Defer Version 1** now
exists, so that assertion is no longer applicable;
do not erase your decision to satisfy it. Test ports 8767 and 9223–9225 must be free.
The browser scripts normally update their report locations; the delivery check
preserved earlier reports and placed its results under `reports/delivery_readiness/`.

Historical `analyze_sources.py`, `evaluate_extraction.py --live` and model probe
scripts execute new requests; they are **not startup or recording steps**.
Do not run the registration/import/export workflows for routine playback.

## Git and recording hygiene

Commit candidates contain code, approved artifacts, exported CSVs and sanitized
reports. `.env`, `.venv/`, `node_modules/`, `__pycache__/`, `data/collected/` and
`data/memory/` are excluded. Keep credentials, private backups, recordings of key
entry, browser profiles and runtime state out of Git. The readiness audit checks
current tracked/unignored files for private paths and candidate secret literals;
it does not certify Git history or future files. No key is required in a clone.
Include the existing `.gitignore` and `.gitattributes` protections in your Git
review; the latter keeps pinned upstream bytes intact across Windows checkouts.

For Loom, record only the browser. Enter credentials and perform private backup
steps off-camera. The presentation should distinguish publisher statements,
recorded pilot measurements, AI-assisted interpretation and your own choice.
