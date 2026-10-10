# Hosted AI infrastructure proposal — 2026-10-10

**Proposed, not provisioned. Production NO-GO.** This prepares the owner's dedicated
Render database and separately hosted vLLM direction. No paid resource, model download,
provider terms, live migration or production inference URL is approved by this document.
Keep the existing local Ollama configuration and user data intact.

## Observed inventory and staging sequence

The authenticated, read-only Render inventory returned HTTP 200. The existing AI
Docker web service is in **Frankfurt**, on `main`; its Docker root, command and
`/core-ready` configuration were repaired and native auto-deployment disabled.
The expanded same-owner inventory returned **zero PostgreSQL resources**, with
no 100-item truncation. No existing AI-specific Render database was discovered
in this authorized account. Recheck inventory before creation; any later candidate
requires ownership, environment, schema and intended-use verification.
No database connection credentials were retrieved and no live schema was inspected.

Use one approved isolated staging backend/environment first. The existing service's
intended staging/production designation needs owner confirmation; do not attach
staging data to the public production service. Do not create a duplicate web service
or incur its cost without approval. Recheck the staging service region before creation.

| Proposed resource | PostgreSQL | Plan / storage | Estimated monthly database cost |
| --- | --- | --- | --- |
| `onesa-ai-db-staging` | 16 with `vector` | `0.5c-1g`, 5 GB | $19 compute + $1.50 storage = **$20.50** |
| `onesa-ai-db-production`, only after staging acceptance | 16 with `vector` | `1c-2g`, 20 GB | $40 compute + $6 storage = **$46.00** |

