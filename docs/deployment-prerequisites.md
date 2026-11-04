# V1 external prerequisites (2026-11-04)

No hosting choice or purchase is made here. Project provider wiring is implemented;
see [project workflow](project-workflow.md) for opt-in configuration and approval.
No provider request, runtime launch, rebuild or volume modification was performed.

## Meterless compatibility

The existing client uses bearer-authenticated `/v1/chat/completions`, model
`meterless/auto` by default, with bounded schema-constrained JSON. Endpoint/model
are configurable per attempt. An HTTPS service or private tunnel ending at
backend loopback can carry this protocol; the route is not established here.

The [official guide](https://meterless.ai/help.html) documents full runtime
endpoints on Windows, Mac M5+ and DGX Spark. DGX is a persistent systemd service;
Windows currently has no start-at-login support. The Linux Node companion is a
relay connector to an existing model server, not a generic x86 Linux runtime.
The browser Session Hotspot refuses structured JSON output and depends on an open
tab, so it does not satisfy this adapter. `ns` is a loopback-only CLI; this Python
HTTP client does not depend on it.

These are current public docs, not certification of the installed hackathon build.
Before deployment: confirm a supported always-on runtime, private reachability,
replacement runtime token and provider keys, an approved model supporting the
requested schema and token budget, and account spending limits. A separately
approved live acceptance request is still necessary; mocks establish no live
provider compatibility, authentication, answer quality or cost.

## Zetaris requirements

The [official hardware page](https://kbase.zetaris.com/knowledge/product-hardware-requirements)
specifies 4 vCPU, 32 GB RAM and 256 GB SSD for an Azure application-server VM.
That is a deployment-specific reference, not a proven minimum for these Docker
images. The [Tanzu installation guide](https://kbase.zetaris.com/knowledge/installing-zetaris-on-vmware)
recommends at least 2 CPU and 8 GB RAM **per executor**, plus PostgreSQL and
persistent storage. It does not establish an 8 GB total-stack requirement.

Existing local packaging uses amd64 images, PostgreSQL, driver, API and UI, with
four original persistent volumes and retained private installation/encryption
configuration. The prior idle observation (about 3.25 GiB across those containers)
is not a peak-memory test. No code-level limit proves a smaller supported host;
full sizing depends on Spark driver/executors, concurrency, disk growth and headroom.
The retained `conf/spark-defaults.conf` contained no active allowlisted numeric
driver/executor memory, core or instance overrides in the read-only check. This
does not resolve image defaults or establish a supported deployment minimum.

Before deployment: obtain Zetaris confirmation for sizing and hackathon image/licence
portability, restore access to the private registry with approved replacement
credentials, preserve original installation identity and encryption keys, and
prepare a consistent database/filesystem/writable-layer backup. Test restore,
table hashes, H-MEM history and realistic peak usage on a separate destination.
Never run init/bootstrap over the original volumes.

## Remaining acceptance gates

Approve credential rotations without embedding values in commands, source or
reports; provision replacements in protected files after they exist. No keys were
revoked or replaced here. Keep provider calls disabled until authorized.

After selecting supported service arrangements: verify image digests and a clean
Linux build, private routing, protected-file permissions for UID 10001, restored
data integrity, restart persistence and backup recovery. Public access additionally
needs authentication and TLS; the current private session/origin checks are not
multi-user authentication. No deployment or push is part of this change.

## Offline verification

85 tests passed across project workflow/adapters, runtime/startup processes,
business and staged assessment, output contracts, Tavily, and model transport.
Providers were mocked; workflow tests used real H-MEM with temporary copies and
verified original memory and both pilot namespaces unchanged. Browser tests
confirmed cancellation sends no provider request. The configured lifecycle
persisted a human decision and reopened it after backend reconstruction; failed
attempts retained their limits across restart. Saved evidence tampering and
fabricated quotations remained rejected.

Synthetic Compose validation passed for private routes/ports, three protected
service secret mounts, persistent mounts, external restored volumes and excluded
bootstrap. `git diff --check` passed. Task-file credential pattern checks found
no matches; no private credentials document was opened. This is offline validation,
not proof of live SQL, model/provider readiness, a Linux image build or recovery.
