# Remote Nextwise V1

Updated 2026-11-09. Nothing deployed, purchased, pulled or restored. No completed
local/end-to-end tests repeated. See [resolved requirements](../../docs/deployment-prerequisites.md).

## Remote arrangement

| Component | Placement |
| --- | --- |
| Complete Python backend, web UI, Node H-MEM bridge | Persistent Linux amd64 Docker host |
| Entire H-MEM history | Backend local disk, one authoritative writer |
| Original artifacts and CSV snapshot | Exact read-only backup on backend host |
| Zetaris PostgreSQL, driver, API, UI | Original private Docker bundle, restored state on this or another private host |
| Meterless inference | Optional for saved work; full AI needs a supported always-on remote runtime |

Base Compose runs the full backend/pilot with AI disabled. Only the Zetaris key is
needed. Saved evidence, decisions and project history remain available; new AI
output requires the provider overlay. The laptop is only an SSH/browser client.

Plan 4 vCPU / 16 GB RAM / 80 GB SSD for the combined stack, increasing disk to fit
the actual consistent backup, restored data and recovery copy. This is an allowance
above the official bundle guidance, not a measured peak-load guarantee. Docker
Engine 25+ is recommended; Compose >=2.24.4 is required for the merge tags.

## Shortest remaining deployment sequence

1. Obtain approved hosting/budget, valid Zetaris image access/licence duration,
   the matching private bundle and protected replacement credentials. Remote
   Meterless can follow separately if saved-work deployment comes first.
2. In an approved backup window, preserve consistent PostgreSQL 16 state, all four
   volumes, original keys/install identity, private bundle/bind files and any
   non-ephemeral driver writable-layer changes. Preserve the complete H-MEM root
   and exact artifact tree. Retain an encrypted recovery copy and hash manifest.
3. Provision a fresh Linux destination. Restore only to new paths/volumes. Never
   run init/bootstrap over original state. The restore overlay requires existing
   `zetaris_pgdata`, `zetaris_customer-data`, `zetaris_driver-data`,
   `zetaris_driver-logs`; it fails if volumes are missing. Keep original image
   versions, ownership and private installation configuration.
4. Checkout the approved revision at `/srv/nextwise/code`; put artifacts at
   `/srv/nextwise/artifacts`, memory at `/srv/nextwise/hmem`, private bundle at
   `/srv/zetaris-platform`, and Zetaris key at `/srv/nextwise/secrets/zetaris_api_key`.
   Copy `remote.env.example` privately to `.env.runtime.remote`. Give UID/GID 10001
   write access to the remote H-MEM copy and read access to artifacts/key files.
   Compose file-backed secrets retain host permissions. Do not change source ACLs.
5. After deployment approval, validate privately, build on Linux, and start only
   the restored services below. Pin verified image digests for the release. The
   Dockerfile includes Node's `libatomic1` dependency and checks TS module import
   during a future build without opening H-MEM or contacting any provider.

Future commands **on the fresh remote host only**, not executed:

```sh
cd /srv/zetaris-platform
docker compose --env-file .env -f docker-compose.yml -f /srv/nextwise/code/deploy/remote/zetaris.restore.override.yaml config --quiet
docker compose --env-file .env -f docker-compose.yml -f /srv/nextwise/code/deploy/remote/zetaris.restore.override.yaml up -d --no-deps --wait postgres
docker compose --env-file .env -f docker-compose.yml -f /srv/nextwise/code/deploy/remote/zetaris.restore.override.yaml up -d --no-deps --wait driver
docker compose --env-file .env -f docker-compose.yml -f /srv/nextwise/code/deploy/remote/zetaris.restore.override.yaml up -d --no-deps --wait api ui
cd /srv/nextwise/code
docker compose --env-file .env.runtime.remote -f deploy/runtime/compose.yaml -f deploy/remote/backend.override.yaml config --quiet
docker compose --env-file .env.runtime.remote -f deploy/runtime/compose.yaml -f deploy/remote/backend.override.yaml build backend
docker compose --env-file .env.runtime.remote -f deploy/runtime/compose.yaml -f deploy/remote/backend.override.yaml up -d --no-deps --wait backend
```

Never use `down -v`, init/bootstrap, prune, broad launcher `--external-compose`,
or source volume recreation. Do not enable the `manual-recovery-only` profile.
Start only the explicit restored services; a newer bundle's additional services
are not automatically included. Keep API/UI/backend loopback-only; database/debug
ports remain unpublished. A remote Zetaris URL can replace the local API route.

6. Accept the destination once: restored table/content identities, saved history
   and decision integrity, restart persistence and backup recovery. Normal H-MEM
   reads append audit events; use a separate copy first, then approve authoritative
   writes at cutover. `/health/ready` performs a Zetaris SELECT, never inference.
   Keep one authoritative writer; no repeated laptop test campaign is needed.
7. From the operator computer:

```sh
ssh -N -L 8765:127.0.0.1:8765 operator@REMOTE_HOST
```

Open `http://127.0.0.1:8765` or `/projects`. Closing the client leaves the remote
stack running. This minimum deployment stays private: session/origin checks do
not authenticate public users.

## Optional full AI activation

Obtain a supported always-on remote Meterless runtime independent of the laptop.
Windows x64, Mac M5+ and DGX Spark have documented full endpoints; DGX documents
headless/system-service use. Windows needs separately supervised startup. The
Linux preview companion only forwards to another model server and does not
establish strict-schema compatibility.

Set `NEXTWISE_METERLESS_URL` to an HTTPS service root or `/v1` base (gateway prefixes
supported). Alternatively supervise this tunnel on the **remote Meterless host**,
with a restricted SSH forwarding key and `GatewayPorts no` on the backend host:

```sh
ssh -N -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -R 127.0.0.1:18088:127.0.0.1:8088 gateway-user@BACKEND_HOST
```

Set the approved model and protected Meterless/Tavily file paths in the private env
file. Add `-f deploy/remote/providers.override.yaml` **last** to backend Compose
commands. This requires TCP connectivity while keeping provider usage disabled by
default. Explicitly enable `NEXTWISE_PROJECT_PROVIDERS_ENABLED=true` only after
usage approval. Per-action approval and persisted limits still apply. One later
approved live JSON-schema acceptance request is needed; TCP success is insufficient.

## Validation boundary

No test suites or previous Compose verifier were rerun. The verifier was updated
for the base and optional provider overlay for later release use. The Linux image
build, restored-stack boot and live-provider acceptance remain unrun.
Change-specific Python syntax checks, four endpoint-construction assertions and
`git diff --check` passed. These checks used no network, credentials or data stores.
