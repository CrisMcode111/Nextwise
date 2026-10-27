# Public Vercel demo

The deployment is an isolated public-only bundle, not the local Nextwise server.
No private data, report, genuine decision, credential, local service client or
Tavily adapter is part of it. The existing local application is unchanged.

The explicitly named AI Raw Gourmet recipe/meal-plan scenario also supports a
labelled **Guided demo — pre-verified opportunities** path. It presents DishGen
and Samsung Food+ using retained official-page evidence, with no live search.
Pre-verification covers product identity and advertised capabilities, not tested
business outcomes. Other projects retain ordinary discovery. See
[the guided presenter flow and limitations](guided-hackathon-demo.md).

## What visitors can do

- Start with an empty project input. No example profile starts a search. Enter
  a description or extract a document, review it, then find opportunities.
- Search public GitHub repositories for the user's reviewed project needs,
  beyond the three catalog products. Relevance patterns, evidence fields and UI
  helpers are reused; product identity/deduplication uses pure helpers extracted
  from the existing local Tavily integration. The local Tavily adapter is unchanged
  and its authenticated transport is never packaged or invoked in the public demo.
  Returned descriptions are repository-owner claims, clearly separate from
  project input and validated recommendations. Fewer or zero candidates are valid.
- See at most two compact opportunities with a tool name, source link, conditional
  business benefit, visible uncertainty and one small next step. If only one
  credible match exists, explicitly explain why a second is not shown. No filler.
  **Explore this** selects one opportunity and visibly confirms its next step;
  it does not start a trial or purchase. **Explain why** opens the existing
  source evidence and limitations inline; it makes no requests or decisions.
  **Not interested** hides the suggestion and saves the existing Defer choice.
  Plain language makes clear these ideas have not been tried for this business.
  Detailed evidence and technical coverage stay collapsed. There are no
  navigation menus or duplicate decision forms in this public view.
- Save **demo choices in their browser only**. Not interested stores Defer and hides that card.
  These choices survive reload on that origin when localStorage is available.
  Selection uses the existing Test choice with an explicit untested rationale.
  One active selection is scoped to a SHA-256 fingerprint of the reviewed text;
  raw project text is not stored. Choosing another replaces the active choice
  for that project. Re-entering the same project restores its selection after reload.
  A storage failure is visible and does not claim that a selection was saved.
  Previously deferred/rejected demo tools are skipped on subsequent visits.
  Clearing demo choices is explicit and affects only the demo storage key.
- Use the left panel for project text or a PDF/TXT file.
  Browser-local rules quote the stated business goal, explicit challenges and
  possible jobs to help with: meal planning, customer questions, bookings,
  marketing drafts and paperwork. Visitors can correct their text; there are no
  technical checkboxes or manual categories. **Find opportunities for my project** applies the
  inferred jobs. Source selection and candidate filtering depend on them.
  Libraries are considered only when the text explicitly requests developer
  tools and describes a supported technical task. Unsupported jobs return no ideas.
  This is transparent rule matching, not model analysis or wider-web search.
- Read TXT and text-based PDF files in the browser only: at most 2 MB, 20 PDF pages,
  12,000 characters and a 15-second PDF processing deadline. Scans need OCR, which
  is not provided; encrypted, damaged or unsupported files ask for pasted text.
  PDF extraction can be incomplete, so the editable review is required for files.
  PDF.js 6.4.299 is self-hosted with its worker, Apache license and package integrity
  provenance. No CDN, upload endpoint, file persistence or project-text storage is used.
- See a decorative Fibonacci spiral and subtly animated stars at idle, with more
  active stars during actual processing. Search messages appear only during source
  requests; file reading and prepared results do not imply live AI discovery.
  Reduced-motion preferences disable all star animations.

Demo context loads through GET `/api/demo`. A blank project starts no discovery.
After review, discovery issues at most three sequential GET `/api/discover?need=<known-id>` requests per visit. Each
serverless invocation makes exactly one unauthenticated GitHub repository-search
GET, inspecting at most five repository records and returning at most three
unvalidated matches. Query templates depend on need categories, never project
text. No arbitrary URLs, queries, pagination or extra page fetches are accepted.
There is no background
service, process-state polling or cross-request job state. Each fixed source gets
at most one attempt per page session. Reconfirming a different project reuses
previous results (including failures), checks only any remaining relevant sources,
and stays within three total search requests. Products are deduplicated across
needs; one match per confirmed need gets priority before remaining slots are
filled. Preferences are keyed by repository identity, persisted only in the browser,
and applied before display. Legacy catalog rejections still suppress matching
product names, without excluding other tools for that need.
The PDF parser uses a local browser
worker for file reading, not a background discovery service.
Choices and clearing choices make no API calls; Use these needs again to reconsider
tools after clearing choices. Unavailable or unsupported sources can leave zero cards;
no placeholder recommendations are substituted. No live-source availability or
business benefit is guaranteed by offline tests.

