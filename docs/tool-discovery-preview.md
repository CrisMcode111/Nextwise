# Manual tool discovery preview

The hackathon expansion reuses `update_discovery.py`, its bounded fetcher,
canonical URL handling, readable-text extractor and conservative project-context
phrase rules. It uses the existing local authenticated API, discovery lock,
manual button and polling. There is no additional service, scheduler, model
integration, dependency or persistence format.

## Reviewed feed configuration

Edit `data/discovery_feeds.json` to remove, reorder or configure feeds on the
three reviewed HTTPS publisher origins. Other origins, credentials, non-HTTPS
URLs, nonstandard ports and duplicate feed URLs are refused. Keep the NVIDIA
entry for the existing coverage. Adding another publisher requires a code review
of the origin allowlist and a real reachability/format check.

| Publisher | Exact feed URL | Manual check on 27 October 2026 |
| --- | --- | --- |
| NVIDIA | https://blogs.nvidia.com/feed/ | HTTP 200, RSS parsed |
| OpenAI | https://openai.com/news/rss.xml | HTTP 200, RSS parsed |
| Hugging Face | https://huggingface.co/blog/feed.xml | HTTP 200, RSS parsed |

These are publisher-operated announcement feeds. Being reachable does not
establish that an item is a tool release, relevant, correct or safe to adopt.

## Behavior and limits

1. Open the existing app and load or **Reopen saved discovery**. A successful
   existing discovery read supplies the in-process exclusion snapshot. If it is
   unavailable, the preview refuses to fetch rather than claim candidates are new.
2. Choose **Check for updates**. The button POSTs to
   `/api/discovery/check?scope=tools`; progress polling uses
   `/api/discovery?scope=tools`. Neither preview endpoint reads or writes H-MEM.
3. Each configured feed is fetched once, using the existing 2 MB response limit,
   8-second socket timeout and 20-second read deadline. Redirects are restricted
   to exact configured feed URLs, with the existing three-redirect maximum.
   There are no automatic retries. Linked articles are never fetched.
4. Parse RSS or Atom, rejecting DTD/entities. Require an explicit timezone-aware
   publication date within the last 14 days, a title, at least 30 characters of
   readable source description and a canonical HTTPS announcement URL on the
   feed publisher's origin. Atom `updated` is not a publication date. Undated,
   future, stale, malformed and untraceable items are excluded. Consider at most
   ten recent eligible entries per feed; show descriptions of at most 600
   characters, copied from readable source text.
5. Require a launch/release signal in the title and an AI/product type in the
   title or excerpt. Exclude generic news, funding, partnership, acquisition,
   report, survey, tutorial, guide, conference, policy and case-study titles.
   Reuse the local relevance function: a nearby positive capability phrase must
   connect to structured requirement extraction, language-model integration
   constraints, or recipe/meal-plan generation under dietary/user constraints.
   Show matched reasons and their exact source phrases. These are questions to
   investigate, not business-benefit claims.
6. Deduplicate canonical URLs, including tracking-parameter/fragment variants,
   and normalized title aliases against the loaded saved candidates and across
   feeds. Also exclude original investigation source URLs. Prefer more explicit
   project connections, then newer publication dates. Return at most three,
   including zero when evidence is insufficient. An individual feed failure is
   visible and does not discard results from other feeds.

Each card shows **Discovery candidate — not yet validated**, title, announcement
link, publisher, publication date, source excerpt and local match reasons. There
is no accept/adopt/prepare-opportunity action. The saved opportunities and genuine
Defer Version 1 remain in their existing sections.

Results exist only in process/page memory. Restart loses them; a page reload
does not reopen them through saved discovery. Another manual check can show the
same unpersisted candidates. “New” means absent from the loaded saved snapshot,
not independently verified as a first-ever product launch. The snapshot can be
outdated if another process changes saved discovery; reopen it before checking.
URL/title matching cannot resolve all differently named announcements of the
same product. Sparse summaries and conservative rules can miss useful tools.
Publisher dates and claims are not independently verified.

## Preservation

The original no-query `/api/discovery/check` and `Store.run()` still perform the
legacy persisted four-resource check. The new button deliberately invokes only
the transient preview. **Reopen saved discovery**, existing startup reads,
semantic cache refresh, historical selection and decision actions retain their
prior behavior; they are not part of the zero-write preview endpoints.
No strict semantic validator, H-MEM adapter, Nightshift/Meterless model transport,
NVIDIA legacy request scope or original decision record was modified. There is
no path from these transient cards into semantic assessment or opportunities.

## Verification

Run these offline checks; fixture announcements do not describe real tools:

```powershell
python -m unittest discover -s tests -p test_tool_discovery.py -v
python -m unittest discover -s tests -p test_update_discovery.py -v
python -m unittest discover -s tests -p test_semantic_discovery.py -v
python -m unittest discover -s tests -p test_nextwise_app.py -v
python -m unittest discover -s tests -p test_decision_workflow.py -v
node --check web/app.js
```

All passed: **7 new preview tests**, **6 legacy discovery tests**, **7 semantic
tests**, **9 app tests**, **6 decision tests**, plus JavaScript syntax checking.
New tests use RSS/Atom fixtures, in-memory HTTP-handler dispatch, and the actual
app script with a DOM fixture. They cover URL/title deduplication, dates,
traceability, relevance and negation, unavailable/malformed feeds, zero results,
caps, authentication/origin protection, overlap, missing exclusion snapshots,
zero memory/model calls, safe rendering and manual preview routes. Existing
tests use isolated temporary H-MEM and synthetic model transports. No tests
fetch real external feeds.

The separate manual live check successfully fetched and parsed all three real
feeds. NVIDIA and OpenAI each supplied ten eligible recent entries before
relevance filtering; Hugging Face supplied zero under the date/description/URL
requirements. Against 13 saved candidate records, **zero candidates qualified**.
See [the actual check record](../reports/tool_discovery/live_feed_check.json),
including feed URLs, timestamps and response hashes. All production memory-file
hashes matched before and after that check; no model or memory-bridge call ran.
Only this development verification report was written, outside memory storage.

Not verified: a positive project-relevant live discovery, linked article contents,
actual tool suitability/integration/cost, or the updated screen in a real browser
against the running authenticated production app. UI execution was checked
offline; visual layout and full production startup were not rerun. No commit or
push was made.
