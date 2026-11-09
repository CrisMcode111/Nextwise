# Unattended backend runtime

This packages the existing single-process Python backend and Node/H-MEM bridge.
It preserves the fixed pilot, strict validators, original CSV snapshot, consumed
model allowances and existing private memory. It does not change the Vercel demo,
initialize memory, import artifacts, register Zetaris tables or start inference.

The backend image and Compose definition have **not been built or started in a
clean environment**. Packaging is implemented; deployment success is unverified.

For remote V1, use the current [remote runbook](../deploy/remote/README.md) and
[resolved service requirements](deployment-prerequisites.md). The sections below
describe the original local packaging; the remote overlays provide saved-work
deployment separately from optional AI activation.

## Prerequisites and unresolved service definitions

The backend needs Python 3.11+, Node 24+ with TypeScript transformation, the pinned
vendor files, the original artifact tree and both complete private H-MEM stores.
The Dockerfile pins Python 3.11.9 and Node 24.22.2 image tags. Base-image availability,
Linux compatibility and immutable image digests remain to be verified.

Zetaris remains the existing external deployment, with its six registrations and
file store. Meterless/Nightshift remains an external gateway. No verified launch
definition or image for either exists in this repository. Repository/docs search,
command lookup and the available global npm package list did not locate one.
The Docker daemon was unavailable during implementation, so installed container
metadata, volumes, image names and Compose labels could not be verified.

Do not invent a replacement Zetaris stack. Locate/restore its existing deployment
definition and volumes privately. The launcher can start supplied existing stacks;
otherwise start them using their independently verified procedure. A gateway is
optional for displaying saved evidence and saving decisions. Startup does not
activate any of the historical model runners.

A clone alone is not a pilot-data restore. Git's stored blobs for several pilot
inputs and CSVs use different line endings from the original hash-verified local
bytes. Restore/mount the exact original artifact backup along with H-MEM; do not
normalize line endings or regenerate exports to make checks pass. The exporter
itself is now marked `-text` in `.gitattributes` so checkout conversion cannot alter
its identity. Its content and recorded hash are unchanged.

## Configuration

Set environment variables before starting Python; configured module paths are
resolved at import time. Relative filesystem paths resolve against the code root,
not the shell working directory. Service URLs accept HTTP(S), without embedded
credentials, queries or fragments. HTTPS is appropriate for remote services.

| Setting | Default / purpose |
| --- | --- |
| `NEXTWISE_ARTIFACT_ROOT` | Code root; directory containing the existing `data/` tree. Keep its relative artifact names intact. |
| `NEXTWISE_MEMORY_ROOT` | `<artifact root>/data/memory/hmem`; full existing private store, including snapshots and retained-response subdirectories. |
| `NEXTWISE_ZETARIS_SNAPSHOT` | Existing `20261024T151413Z-fdf0c15b-csv-5fa0db458643` under the artifact tree. Overrides location, not snapshot identity. |
| `NEXTWISE_HOST`, `NEXTWISE_PORT` | `127.0.0.1`, `8765`; container listens on `0.0.0.0` internally. |
| `NEXTWISE_PUBLIC_ORIGIN` | Empty; optional exact external origin for an independently secured reverse proxy. Adds Host/Origin acceptance and Secure cookies for HTTPS. |
| `NEXTWISE_ZETARIS_URL` | `http://127.0.0.1:8888` for native Python; avoids IPv6-first `localhost` when Docker publishes only IPv4 loopback. Compose uses `http://host.docker.internal:8888`. Base URL may include a reverse-proxy path prefix. |
| `NEXTWISE_ZETARIS_ORG_ID` | `1`; organization header. Existing database name `nextwise` is preserved. |
| `NEXTWISE_ZETARIS_API_KEY` / `_FILE` | Required for unattended startup. Prefer a private UTF-8 secret file. Never provide both. |
| `NEXTWISE_METERLESS_URL` | `http://127.0.0.1:8088`; transport appends `/v1/chat/completions`. |
| `NEXTWISE_MODEL` | `meterless/auto`; existing returned-route validators and authorization caps remain unchanged. |
| `NEXTWISE_NODE` | `node`; executable name or absolute executable path. |
| `NEXTWISE_DEPENDENCY_TIMEOUT` | `3` seconds per SQL/TCP dependency check; allowed range 1–30. |
| `NEXTWISE_REQUIRE_METERLESS` | `false`; when true an unreachable gateway makes readiness fail. TCP checks do not prove model/provider authentication. |
| `NEXTWISE_UNATTENDED` | `false`; `serve_runtime.py` always selects unattended mode. A configured Zetaris key also selects it in the original app entry point. |
| `TAVILY_API_KEY` / `TAVILY_API_KEY_FILE` | Optional local discovery credential; same exclusive secret-file support. Leave absent to avoid Tavily spending. Not forwarded by the base Compose definition. |

Secrets are never logged or returned by health endpoints. Secret files are bounded
to 16 KB and one nonempty line. The code does not load `.env` files implicitly;
Docker Compose loads the explicitly supplied interpolation file. Gateway/provider
credentials belong in the verified gateway deployment. The historical live-model
CLIs retain their explicit authorization guards and hidden-token prompts.

## Native unattended startup

Use the existing Python and Node installations. Configure the Zetaris secret file
and any relocated paths/URLs through the service manager environment, then run:

```powershell
python -B scripts/serve_runtime.py
```

