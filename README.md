# Nextwise

A local prototype that helps a solo founder inspect whether a technical update
deserves further testing. It connects approved project context, dated sources,
qualified claims, a saved four-case pilot, an existing AI-assisted proposal and
an explicit human decision with evidence links.

**Feature scope is frozen for delivery.** This demonstration resumes existing
results through live Zetaris queries and official H-MEM retrieval. Refresh,
decision save and restart do **not** call a model or rerun an experiment.
See [demo readiness and recording sequence](docs/demo-readiness.md).

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
check expects the real investigation to remain undecided, as it is before your
first save. After your genuine save, that assertion is no longer applicable;
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
