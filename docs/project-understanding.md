# Phase 2F project understanding

`project_understanding.prepare_research(state, ...)` is a pure backend capability
over an integrity-checked Projects state. It builds on Phase 2A planning and the
existing reviewed semantic-topic contract. It does not resolve credentials,
reserve allowances, call models/search, or write project records.

The result preserves the Phase 2 plan envelope, bounds and decision constraints,
and adds an understanding view, research questions and a fixed research context.
Saved user statements and current answers are attributed separately. The
`confirmed_facts` collection means user-stated facts, not independently verified
truth. Role classifications and normalized concepts are interpretations; proposed
improvements are unverified hypotheses. Stated uncertainties, material unanswered
questions and limitations remain visible. Evidence and decisions remain history,
not automatically accepted project facts or permission to reopen a candidate.

## Local preview contract

POST `/api/projects/<id>/research_plan` uses existing session/origin protections.
It requires `expected_version`, and optionally accepts:

- `research_focus`: `general`, `technology`, `product`, `product development`,
  `marketing`, `sales`, `funding`, or `operations`.
- `clarifications`: ephemeral `subject`, `audience`, and/or `outcome` answers.
- `language`: a language tag; and `semantic_topics`: the existing reviewed,
  source-context-quoted native-language query objects.
- `limits`: existing `max_queries`, `results_per_query`, `max_source_pages` bounds.

No request ID or external-authorization flag is accepted by this preview action.
It does not create a journal entry, increment the project version or mutate the
saved brief. Answering a question or changing focus only recomputes the preview.
An omitted focus uses an explicit saved focus/priority when available, otherwise
general exploration. Explicit `general` returns to broader project needs.

The fallback asks at most two material questions. Unknown offers and audiences,
unclear marketing outcomes, conflicting exclusions, ambiguous alternatives and
unsupported languages block search proposals. It avoids asking for numerical
budgets or architecture details merely to conduct broad public research.

## Integration and safety

New `discover_adaptive` runs use Phase 2F and accept the same research options.
The original Phase 2A `plan_discovery` function remains available for compatibility;
new callers should use `prepare_research` or the `research_plan` action.
Clarification blocks execution before the first journal save. Execution still
requires both existing external/adaptive authorization flags, a fresh request ID,
current project version, enabled transports and remaining lifetime allowance.
Authorization is separate from understanding. No provider is enabled by this work.

The strategy retains the research options, reuses them during feedback adaptation,
and keeps reservations consumed across failures/restarts. Resume cannot replace
focus, answers or limits. A separate preview may explore a different focus, but
cannot reset or replace an existing cumulative run. Legacy saved strategies keep
their prior planning path; no saved projects are migrated.

## Offline and semantic limits

The offline layer recognizes a bounded set of intent, subject, audience and outcome
concepts. It is not unrestricted semantic understanding or translation. Public
queries use controlled vocabulary instead of copying arbitrary private tokens.
Unknown vocabulary stays unresolved. Source categories are targets, not enforced
publisher identity filters. Search hypotheses do not establish improvements.

For richer/multilingual interpretation, the existing `semantic_topics` contract
accepts a reviewed query tied to an exact saved-context excerpt and a review
reference. This implementation adds no automatic interpretation call or provider.
Unreviewed model output is rejected. French and Spanish clarification prompts are
available; unsupported prompt languages explicitly fall back to English. Native
queries are preserved without fabricated English suffixes when English rules are
unavailable. No full conversational UI is added.

Run focused tests with:

```powershell
python -B -m unittest discover -s tests -p test_project_understanding.py -v
```

Run the local synthetic demos with `python -B scripts/demo_project_understanding.py`.
To additionally read an existing project, supply both `--memory-root` and
`--project-id`. The demo prints summaries and writes nothing.
