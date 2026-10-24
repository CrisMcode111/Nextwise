# Synthetic extraction milestone

Date: 2026-10-24. Investigation:
`nemotron-lightning-requirements-extraction` (AI Raw Gourmet reference case).

## Actual live pilot

Run: `20261024T151413Z-fdf0c15b`.
Results: `data/evaluations/20261024T151413Z-fdf0c15b/results.json`.
Recommendation: sibling `recommendation.json`.

Exactly four sequential model requests were made, one per saved synthetic
fixture. All returned HTTP 200 and strict JSON matching the pilot schema.
There were no retries, preliminary live probes or parameter experiments.
`max_tokens` was 1024 and timeout 180 seconds for every request. The runtime
token was entered once using hidden `getpass` in a local interactive terminal.
The endpoint, routing model, headers and JSON/thinking settings were reused
from the successful source analyzer without changing it.

Every response identified
`nvidia/nemotron-3.5-lightning-30b-a3b` as the actual model.

| Synthetic fixture | HTTP / schema | Local quality checks | Duration (seconds) | Input / output / total tokens |
| --- | --- | --- | --- | --- |
| Explicit | 200 / valid | Failed | 3.596 | 649 / 190 / 839 |
| Incomplete | 200 / valid | Failed | 1.380 | 636 / 92 / 728 |
| Contradictory | 200 / valid | Passed | 3.528 | 641 / 234 / 875 |
| Ambiguous | 200 / valid | Failed | 1.874 | 636 / 122 / 758 |

Summed request duration: 10.378 seconds (not full program wall time).
Reported token totals: 2562 input, 638 output, 3200 total. Prices and monetary
cost remain unknown. These are synthetic extraction observations, separate from
the earlier 30.152-second Nextwise source-analysis observation.

The explicit case omitted dinner, returned the count as the string `two`, and
marked the time limit unknown despite extracting 20 minutes. The incomplete
case returned no facts, omitting dinner and tomorrow. The contradictory case
retained both requirements and asked for clarification. The ambiguous case
asked what light meant but omitted dinner and the original preference as facts.

The evaluator's generic schema allows both string and integer values; its
scorer expects numeric people_count. Thus the string `two` was recorded as
changed/missing even though its ordinary meaning preserves the stated quantity.
This is a representation mismatch, not evidence of an invented people count.
The original automated findings are preserved, with this qualification in the
AI-assisted recommendation. All four outputs also listed every unknown
category; the scorer does not exhaustively penalize irrelevant unknowns.

## Evidence-linked next step

The saved AI-assisted recommendation proposes reviewing these outputs and
refining field types, fact-capture instructions and unknown-category scope
before any separately authorized follow-up. Quality thresholds, spending
ceiling and baseline remain undecided. A larger representative evaluation and
repeated measurements would still be needed. Neither production adoption nor
fine-tuning is supported by four cases.

The recommendation references the exact results hash and original draft/review
hashes, and identifies each reviewed case by JSON pointer. User approval stays
pending. Every investigation decision remains null. The pre-pilot use-case
snapshot is retained as the exact input; execution status belongs to the
versioned result, not a rewrite of that snapshot.

## Executed validation

- `python -m unittest discover -s tests -v`: 43/43 passed in 74.936 seconds,
  including 11 evaluator tests and one extended H-MEM cross-process test.
- Python syntax checks passed for the evaluator, memory CLI and new tests.
- Dry run succeeded without network calls or token entry. No expected answers
  or scoring rubric are included in model messages.
- Actual results, use case and recommendation were imported into genuine
  official-reference H-MEM, then recovered unchanged by a separate process.
  Recorded IDs: use case `mem-7`, results `mem-8`, recommendation `mem-9`,
  manifest `mem-10`. The previous evidence and review IDs remain `mem-4` and
  `mem-5`; the original manifest is retained.
- Fixture, schema, evaluator and input-artifact hashes were checked locally.
  Pending approval, null decision and the ten historical unresolved review gaps
  survived retrieval. Historical gaps are not silently resolved by this pilot.
- Original draft, review, source registry, investigation, profile and successful
  analyzer bytes remained unchanged. No upstream H-MEM implementation changed.

H-MEM retains its reference limitations: mock embeddings, synchronous
nontransactional persistence, cooperative locking and manual stale-lock/crash
recovery. The adapter checks integrity and lineage; it does not independently
verify evidence, decide approval or establish production reliability.

## Exact commands

```powershell
Set-Location C:\Users\crist\Desktop\Nextwise
python .\scripts\evaluate_extraction.py --dry-run
python -m unittest discover -s tests -v
python .\scripts\investigation_memory.py import --evaluation-results .\data\evaluations\20261024T151413Z-fdf0c15b\results.json
python .\scripts\investigation_memory.py resume
```

The authorized live pilot has already run. The command used was
`python .\scripts\evaluate_extraction.py --live`; it must not be repeated as
part of this milestone.
