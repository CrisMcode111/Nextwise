# Bounded synthetic extraction pilot

The proposed decision is whether the solo developer should proceed with further
bounded evaluation of Nemotron for explicit requirements extraction. A four-case
pilot cannot justify production adoption or fine-tuning. Current extraction
implementation, baseline measurements, acceptance thresholds and budget remain
unknown. Zetaris is the planned data layer; actual integration is pending.

## Protocol

`data/extraction_schema.json` is the explicit JSON Schema. The evaluator uses a
dependency-free validator for the keywords present in this schema. Facts contain
a field, value and verbatim input evidence. Unknown categories and clarification
issues are separate arrays. Unstated facts must be omitted and left unknown.

Only the task, schema and synthetic input are sent. The expected facts, local
rubric, source evidence, project profile and review are never model inputs.
Scoring uses the expected facts in `data/use_case.json`, exact input evidence,
the local unknown/issue rubric and the predeclared normalization rules saved with
each run. It detects missing/changed facts, unsupported evidence, duplicate
fields, missing unknown categories and missing contradiction/ambiguity flags.
This conservative deterministic check is not an independent semantic judge:
equivalent paraphrases can need manual review, and clarification wording and
arbitrary fabricated prose are not exhaustively evaluated. Quality-pass means
these checks passed, not that acceptance thresholds have been approved.

The live command prompts once using `getpass` in an interactive local terminal.
It sends at most four sequential requests (one per fixture), with `max_tokens`
1024 and timeout 180 seconds. It retains the successful analyzer's endpoint,
model, headers, JSON response setting, disabled thinking and disabled tier split.
There are no tools, retries, parameter experiments or preliminary live probes.

Transport failures, malformed response envelopes, invalid JSON or schema-invalid
outputs stop the pilot. Schema-valid quality failures are recorded and the next
fixture proceeds. Interrupted/failed runs remain incomplete. A versioned
directory is created before the first request and results are saved after each
response. No original evidence or source analyzer is rewritten.

Each run saves fixture snapshots and canonical hashes, schema and evaluator
references, actual model when supplied, original text output, parsed output,
validation findings, per-request duration and available token counts. Monetary
cost and verified prices remain null. Missing model or token metadata stays
unknown. `recommendation.json` is an evidence-linked AI-assisted next-step
proposal pending user approval, not an investigation decision.

## PowerShell commands

```powershell
Set-Location C:\Users\crist\Desktop\Nextwise
python .\scripts\evaluate_extraction.py --dry-run
python -m unittest discover -s tests -v
python .\scripts\evaluate_extraction.py --live
```

Run the live command only once for the authorized pilot. After it reports the
actual versioned results path, import that exact file (replace `<run-id>`):

```powershell
python .\scripts\investigation_memory.py import --evaluation-results .\data\evaluations\<run-id>\results.json
python .\scripts\investigation_memory.py resume
```

H-MEM's optional import stores the use case, results and recommendation as
separate official working-layer records, with exact-byte hashes and provenance.
Results derive from the use case and original evidence; the recommendation
derives from the recorded result ID. Resume retrieves IDs and verifies hashes,
fixture snapshots, lifecycle and evidence relationships. Original five-artifact
manifests remain readable. Repeated imports reuse IDs. Per-investigation locking
and storage isolation remain in force. No approval events are manufactured.

## Local checks

```powershell
python -m unittest discover -s tests -v
python -m py_compile scripts/evaluate_extraction.py scripts/investigation_memory.py tests/test_evaluate_extraction.py tests/test_extraction_memory.py
```

Offline tests include four valid fixture outputs, missing/invented facts,
unknowns, contradictions, malformed JSON/schema, request failures, stopping and
continuation behavior, no expected-answer leakage, dry-run isolation, and
extended H-MEM persistence/reimport across independent processes. The integration
test uses an explicitly labeled offline failure fixture, never a real model.