The repository search has a 250 KB response limit, 3-second socket timeout, 5-second
read deadline (a blocked read can add one socket timeout), no redirects and no
retries. Vercel's configured invocation duration is 15 seconds. DNS resolution
uses platform resolver limits; the browser aborts an API request after 12 seconds
and reports incomplete coverage rather than substituting a candidate.

The new transport can contact only `https://api.github.com/search/repositories`
with server-generated query templates, without credentials, redirects, proxies
or retries. GitHub may rate-limit shared hosting IPs; failures or incomplete
results are reported with no paid fallback or fabricated suggestions. Repository
identity, public/non-fork/non-archived status, dates and capability descriptions
are checked from GitHub's response. Descriptions support a possible project
connection, not repository code quality, verified ownership or business benefits.
For business jobs, candidates also need an advertised user-facing app/service
and a non-documentation product website. Libraries, SDKs and command-line or
self-hosted-only projects are excluded. Advertised online/no-code/cloud access
gets priority; neither a homepage nor those claims establishes usable hosted
access. The existing card uses plain business language, a potential benefit and
a practical trial; the owner's exact description and uncertainties stay in
Explain why. No savings, conversion uplift or dietary safety is claimed.
READMEs and third-party product pages are not independently fetched or verified.
The original three-document catalog API remains available under `?source=` for
legacy clients, with its original 2 MB cap; it is not substituted silently for
failed searches. Visitors cannot
supply URLs, source text, project files or credentials to the server. Project/file
content and reviewed needs are never added to requests; only fixed source IDs are
sent. API writes are rejected;
arbitrary paths and the local app's APIs are unavailable. Source-request proxies
are disabled and no authorization header is sent. Error bodies are suppressed.
Tavily costs **zero credits**, including if a Tavily key exists in the deployment
environment: the public bundle neither reads that key nor includes the adapter.
Zetaris, H-MEM, Nightshift and NVIDIA model paths are absent and disconnected.
Ordinary outbound documentation fetches and Vercel invocations still count
against hosting/provider limits; the demo is not an unrestricted URL proxy.

## Build the isolated upload folder

From the private repository root, run this offline build:

```powershell
python -B scripts/build_vercel_demo.py
```

The prepared output is `.nextwise-vercel-demo/` (ignored by Git). It contains
exactly eighteen allowlisted files (CLI project metadata is kept separately):

```text
.python-version
.vercelignore
vercel.json
api/index.py
lib/collector_public.py
lib/discovery_public.py
lib/business_public.py
lib/identity_public.py
lib/search_public.py
public/index.html
public/app.js
public/demo.js
public/project.js
public/style.css
public/pdfjs/pdf.mjs
public/pdfjs/pdf.worker.mjs
public/pdfjs/LICENSE
public/pdfjs/provenance.json
```

The build uses a small public-only HTML template, reuses existing styles and extracts just the existing UI
helpers/candidate renderer and pure catalog discovery functions. It does not
copy the local startup, private history renderer, local API server, service
adapters or catalog/private data files. The public Python handler supplies its
own example context and explicit public source definitions. There are no runtime
project-file reads, filesystem persistence, Node subprocesses, model calls or
third-party Python dependencies. The only added runtime library is the self-hosted
browser PDF parser; its pinned source and SHA-256 checks are in provenance.json.

The builder reads only an explicit set of source/template files. It refuses to
build into the repository root or a folder containing unexpected files, and
never deletes files. The repository-root `.vercelignore` denies every file to
prevent accidentally uploading the private checkout with Vercel CLI. The generated
folder has its own independent Vercel config/ignore rules.

**Deploy only this generated folder. Do not import/upload the private repository
root, its data directory, reports or memory storage.** Do not add environment
variables or private assets to the generated folder. Rebuild after changing the
shared UI or discovery code; build checks fail if extraction boundaries change.

## Offline verification completed

```powershell
python -B -m unittest discover -s tests -p test_public_demo.py -v
python -B tests/public_demo_browser.py
```

