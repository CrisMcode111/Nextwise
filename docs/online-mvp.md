# Online MVP bundle

Build with `python scripts/build_online_mvp.py`. Upload only `.nextwise-online-mvp`,
never the repository root, local memory or reports. The build is isolated from the
existing local project runtime. The source uses the OpenAI Responses API with
structured output and Tavily Basic Search. No provider request runs on startup.

The deployment owner must configure Preview-scoped `OPENAI_API_KEY`,
`TAVILY_API_KEY`, and a random `NEXTWISE_ACCESS_TOKEN` of at least 32 ASCII
characters in Vercel. Give the access code only to authorized testers; the
provider keys stay server-side. Enable Vercel Authentication for the preview,
configure platform rate limits and provider spending limits before activation.
The application token and per-invocation limits do **not** implement a durable
per-user or global spending cap. Do not expose the production domain until an
appropriate access and spending policy is in place.

One discovery invocation permits at most two OpenAI calls and three Tavily
Basic searches, no automatic retries, 2,048 output tokens per model call, a
32,768-byte provider request cap, a 48-second pre-dispatch deadline and a
12-second socket timeout. Vercel terminates an invocation at 60 seconds;
DNS and an individual blocked read may extend beyond the pre-dispatch deadline.
For `gpt-6.1-terra`, OpenAI's published standard pricing is $1 per million
input tokens and $5 per million output tokens; the conservative request-size
and output caps suggest roughly $0.09 per session for model use, plus up to
three Tavily credits (currently $0.024 on pay-as-you-go), excluding platform
costs, provider overhead, taxes and pricing changes. This is an estimate, not
a billing guarantee. Verify account pricing, model availability and limits
before live activation. See the [model page](https://developers.openai.com/api/docs/models/gpt-6.1-terra)
and [Tavily credits](https://docs.tavily.com/documentation/api-credits).

The UI accepts pasted text, browser-extracted TXT or text-based PDF, and public
GitHub repository URLs. Repository metadata and README excerpts are retrieved
from the fixed `api.github.com` host and must be reviewed as untrusted text. It
stores project text and choices in browser local storage. It sends the submitted
text to OpenAI and model-generated public queries to Tavily. Search excerpts
are untrusted data. Returned quotations are checked against Tavily extracts;
they have not been independently checked against publisher pages. Dates are
always labelled unverified. Model outputs and suitability are hypotheses,
not independently validated benefits. No recommendation is substituted when
providers fail or when no source quotation passes validation.

Arbitrary website ingestion is not exposed: the earlier ingestion helper
still needs an independently bounded DNS resolver and security review. The
offline fixture tests do not establish model quality, provider compatibility,
deployment security or suitability for live spending. Real validation remains
subject to explicit owner approval of provider calls.
