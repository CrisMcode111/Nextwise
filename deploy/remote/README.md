# Remote Nextwise V1 deployment preparation

Prepared 2026-11-04. Nothing has been deployed, purchased, built, pulled, stopped,
restored, or exposed. Provider integration was subsequently implemented and tested
offline; live providers remain disabled in the template.
This is the persistent Python/Node application and original Zetaris data path,
not `deploy/vercel_demo` and not a project-only replacement for the pilot.

## Architecture and honest readiness boundary

The candidate packaging assumes x86-64 Linux, Docker Engine and Compose >=2.24.4,
with persistent local storage and private SSH access. This is not a hosting choice
or a verified capacity recommendation. Resolve the prerequisites before choosing
where the backend, H-MEM, Zetaris and supported Meterless runtime will run.
An authenticated SSH tunnel is the minimum access layer because the application
session cookie and origin check do not authenticate a remote user.

| Component | Placement | State and requirements |
| --- | --- | --- |
| Python backend + Node H-MEM bridge + web UI | VPS, one container/process | Existing runtime Dockerfile and entry point; no Vercel dependency |
| H-MEM | VPS local persistent directory | Entire existing store, ledger, checkpoints, snapshots and retained responses; not an in-memory/ephemeral host or shared network filesystem |
| Original pilot artifacts/CSVs | VPS, read-only backup | Preserve exact bytes and original relative paths, including line endings |
| Zetaris PostgreSQL, API, driver, UI | Same VPS, original private Compose | Restore existing catalog and file stores; use original x86 images and private settings |
| Meterless | External supported, always-on host | Existing Windows/Mac/DGX installation, reached through private reverse SSH; do not invent a Linux/x86 Docker image |
| Tavily and model providers | External APIs | Rotated protected credentials, explicitly authorized usage and budget; no local GPU needed |

Zetaris can instead stay on another always-on private host, but it must remain
reachable for the original pilot. Meterless is optional for saved evidence/decisions
and necessary for actual AI operations. This configuration requires its TCP route
for full-stack readiness; TCP success does **not** prove model authentication.

Project Tavily and Meterless adapters are now connected behind the opt-in
`NEXTWISE_PROJECT_PROVIDERS_ENABLED` setting, protected key/token files, per-action
approval and persisted project attempt limits. They remain disabled in this template.
No live provider test has been performed. See
[deployment prerequisites](../../docs/deployment-prerequisites.md) and
[workflow configuration](../../docs/project-workflow.md).