These are single-instance planning estimates, not invoices or HA designs. Prices
exclude tax, workspace subscription, extra exports, bandwidth, backend and identity
worker compute. Storage autoscaling is initially off; monitor capacity and approve
increases. The account's actual quote and recovery retention must be confirmed.
[Render pricing](https://render.com/pricing?trk=article-ssr-frontend-pulse_little-text-block),
[storage and bandwidth pricing](https://render.com/articles/how-much-does-cloud-application-hosting-cost-for-small-businesses).

Reviewable resource parameters are in
[`ai-db-staging.json`](../../infra/deployment/proposals/ai-db-staging.json) and
[`ai-db-production.json`](../../infra/deployment/proposals/ai-db-production.json).
They are proposals, not executable API payloads or automatically applied Blueprints.
The historical root `render.yaml` includes a different database name; **do not apply
it as well**. Choose a verified reused resource or the single approved proposal,
then explicitly reconcile the Blueprint before any future application.

## Database acceptance and permissions

Use the corresponding service's same Render account/region and actual **Internal
Database URL**. Render supports PostgreSQL 16 and the `vector` extension.
[Connection guidance](https://render.com/docs/postgresql-creating-connecting),
[supported extensions](https://render.com/docs/postgresql-extensions).

The established setting is **ONESA_DATABASE_URL**. SQLAlchemy uses **psycopg 3**;
its explicit supported driver prefix is `postgresql+psycopg://`. A provider
`postgresql://` URL must be parsed/checked by the operator and deliberately adapted
for this installed driver, preserving its actual host, database and correctly
escaped credentials; do not blindly rewrite an unknown URL or introduce a second
setting. For Render internal connections, use **sslmode=require** and inspect
`pg_stat_ssl` on the actual connection before acceptance. Render documents
self-signed certificates internally and does not support verify-ca/verify-full
on that path; do not prescribe incompatible certificate verification.
Never downgrade silently to plaintext or print the URL.

1. Identify the empty isolated staging database and account, region, owner and
   environment; inventory any existing AI data. Preserve local data. An existing
   populated candidate requires an inventory and verified backup before migration.
2. A scoped administrative bootstrap enables `vector`. Use a separate migration
   owner, and a non-owner runtime CRUD role with CONNECT, schema USAGE and existing
   and default future table/sequence permissions. Deny superuser, CREATEROLE,
   CREATEDB, schema CREATE and membership that inherits elevated rights. Use
   independent credentials for production, staging and Company Portal.
3. From the reviewed backend image/source, set **only** the migration process's
   `ONESA_DATABASE_URL` through approved secret injection, using the migration role.
   Run `python -m alembic upgrade head`, then `python -m alembic current`. The
   required head is **20261010_capacity**. Alembic now reads that setting directly:
   it does not require a model endpoint merely to initialize an isolated database.
   Do not embed migration passwords in commands, logs or process arguments.
4. Verify extension version, `document_chunks.embedding` dimensions **256**, user
   ownership constraints and all identity/upload/capacity migrations. Run negative
   cross-owner and runtime-role/DDL checks against the staging database.
5. Application engines use **pool_size=5, max_overflow=0, pool_timeout=2s**,
   connection timeout 3s and statement timeout 5s, per process. Alembic uses
   **NullPool**. Budget connections as five per API/worker process plus migration,
   maintenance and operator reserve; start one API and one worker, monitor actual
   saturation before scaling. Schema-owner credentials must not enter the API.
6. Paid Render PostgreSQL has PITR, but a working restore is an acceptance test.
   Restore a synthetic backup/PITR point to a separately approved isolated target;
   check rows, roles/ownership, vector extension/dimensions, revocations, mail leases,
   upload expiry and cross-owner rejection. Suppress mail/model calls on the restored
   target. Document measured recovery time and data-loss window; owner approves
   RTO/RPO. Never overwrite production during this exercise.
   [Render recovery](https://render.com/docs/postgresql-backups).

Local checks against the owned disposable pgvector/PostgreSQL 16 database passed,
including migrations while full application configuration correctly rejects missing
production inference. This is not validation against a managed Render database.

## One concrete GPU proposal

**Scaleway, Paris `fr-par-1`, one `L4-1-24G`: NVIDIA L4 24 GB VRAM, 8 vCPU,
48 GB host RAM, 2.5 Gbit/s public networking.** The provider lists L4 availability
in Paris, but account quota, current stock, approved account and regional capacity
are unverified. This is an alternative to the Mac for hosted inference, not part
of Render's private network.
[GPU catalog and zones](https://www.scaleway.com/en/docs/gpu/),
[GPU types](https://www.scaleway.com/en/docs/gpu/reference-content/choosing-gpu-instance-type/),
[bandwidth](https://www.scaleway.com/en/docs/gpu/reference-content/gpu-instances-bandwidth-overview/).

Prepare the existing pinned vLLM image `v0.27.0` with digest
`sha256:07ea4e292adf3a26b05ac97114b28849cf4551a26beb1fbe7decd3842d752ed7` from
`compose.gpu.yaml`, re-scan it and review the Linux/NVIDIA driver/CUDA compatibility
before execution. Serve **Qwen/Qwen3-4B-Instruct-2507**, revision
`cdbee75f17c01a7cc42f958dc650907174af0554`, tensor parallel 1, BF16 subject to
hardware validation, maximum context **8192**, maximum simultaneous sequences **2**,
GPU utilization **0.80**. These proposed overrides are not measurements or a running
deployment. [Publisher serving guidance](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507).

The local Ollama tag `qwen3:4b-instruct-2507-q4_K_M` is a quantized Ollama artifact,
not the Hugging Face identifier above. Preserve it; validate template, tokenizer,
request protocol, stop behavior and quality against the new checkpoint before any
hosted-model decision is marked verified. Planning estimate: approximately **8 GB
16-bit weights**, another **4–10 GB KV cache/runtime/workspace**, roughly **12–18 GB
VRAM total** at the bounded workload. These are unmeasured sizing allowances; record
actual NVML peak/cold start/first-token latency/concurrency and adjust context or
admission limits before claiming capacity. Current application global concurrency
must be reduced/qualified for this single-host proposal, not assumed eight-way safe.

### Network and operational controls

A managed authenticated TLS gateway on the GPU VM listens on 443. Bind vLLM and
embeddings to loopback only; firewall their ports from the internet. Restrict SSH
and consider the actual Render outbound ranges as defense in depth. Use separately
scoped bearer credentials for generation and embeddings, exact request-body/time
limits and an allowlist for required operations (`GET /v1/models`,
`POST /v1/chat/completions`, `POST /v1/embeddings` to its separate upstream).
Deny all unspecified administrative, profiling, model-management, documentation,
health and metrics routes at public ingress. **vLLM's API-key flag alone does not
protect every endpoint.** [vLLM security](https://docs.vllm.ai/en/stable/usage/security/).

No approved private tunnel exists between Render and this provider. This proposal
uses authenticated public TLS, not an invented private network. Actual DNS, TLS
certificate and endpoint URL come only after approved provisioning. Keep both
hosted endpoints **BLOCKED** meanwhile. No localhost/developer-Mac production URL.

Startup: verify pinned image and weight hashes, mounted encrypted persistent cache,
NVIDIA runtime and local model/embedding health; publish gateway readiness only
following authenticated discovery and real synthetic requests. Keep access logs
free of authorization headers, prompts, documents and token-bearing URLs.
Cancellation: stream without proxy buffering; propagate disconnect, bound timeout,
verify stop under load and that no late assistant completion is stored. Recovery:
supervised restart, bounded retries and alerts; test gateway rejection during cold
start/outage. Restore pinned configuration/cache from a protected snapshot and
re-test from the actual Render staging environment. A single GPU host is not HA;
production capacity/recovery targets remain unqualified.

### Itemized cost and approval

Planning uses 730 hours/month, ex-VAT; current June 2026 rates are published by the
provider. A console quote, quotas and account terms must be reviewed before purchase.
[Effective pricing update](https://www.scaleway.com/en/blog/a-transparent-update-on-scaleway-pricing/).

| Item | Rate and allowance | Monthly estimate |
| --- | --- | --- |
| GPU VM, including idle running time | €0.792/hour × 730 | €578.16 |
| Persistent boot/model cache, total 100 GB | €0.00013/GB-hour × 100 × 730 | €9.49 |
| One zonal flexible IPv4 | €0.005/hour × 730 | €3.65 |
| One retained 100 GB snapshot allowance | €0.000049/GB-hour × 100 × 730 | €3.58 |
| Planned infrastructure subtotal | | **€594.88/month** |

GPU public network transfer is advertised without egress fees; Render outbound
traffic remains subject to its workspace allowance/overage and is **not priced
as zero** here. Monitoring/support, additional snapshots, tax and any approved
staging backend/worker are additional. [GPU networking](https://www.scaleway.com/en/gpu-instances/),
[Render bandwidth](https://render.com/articles/how-much-does-cloud-application-hosting-cost-for-small-businesses).

Recommend first approving **50 running GPU hours** for staging qualification:
€39.60 compute plus €16.72 retained storage/IP/snapshot for a full planning month,
**€56.32 ex-VAT**, plus Render database **$20.50/month** and unapproved extra service
costs. Running idle time is billed at the full rate. Provider stop must release
compute; retained disks/IP/snapshots continue billing. Do not assume shutting down
a container or guest stops billing. Retain or release artifacts only under explicit
retention/deletion instructions. [Instance billing states](https://www.scaleway.com/en/docs/instances/reference-content/instance-states/).

Exact remaining approval: owner approves the Render staging database account,
Frankfurt region, plan and monthly budget; identifies the isolated staging backend
and its compute budget; separately approves Scaleway account/terms/DPA, Paris L4
quota, 50-hour trial cap, 100 GB volume, IPv4 and snapshot costs, pinned model download,
operator access, TLS endpoint and secret lifecycle. Production database/continuous
GPU operation and identity worker are separate approvals after staging results.
No such purchase or provider-terms acceptance occurred during preparation.

## Embeddings and private document persistence

Semantic retrieval uses a **separate embedding service**, not vLLM chat. Preserve
`Qwen/Qwen3-Embedding-0.6B`, pinned revision
`97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3`, publisher weight SHA-256
`0437e45c94563b09e13cb7a64478fc406947a93cb34a7e05870fc8dcd48e23fd`.
The implemented service uses float32, last-token pooling, normalized Matryoshka
vectors **256**, bounded tokens and a versioned query instruction. Proposed placement
is a separate **CPU** process/venv on the same GPU VM, loopback 8364 behind its own
TLS/auth gateway upstream. Estimate approximately **2.4 GB float32 weights and
4–8 GB process RAM**, unmeasured; qualify Linux CPU latency/memory and generate/audit
a Linux lock first. The existing lock is macOS-specific. Chat readiness does not
establish embedding readiness. Do not switch existing vectors without backed-up,
per-owner reindex acceptance. See [embedding instructions](../../onesa-ai-platform-backend/embedding_service/README.md).

The implemented bounded upload store keeps private SQL
chunks temporarily; provider encryption at rest must be verified; document extraction then persists owner-scoped text, metadata
and 256-dimensional vectors in PostgreSQL. Original PDF binaries are **not archived**
in an AI S3 bucket: transient extraction files are removed. A healthy private database
therefore makes implemented knowledge text/vector storage durable, but does not
provide original-upload archive retention. If originals are required, private object
storage, scoped credentials, scan/retention/deletion and restoration acceptance are
still missing; no S3 provider integration is invented. Do not reuse Portal's bucket
or credentials. Production embedding service, managed database and qualified backups
remain missing dependencies.

## Deployment order and honest readiness

See [actual configuration keys](HOSTED_AI_CONFIGURATION.md). Enter credentials directly
in the appropriate Render service/worker secret settings, separately by environment.
Save without deploying until the reviewed immutable commit, image scan and qualification
record are ready; confirm auto-deploy is off. Adding variables must not redeploy the
older cloud revision. Migrate only the identified staging database with scoped role.
Deploy the reviewed staging backend, verify `/health` (process), `/core-ready` (real
current database) and `/ready` (database plus model) separately. With healthy database,
model outage may leave non-AI core routes usable; generation must fail honestly.
No fake responses or unconditional health success are allowed.

The older Render AI revision returned a green readiness response despite missing
configuration. The new code rejects implicit Render development defaults and requires
an actual database for core readiness; **it has not been qualified on the hosted path**.
Vercel's server-side `ONESA_API_URL` is absent. Test real browser → Vercel BFF → Render
→ database/model/embeddings before claiming the hosted 503 resolved. Preserve the
mandatory exact-commit staging/operations/legal release gates and separately prove
revocation/replacement of previously exposed credentials; no compromised value is reused.