For the existing private Compose settings file, native startup can load its
protected key-file paths explicitly:

```powershell
python -B scripts/serve_runtime.py --env-file .env.runtime
```

This maps `NEXTWISE_ZETARIS_SECRET_FILE` to the native API-key-file setting and
converts `host.docker.internal` service URLs to the same ports on `127.0.0.1`.
Existing process settings take precedence. The file is parsed as assignments,
never executed, and credential values are never printed. Provider usage remains
off unless explicitly configured and separately authorized through the interface.

No terminal input is requested. Missing credentials, incompatible Node, missing
memory or invalid pilot artifacts stop startup with fixed dependency diagnostics.
No empty store is created. SIGTERM/Ctrl+C closes the listener. The original
`scripts/nextwise_app.py` still supports the interactive local workflow when no
unattended flag or configured key is supplied. In unattended mode, after an explicit
disconnect or rejected key, correct the configured secret and restart the process;
there is no console prompt waiting for a replacement key.

## Container startup

Copy `deploy/runtime/runtime.env.example` to `.env.runtime` and fill its blank
absolute paths privately. The three required host inputs are:

1. An existing artifact directory containing `data/`, including the exact pilot
   files and CSV snapshot. It is mounted read-only.
2. The complete existing `data/memory/hmem` directory, mounted read/write. Both
   `nemotron-lightning-requirements-extraction` and `update-discovery` must contain
   their existing `state.json` and `ledger.jsonl`; retain all other files too.
3. An existing private file containing only the Zetaris API key.

Use forward slashes for Windows paths in the Compose environment file. Bind mounts
have `create_host_path: false`; nonexistent directories are errors. Nothing is
copied into an empty volume. The image runs as UID/GID 10001 with a read-only root
filesystem. Verify mount/secret access for that identity on the target host; the
launcher never changes ownership or permissions. Back up with existing writers
stopped before using a relocated copy. Do not run two backends against this store.

When the existing services are already running:

```powershell
python -B scripts/start_runtime.py --env-file .env.runtime
```

To also start existing service stacks, append `--external-compose` once for each
**verified existing** Compose file. No default paths are assumed. Each external
stack runs from its own definition's directory with `docker compose ... start`,
which only starts existing containers and cannot provision replacement volumes.
It retains its existing environment/project resolution. Supply the correct existing Compose
project environment yourself; do not use a new project name for an existing data
stack. This wrapper supports standalone Compose files, not a guessed combination
of multi-file overrides. If the existing stack needs overrides, use its verified
startup procedure separately. Restoring/provisioning those services on a new host
remains external work until their definitions are verified.

The backend runs `up -d --build --wait --wait-timeout 120`. No command removes
containers, resets volumes, registers data or reruns pilots. External command output
is suppressed because third-party configuration may print secrets. Investigate a
failure privately with Docker tooling and backend health/logs. Starting external
stacks does not attest that they have no independently configured startup jobs.

Compose publishes the backend on host loopback only. `host.docker.internal`
defaults target existing host services. Host loopback bindings are not necessarily
reachable from Linux containers: verify platform routing or configure reachable
private endpoints/shared Docker networks once the existing stacks are known.
Never fix this by publishing the Zetaris API openly.

Existing session/origin checks are not user authentication. Keep the service
private; setting `NEXTWISE_PUBLIC_ORIGIN` does not make it safe for anonymous access.

## Health checks

- `GET /health/live`: listener is alive; no dependency access.
- `GET /health/ready`: checks Python/Node, pinned vendor hashes, exact CSV/artifact
  lineage and structural/read-write access to existing stores, then one authenticated
  Zetaris `SELECT 1` and, when `NEXTWISE_REQUIRE_METERLESS=true`, a Meterless TCP
  connection. Returns 503 on required failure. Otherwise Meterless is marked
  `not_checked`, with no connection attempt or wait for an optional runtime.
- `python -B scripts/runtime_health.py`: the same local checks, **no network**.
  Without a configured Zetaris key it correctly exits 1 with a credential error.
- Add `--network` only when dependency access is intended. This makes the bounded
  SQL/TCP checks, never inference, Tavily search, or an H-MEM bridge read.

Readiness does not validate full live Zetaris table content, provider credentials,
semantic model quality, crash recovery, disk capacity or future write success.
It checks memory JSON/ledger structure and permissions without writing test files,
opening auditing H-MEM reads, creating locks or repairing data. Existing application
reads still enforce the original full evidence reconciliation.

## Offline verification and release gates

Run the targeted configuration/startup suite with:

```powershell
python -B -m unittest discover -s tests -p 'test_runtime*.py' -v
```

It uses mock service transports, an in-memory HTTP handler, temporary stores and
fresh import subprocesses. One process test starts the real unattended listener
with installed Node and a loopback-only mock SQL server, using temporary synthetic
stores. No model or external service calls occur. Do not run
the entire historical suite indiscriminately: some older tests read the production
H-MEM through its auditing bridge.

Before claiming reproducibility/deployment, a clean host must build the actual
image, verify Node/Python and UID access, restore a private copy of the preserved
state, start the independently verified existing services, pass readiness, load
all six live tables, and demonstrate an explicitly chosen decision surviving a
backend restart. Verify bad-key and stopped-service failures and graceful shutdown.
Compare evidence/allowances before and after; do not use original data for write
tests. No paid API call is necessary for these runtime checks. Model usefulness,
live Tavily, public authentication and a new AI workflow remain separate work.
