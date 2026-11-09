# V1 remote deployment prerequisites

Updated 2026-11-09. Preparation only: no paid calls, provisioning, registry pulls,
credential reads or data modifications. No completed tests repeated.

## What the existing architecture can deploy

The complete Python backend, web UI and Node H-MEM bridge run as one persistent
Linux amd64 container. Restore the original Zetaris Docker stack on that host or
another private always-on host. Preserve the entire H-MEM store, exact artifact/CSV
bytes, catalog, file stores, private installation settings and encryption keys.
Private browser access uses SSH forwarding; the laptop becomes only a client.

`deploy/remote/backend.override.yaml` supports saved evidence, decisions and project
history without a Meterless host or Tavily/Meterless secret files. It still needs
real Zetaris and original pilot data. AI operations remain disabled. Readiness
skips optional Meterless connectivity rather than waiting for an absent runtime.

## Meterless: compatibility boundary

The [official guide](https://meterless.ai/help.html) documents full endpoints on
Windows x64, Mac M5+ and DGX Spark. DGX explicitly supports headless installation
and a persistent system service. Windows supports CPU mode but has no built-in
start at login. A generic Linux amd64 full runtime is not documented. The vendored
H-MEM reference is portable memory code, not an inference daemon.

The browser Session Hotspot needs an open tab and rejects structured output.
The Linux Persistent Hotspot companion forwards to an existing model server; it
runs no model and its strict-schema compatibility is not established by the guide.
Neither is an established drop-in replacement for Nextwise's model adapter.

Full AI needs an independently hosted supported runtime, a model accepting strict
`response_format` JSON schema, non-streaming responses and the 4096-token project
budget. Use HTTPS or a private tunnel ending at backend loopback, protected token
files and the existing per-action authorization and persisted attempt limits.
Service-root and `/v1` base URLs now both construct the right completions URL,
including a gateway prefix. No schema fallback or direct-provider bypass was added.

Merge `deploy/remote/providers.override.yaml` last to mount the provider secrets
and require runtime connectivity. Providers stay disabled until explicitly enabled
in the env file. An open TCP port proves neither authentication nor schema support.
A supported remote runtime/release, authorized model access and permission for a
later live acceptance request remain external. A laptop-hosted tunnel does not
meet independent deployment.

## Zetaris: hosting requirements resolved

The current [official Docker bundle guide](https://github.com/zetaris/getting-started/blob/main/docs/install/updated_zetaris_installation_guide.md)
documents Linux Docker Engine, amd64 images, 4 CPUs and **8 GB available to Docker**
recommended (preflight rejects below 6 GB), and 15 GB free disk plus data/logs.
Its example settings are `ZSPARK_DRIVER_MEM=2g`, `ZSPARK_DRIVER_CORES=2`,
`ZSPARK_MASTER_URL=local[2]` and `ZETARIS_API_MAX_HEAP=1g`. Apply only to a matching
private bundle that consumes those variables; preserve existing installation
settings for the initial restore rather than guessing at its version's mapping.

The earlier Azure 32 GB server reference and Tanzu per-executor guidance are not
requirements for this bundle. Vendor sizing confirmation is no longer a blanket
blocker for planning the Docker route.

For cohosting Nextwise and Zetaris, **4 vCPU / 16 GB RAM / 80 GB SSD** is an engineering
planning recommendation, not a measured production minimum or a selected purchase.
It allows headroom for Nextwise's 1 GB limit, the OS and backups. Previously recorded
images and writable layers already occupied about 18 GB, so 15 GB total disk would
not fit this preserved installation. Increase disk for the actual backup, restored
data, build cache and recovery copy. Validate capacity on the destination before
accepting traffic; do not upgrade the original images just to match a newer example.

The [official managed AWS route](https://github.com/zetaris/getting-started/blob/main/docs/install/managed-aws-cluster-guide.md)
requires account/IAM approval and infrastructure charges. It supplies separate
cluster credentials and JDBC access; it is not established as a drop-in replacement
for Nextwise's current REST SQL contract, catalog and filestore. Restoring the
original Docker stack is the shortest path without an adapter/data migration.

## Only external approvals/dependencies remain

1. Remote host/budget and private operator SSH access.
2. Valid Zetaris registry access, matching private bundle, and entitlement covering
   the remote installation and intended duration. The official guide distinguishes
   the platform licence from the recipes' Apache licence and limits uncontracted
   evaluation to 30 days. Confirm the actual account entitlement; do not assume
   hackathon access is perpetual.
3. Owner-provisioned replacement credentials, preserved installation/encryption
   identity, and a consistent backup/cutover window. Never initialize source volumes.
4. For AI only: supported remote Meterless hosting/release, model/provider access,
   protected replacement tokens, budget and live-request approval.

Linux image build, restored boot, recovery and live model acceptance are future
destination release checks. They were not performed here and do not call for
another laptop test campaign. Follow the [remote runbook](../deploy/remote/README.md).
