# P0 runtime packaging verification — 3 November 2026

Backend packaging and offline verification are implemented. No deployment or
clean-environment success is claimed. No paid API calls, production H-MEM bridge
reads/writes, data resets, service launches, image builds or package installations
were performed. Local process smoke testing used only a loopback mock SQL service.

## Changes

| Files | Change |
| --- | --- |
| `scripts/runtime_config.py` | Shared validated service URLs, organization, model, bind address, paths, Node executable, health timeout and optional-gateway requirement. Zetaris and Tavily support exclusive environment or `_FILE` credentials with bounded/redacted errors. |
| `scripts/serve_runtime.py` | Unattended entry point; validates configuration before configured module imports. No inference or hidden prompt. |
| `scripts/nextwise_app.py` | Unattended lifecycle, preflight, configured listener/origin, Secure cookies for HTTPS origins, liveness/readiness endpoints and appropriate server-secret recovery messages. Legacy interactive startup remains available. |
| `scripts/runtime_health.py`, `scripts/probe_runtime.py` | Read-only static preflight and container readiness. Network readiness only issues Zetaris SELECT 1 and gateway TCP probe. No H-MEM bridge access, Tavily search or inference. |
| `scripts/start_runtime.py` | Starts only supplied existing external Compose containers, then builds/starts the backend and waits for health. Stops on errors and suppresses potentially secret external output. No guessed external stack/image/volume names. |
| `deploy/runtime/Dockerfile`, `compose.yaml`, `runtime.env.example`, `.dockerignore` | Python/Node backend image, non-root/read-only execution, explicit secret, required existing bind mounts, health probe and loopback-only published port. Private data and secrets are excluded from the build context. |
| `scripts/investigation_memory.py` | Configured artifact/memory roots and Node executable; bridge/code remains under the code root. No H-MEM format or vendor changes. |
| `scripts/integrate_zetaris.py`, `validate_zetaris_profile.py` | Configured endpoint, organization, artifact/snapshot paths and short health-query timeout. Export reproduction uses the configured input root without altering the original exporter. |
| `scripts/analyze_sources.py`, `collect_sources.py`, `evaluate_extraction.py`, `update_discovery.py` | Existing adapters use configured artifact roots; model transport uses configured gateway/model. No live commands executed or allowances expanded. |
| `scripts/assess_discovery.py`, `reassess_discovery_once.py`, `reassess_opportunity_once.py` | Availability probes use the configured gateway instead of a fixed local port. Existing authorization caps, prompts and strict validators remain. |
| `scripts/tavily_discovery.py` | Optional secret-file credential support; API endpoint and spending bounds stay unchanged. Base Compose does not forward Tavily credentials. |
| `.gitattributes`, `.gitignore` | Prevent exporter checkout conversion; ignore private runtime environment/secret locations. |
| `tests/test_runtime.py`, `test_runtime_process.py` | Configuration, redaction, adapter routing, failure paths, dependency scope, real HTTP handler, no-prompt startup/cleanup, service-launch safety and native subprocess smoke test. |
| `docs/runtime.md`, `README.md` | Configuration/startup guide, preservation requirements, exact limitations and release gates. |

## Results

- **16 new runtime tests passed.** The process test starts the actual backend with
  installed Python/Node, synthetic temporary memory and loopback fake SQL. It
  verifies unattended startup, liveness, readiness, exactly one SELECT 1, no model
  HTTP requests and unchanged temporary store bytes. Windows process termination
  is not claimed as a Linux graceful-SIGTERM test; interrupt cleanup is tested
  separately in process-local mocks.
- **67 existing regression tests passed:** Zetaris integration/profile/export,
  public demo, Tavily, schema transport, business assessment, semantic output
  contract and staged opportunity tests. Staged H-MEM operations use temporary
  copies only. Existing production-memory test classes were not run.
- **4 existing local HTTP tests passed**, covering session/origin protections,
  service/authentication failures, disconnect and duplicate listener rejection.
  Total: **87 tests passed** across these targeted runs.
- Docker Compose parsed the package offline with
  `docker compose -f deploy/runtime/compose.yaml config --no-interpolate --no-env-resolution --quiet`:
  **exit 0**. The CLI warned that the user's Docker config file was inaccessible;
  no daemon or account access was needed for parsing.
- Real offline preflight passed Python, Node/TS import, vendor hashes, pilot
  snapshot lineage and existing memory JSON/ledger/permission checks. It exited
  **1 as expected** for the absent configured Zetaris credential. SQL and gateway
  connectivity were not tested against real services.
- Python syntax and `git diff --check` passed.

## Preservation

All 14 original private memory files retain aggregate SHA-256
`a5b5d4669c0c9eb994d99d516a40784f3112f1a56c6294324163f4e32b163899`.
The 24 pinned vendor files match their recorded hashes. The exporter retains
SHA-256 `56f00cf457708474785aed2017a7d6d6fadaa4f32e7a3b3d1f1ab0ece6c8ae53`.
No tracked data, web assets or Vercel demo files changed. Existing untracked
`zetaris.txt` is untouched. No real application credential was supplied.

The original export includes the exporter source hash in snapshot identity;
configuration therefore lives in its callers. Git blobs for several pilot JSON
inputs and CSVs differ in line endings from the original local hash-verified bytes.
A clone alone is insufficient: restore/mount the exact original artifact backup,
not rewritten exports or normalized files. This is detected by preflight.

## Still unresolved / release gates

1. Verify existing Zetaris and Meterless/Nightshift deployment definitions,
   provider configuration and exact images. Repository/docs, command and global
   npm inspection did not locate them. Docker daemon/container metadata was
   unavailable. External services are configurable; replacement stacks are not
   fabricated. Starting existing containers is supported, provisioning/restoring
   those services on a clean host is not yet established.
2. Build the actual backend image on a clean Linux/Docker host; verify base-image
   tags/digests, Node/TypeScript operation and non-root bind/secret permissions.
3. Restore a private copy of complete H-MEM and original artifacts. Verify service
   networking: host loopback services may not be reachable through Docker host
   addressing on every platform. Do not expose Zetaris publicly to solve this.
4. With real credentials, pass dependency readiness and load/reconcile all six
   live Zetaris tables. Verify unavailable-service and invalid-secret diagnostics.
5. On isolated restored data, verify explicit decision persistence across restart,
   preserved evidence/allowances and graceful Linux SIGTERM cleanup. No paid API
   call is required for runtime acceptance.

Authentication for public access, useful live model reasoning and live Tavily
validation remain separate work. The package deliberately publishes only to
loopback and does not enable a new autonomous agent workflow.