Fifteen checks cover the build allowlist, no private-file reads, no private imports,
new example context, ignored secret environment variables, real packaged Python
handlers, Vercel rewrite query handling, one bounded source per request, HTTP
scope/size/timeout controls, failed/unsupported sources and blocked private/write
routes. The actual generated JavaScript is executed with a DOM/localStorage
fixture: automatic initialization, simple evidence-backed cards, sequential and
cached checks, three-page cap, failures, zero candidates, local choices,
Not interested suppression on reload, accessible collapsed explanations, safe text and unavailable browser storage. The
HTML check confirms two panels, local project inputs and collapsed details.
Tests also cover real project-driven source selection and filtering, confirmed
needs, unrelated and negated needs, project edits, TXT review, PDF bounds and error
handling, request-only progress and no project content in requests or storage.
Vendored PDF files are checked against their pinned SHA-256 hashes.
Repository tests use synthetic records and mocked HTTP: unknown products,
query scope, capability matches, mismatches, dated/inactive/unsafe records,
deduplication, failures, empty/incomplete results, no credentials and strict caps.
All ten existing local Tavily tests pass with mocked transports. No live Tavily,
private-service or model call was made. Two bounded live repository-search checks
were made for meal planning and bookings: both succeeded, both returned zero
eligible products. Source coverage remains a material constraint. These checks
do not establish availability or suitability of any hosted commercial service.
Business tests use clearly synthetic product records, not claimed real findings.
Network and service subprocesses are blocked
in the Python tests; public source responses are synthetic fixtures, not findings.

The explicit Chrome check serves only the generated public bundle and mocked API
responses on a temporary loopback server, blocking external requests. The exact
bundled PDF module/worker bytes are fulfilled through CDP to avoid flaky large
loopback HTTP transfers; the real parser still executes. It passed
real PDF.js worker extraction of a synthetic salon-project PDF, automatic business
job selection for food and salon projects, no technical classification, usable
product filtering, browser-only Not interested, unrelated-project zero results, explanations,
desktop/mobile layout and the three-request ceiling. No file upload occurred.

No deployment, package installation, service change, commit or
push has been performed for this delivery. A browser on Vercel, platform routing,
Python runtime packaging, actual source availability and account limits remain
unverified until an authorized deployment. The previous local live-source reports
are not claimed as verification of this public deployment.

## Exact next steps to get a public URL (not executed)

1. Review the generated folder. Use a Vercel account/team eligible for the intended
   demo use; confirm Hobby eligibility, current limits and available deployment
   quota in that account. No paid API key or hosted database is needed.
2. If Vercel CLI is not already available, install it **only after authorization**
   (for example, `npm install -g vercel`) and authenticate with `vercel login`.
3. In PowerShell, enter the generated folder and start a preview deployment:

   ```powershell
   Set-Location -LiteralPath 'C:\Users\crist\Desktop\Nextwise\.nextwise-vercel-demo'
   vercel
   ```

   Create/link the intended demo project, select **Other** if framework detection
   asks, use the current directory as root, no frontend build/install command,
   and `public` as the output directory. The bundle supplies Python 3.12,
   `api/index.py`, routing, headers and the 15-second function duration. Do not
   attach any private repository or copy any private environment variables.
4. Check the returned preview URL in a browser: public label, automatic source
   checks and simple suggestions, Explain why/Not interested behavior, saved-choice reload, and an unavailable-source
   state. Verify `/data/`, `/lib/`, `/.env`, `/api/load` and write APIs are
   inaccessible and no local-service or Tavily call occurs.
5. Once that preview passes, publish production with `vercel --prod` from the
   same isolated folder. Use the returned production `https://…vercel.app` URL.
   Ensure Vercel Deployment Protection permits intended visitors before sharing;
   test in an unauthenticated/incognito browser.

Vercel CLI was not found on this machine during this delivery. Remaining blockers
are authorized CLI installation, Vercel authentication/project setup, free-tier/account
eligibility and the first remote build/smoke test. No application/database
credentials or local services are needed. Allow approximately 15–30 minutes for
login, first deployment and browser checks if the platform build succeeds; any
platform-specific packaging correction cannot be confirmed offline.

References checked during implementation:
[Vercel Python runtime](https://vercel.com/docs/functions/runtimes/python),
[Vercel routing/function configuration](https://vercel.com/docs/project-configuration/vercel-json).