If all services must run independently of the existing workstation, a supported
always-on remote Meterless deployment and its price must be obtained first. The
cheap Linux VPS is not a verified replacement for that runtime. The official guide
documents Windows/Mac/DGX editions, not a generic x86 Linux server package:
[Meterless guide](https://meterless.ai/help.html),
[runtime token location and CLI](https://meterless.ai/cli.html).

## Sizing pending vendor confirmation

The earlier provider/cost recommendation is withdrawn pending verified service
requirements. No hosting provider is selected. Zetaris documents a 4 vCPU / 32 GB /
256 GB SSD Azure application-server configuration and a separate recommendation of
2 CPU / 8 GB per executor for Tanzu. Neither establishes an 8 GB all-in-one minimum.
See the official references and acceptance gates in
[deployment prerequisites](../../docs/deployment-prerequisites.md).

The retained local observations are idle measurements only: about 0.65 GiB API,
2.41 GiB driver, 0.10 GiB PostgreSQL and 0.09 GiB UI. Images used about 10.16 GB,
writable layers 7.94 GB and named volumes 84 MB. All original images were amd64.
Peak load, backup headroom and supported image/licence portability remain unverified.

## Prepared files and offline verification

- `backend.override.yaml`: merges with the existing runtime Compose definition.
  Linux host networking reaches Zetaris's existing loopback publish and the private
  Meterless tunnel without relying on Docker Desktop's `host.docker.internal`.
  Backend listens on 127.0.0.1 only; all capabilities are dropped. Original mounts,
  non-root user, read-only image and full backend entry point remain in effect.
- The additional read-only `/app/data` mount preserves the existing TS decision
  validator's original-file lookup. `/artifacts` remains the configured artifact
  root; `/memory` remains the only authoritative writable H-MEM mount.
- `zetaris.restore.override.yaml`: merges with a private copy of the actual original
  `/home/crist/zetaris-platform/docker-compose.yml`. It requires all four existing
  named data volumes, removes the init dependency, makes ports private and isolates
  init/bootstrap/Caddy behind a manual-only profile. Never enable that profile.
- `remote.env.example`: contains only paths, local endpoints and settings. Secret
  values belong in separately protected files, not this template or Git.
- `scripts/verify_remote_config.py`: renders both configurations with synthetic
  settings using `docker compose config`; it does not contact the daemon, pull
  images, start containers, read credentials, or initialize data paths.

Run from the repository root:

```sh
python -B scripts/verify_remote_config.py
git diff --check
```

Both synthetic merges passed. A separate offline merge against the real private
WSL Zetaris definition also passed all six restore/isolation checks. Rendered
private configuration and stderr were captured in memory and never displayed or
written to a report. No clean Linux image build, restored-volume boot, licence
check, remote SSH route, live API request or model run has been performed.
[Compose merge tags](https://docs.docker.com/reference/compose-file/merge/),
[Linux host networking](https://docs.docker.com/engine/network/drivers/host/).

## Approval gates and deployment sequence

All following operational actions are **future steps requiring approval**. Commands
are for the new remote host after these gates; they have not been executed.

1. Approve the final provider quote, region, x86 instance, billing term, backup cost
   and maximum monthly spend. If keeping Meterless external is unacceptable, obtain
   its supported remote hosting first. Confirm Zetaris hackathon image access and
   cloud-use entitlement with the organiser; the public Zetaris Air offer is not
   proof that these particular hackathon images may be redistributed or migrated.
2. Approve required credential rotations and private transfer. Do not invalidate
   the old Meterless token or any shared registry credential without approval.
   Registry credentials go into the remote Docker credential store via protected
   stdin; no password arguments, shell history, Git, logs or public images.
3. Approve a consistent backup/cutover window. Quiesce existing application writers
   and coordinate a consistent PostgreSQL 16 backup with customer-data/driver-data.
   Preserve all existing H-MEM history, the exact artifact/export tree, original
   private Zetaris Compose directory and bind files (`init`, Spark config, etc.),
   private `.env`, encryption key pairs and installation identity. Keep an encrypted
   recovery copy and content-hash manifest. Do not rerun the exporter or bootstrap.
   Inspect the driver's small set of non-ephemeral writable-layer changes before
   declaring the volume archives sufficient; do not blindly discard them or publish
   a container snapshot. This remains a migration sign-off gate.
4. Approve provisioning and configuring **only the new VPS**: Ubuntu x86-64, Docker
   Engine, Compose >=2.24.4, key-only SSH, cloud/host firewall accepting port 22 only
   from approved users/addresses. Use the root disk for this small persistent stack.
   No DNS/domain, public HTTP port, reverse proxy service, Kubernetes or GPU is needed.
5. Approve transfer and restoration into fresh remote paths/volumes, never over local
   source volumes. Checkout the approved application revision at `/srv/nextwise/code`;
   transfer exact original bytes to `/srv/nextwise/artifacts`, the entire H-MEM root
   to `/srv/nextwise/hmem`, and private Zetaris files to `/srv/zetaris-platform`.
   Restore new remote volumes named `zetaris_pgdata`, `zetaris_customer-data`,
   `zetaris_driver-data`, `zetaris_driver-logs` from the consistent backup. They must
   already exist and contain verified data before Compose runs. Missing volumes fail
   closed. Match PostgreSQL version/UIDs and preserve Zetaris ownership and keys.
   Give UID/GID 10001 access to the **remote copy** of H-MEM and read access to
   artifacts/secrets; do not chmod/chown the source. Docker Compose file-backed
   secrets use host-file permissions, so ensure group 10001 can read the secret files.
6. Copy `remote.env.example` privately to
   `/srv/nextwise/code/.env.runtime.remote`, set the real remote paths, and place
   the three protected service key/token files in `/srv/nextwise/secrets`. Keep the registry login
   and Meterless/provider keys separate. Verify hashes and permissions before boot.
7. Approve private route setup. On the existing supported Meterless host, create a
   supervised reverse tunnel to the VPS, with SSH server permission restricted to
   remote listen address `127.0.0.1:18088`, key-only authentication and no public
   forwarding (`GatewayPorts no`). Do not start a second runtime or import its data:

   ```sh
   ssh -N -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=3 -R 127.0.0.1:18088:127.0.0.1:8088 gateway-user@REMOTE_HOST
   ```

8. Approve downloading/building the existing images on the fresh server. Resolve and
   pin image digests after verifying the existing Dockerfile's Python/Node tags.
   No image has been built here. The private Zetaris environment must retain the
   matching original image versions; a clone of this repository cannot reconstruct
   the private stack or original database state.
9. From an SSH session **on the new server only**, validate the private Zetaris
   configuration without printing rendered secrets, then start only restored runtime
   services. Never run `down -v`, initialization, bootstrap, prune, or force-recreate:

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

   The server must be empty/new for these commands; no existing deployment is to be
   recreated. Do not use the existing general launcher's `--external-compose` option
   for this migration, because its broad `start` is not restricted to restored services.
10. Approve acceptance tests on restored copies: liveness/readiness (one read-only SQL
    query; no paid call), all six original table/content checks, saved decision and
    snapshot integrity, new-project history after restart, and backup restore rehearsal.
    H-MEM's normal pilot reads append read-audit events; test with a separate memory
    copy first, then explicitly approve normal auditing on the remote authoritative
    store. Do not inject mocked results into production to claim a complete live agent.
    Keep original source data intact and one authoritative writable backend at cutover.
11. For private browser access, forward the same local port so existing origin checks
    remain valid, then open `http://127.0.0.1:8765` (pilot) or `/projects`:

    ```sh
    ssh -N -L 8765:127.0.0.1:8765 operator@REMOTE_HOST
    ```

    Public multi-user access would require real authentication and TLS, not just
    `NEXTWISE_PUBLIC_ORIGIN`; that is outside this minimum private deployment.

## Remaining blockers

- Live provider authentication, model schema support and cost remain untested.
  The connected adapters require approved replacements, limits and explicit opt-in.
- Meterless needs an approved always-on supported external host/private tunnel;
  a fully workstation-independent deployment has no verified Meterless package/quote.
- Exposed credential replacements, private registry access and hackathon licence
  portability require owner confirmation; no revocation or account action was done.
- Consistent backup set, encryption/install identity and writable-layer migration
  sign-off are outstanding. No backup/volume contents were modified in this work.
- Linux image build/digest verification, secret permissions, restored-stack boot,
  peak memory/load test, recovery rehearsal, and final provider checkout are unverified.
