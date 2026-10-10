# AI configuration inventory and provisioning delta — 2026-10-10

**Production NO-GO. Free-only purchasing policy remains in effect.**
This is an AI-only configuration review, not a new architecture or release approval.
Portal, Robot, private environment files, local Ollama and user data are unchanged.

## A. Complete redacted configuration matrix

Authenticated read-only workflow [38065741091](https://github.com/DruHustle/onesa-ai-platform/actions/runs/38065741091),
source `86ea737e64ec3edee20a819916c41cf845a66867`, finished successfully at
15:58 UTC. Render's environment endpoint contains only
`NEXT_PUBLIC_ONESA_DOCUMENTATION_URL`, which the Python backend does not consume.
No linked environment groups, group conflicts or matching AI background workers
were found. Every backend Settings override below is **missing**; optional fields
still have code defaults. Missing overrides do not mean every field is mandatory.
Configured/present syntax alone would not prove database/model functionality.

Backend source **B** = `onesa-ai-platform-backend/app/config.py:Settings`.
All B rows load in the API and also in `app/identity_worker.py` via the same Settings
class. Workers therefore inherit production validation even when not calling the model.
Runtime DB = `app/database.py`; migration DB = `migrations/env.py` (reads only
`ONESA_DATABASE_URL`, does not require full application/model settings).
Secrets below are never included as values in this document.

| Key | Consumer / purpose | Required and accepted value | Classification / scope | Status and exact value source |
| --- | --- | --- | --- | --- |
| `ONESA_ENVIRONMENT` | B, API/worker deployment mode | Required on Render; `development`, `test`, `staging`, `production`; only last two on Render | Nonsecret; separate staging/production | Missing. Production target `production`; staging target `staging` after owner identifies isolated service. `NODE_ENV` does not control Python. |
| `ONESA_PUBLIC_ORIGIN` | B, auth Origin/CSRF and mail links | Required exact HTTPS origin, no path/trailing slash/query/credentials in hosted modes | Nonsecret; separate origins | Missing. Owner-confirmed production `https://platform.onesa.eu`. Staging actual Vercel assignment not yet identified; do not reuse production origin/data or wildcard previews. |
| `ONESA_SECURE_COOKIES` | B, session cookie | Required `true` in hosted modes (`true`/`false` accepted) | Nonsecret; both hosted environments | Missing; known target `true`. |
| `ONESA_DATABASE_URL` | B/database.py, worker; migrations/env.py | Required hosted; explicit installed SQLAlchemy psycopg3 scheme `postgresql+psycopg://` | Secret; isolated per product/environment/role | BLOCKED: owner-created Neon staging database reported; ownership/schema/plan and fresh restricted-role credentials pending. Actual Neon pooled runtime URL; deliberate psycopg3 driver adaptation, preserving escaped credentials/query. Production database remains separate and unprovisioned. Migration owner injected separately under same key, never API owner role. |
| `ONESA_METRICS_TOKEN` | B, protected metrics | Required hosted, >=32 random characters | Secret; per environment | Missing. Generate privately through approved secret mechanism; never copy portal/proxy/previous exposed values. |
| `ONESA_MODEL_BACKEND` | B/model factory | `mock`, `ollama`, `vllm`; production rejects mock | Nonsecret; model decision per environment | Missing. Local verified `ollama` unchanged. Hosted vLLM proposal is not approval to replace it. |
| `ONESA_MODEL_NAME` | B/model client | Nonempty served model identifier | Nonsecret; model host | BLOCKED hosted. Local `qwen3:4b-instruct-2507-q4_K_M`; proposed HF `Qwen/Qwen3-4B-Instruct-2507` is a different artifact and requires compatibility acceptance. |
| `ONESA_MODEL_BASE_URL` | B/model client | OpenAI-compatible base including `/v1`; production authenticated HTTPS, no development addresses/URL credentials | Nonsecret endpoint; API/worker configuration only | BLOCKED. Actual authenticated generation gateway after host provisioning; never a guessed hostname or Mac listener. |
| `ONESA_MODEL_API_KEY` | B/model client | Nonempty production authentication | Secret; API and validated worker settings | BLOCKED. Independently scoped credential generated at approved gateway. |
| `ONESA_EMBEDDING_BACKEND` | B/knowledge.py | `lexical` or `http`; explicit `http` for real semantic candidate | Nonsecret; both environments | Missing. Preserve local semantic candidate in provider templates; lexical remains labelled fallback option only by an explicit decision. |
| `ONESA_EMBEDDING_NAME` | B/knowledge.py | Served embedding identifier; response must be 256-dimensional | Nonsecret; embedding host | Missing; candidate `Qwen/Qwen3-Embedding-0.6B`. This runs through a separate HTTP embedding service, not automatically inside FastAPI/chat vLLM. |
| `ONESA_EMBEDDING_REVISION` | B/knowledge.py | Version string used in stored index identity | Nonsecret; per index | Missing; locally qualified candidate `97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3:qwen-retrieval-v1`. Reindex existing data deliberately; never discard lexical indexes silently. |
| `ONESA_EMBEDDING_QUERY_INSTRUCTION` | B/knowledge.py | String <=800 chars; preserve candidate instruction | Nonsecret; both environments | Missing; `Given a user question, retrieve relevant document passages that answer the question`. |
| `ONESA_EMBEDDING_BASE_URL` | B/knowledge.py | Base `/v1`; production authenticated nonlocal HTTPS | Nonsecret endpoint; backend only | BLOCKED; actual embedding gateway, independently discovered/tested. `/embeddings` appended by code. |
| `ONESA_EMBEDDING_API_KEY` | B/knowledge.py | Required for production HTTP candidate | Secret; backend only | BLOCKED; separate embedding gateway credential, not assumed generation key. |
| `ONESA_MAIL_PROVIDER` | B/identity_worker.py | `disabled` or `resend` | Nonsecret; API + worker | Missing override; code default `disabled`. Keep disabled until AI-scoped mail settings, worker and approved recipient tested. |
| `ONESA_AUTH_DELIVERY_KEY` | B/auth.py/identity_worker.py | >=48 chars when mail enabled; persistent HMAC key for invitation/recovery hashes | Secret; API + worker, same per environment | Missing; independently generate and inject privately. This is not a session signing key. |
| `ONESA_RESEND_API_KEY` | B/identity_worker.py | Required when mail enabled | Secret; worker + validated API configuration | Missing; newly generated AI-scoped sending credential, do not reuse exposed chat value. |
| `ONESA_MAIL_FROM` | B/identity_worker.py | Required nonempty sender when mail enabled | Nonsecret; both hosted | Missing; proposed `Onesa AI <noreply@mail.onesa.eu>`, separately verify authorized sender. Portal domain verification is not AI delivery acceptance. |
| `ONESA_MAIL_REPLY_TO` | B/identity_worker.py | Optional sender reply address | Nonsecret; both hosted | Missing; owner mailbox direction `hello@onesa.eu`, delivery unverified. |
| `ONESA_API_URL` | frontend `src/lib/backend.ts`, server-only BFF | Required hosted exact backend origin, no `/api` or `/v1` suffix | Nonsecret; Vercel production/isolated preview | Missing. **Actual production candidate `https://onesa-ai-platform-backend.onrender.com`**, read from Render serviceDetails.url. Prepared, not remotely saved. Preview must point to its isolated staging backend. |
| `ONESA_PROXY_TIMEOUT_SECONDS` | frontend backend.ts | Optional finite 1..600 seconds, default135 | Nonsecret; Vercel | Missing override; proposed135, greater than backend generation timeout60. |
| `NEXT_PUBLIC_ONESA_DOCUMENTATION_URL` | frontend `src/lib/documentation.ts` | Public docs URL | Nonsecret; Vercel build/runtime | Missing in Vercel; known `https://docs.onesa.eu`. Misplaced copy on Render preserved (not deleted). DNS availability remains separate. |
| `NEXT_PUBLIC_ONESA_ENGINEERING_DOCUMENTATION_URL` | frontend documentation.ts | Optional private gateway URL; default loopback3201 is local only | Nonsecret URL; Vercel, never content/credentials | Missing; BLOCKED until actual authenticated internal-docs gateway assigned. Do not expose private docs through public docs. |
| `NEXT_PUBLIC_MAX_UPLOAD_BYTES` | frontend knowledge page | Optional numeric limit; proposed5242880 matches fixed backend5MiB and bounded uploads | Nonsecret; Vercel | Missing override; default5242880 already matches. |
| `ONESA_HSTS_ENABLED` | frontend `src/proxy.ts` | Optional exact `true` enables header, defaultfalse | Nonsecret; Vercel | Missing override; leavefalse until intended TLS deployment/rollback reviewed. |
| `NODE_ENV` | Next.js framework/build tooling | Framework-managed production during hosted build | Nonsecret; frontend only | Provider-managed, not a Python control or replacement for ONESA_ENVIRONMENT. |
| `SESSION_KEY`, `DATABASE_URL`, `S3_BUCKET`, AWS/S3 credentials | Not read by this AI Settings class | Not AI configuration keys | Do not inject portal secrets | Not applicable. AI uses random opaque sessions hashed in PostgreSQL and CSRF tokens; no session signing secret is required. |

### All other backend Settings (exact accepted types/defaults)

Every row is B/API + inherited worker Settings, staging/production scope, optional
except enabled-feature permissions. Classification is nonsecret configuration;
user IDs are private access-control identifiers. Current provider status is
**missing override, code default active**. Values come from the checked-in Settings
class; capacity/security defaults still require hosted acceptance. Override the
concurrency fields to1 for bounded free staging as in `staging.env.example`.

| Exact key | Accepted type / limits | Code default | Purpose / exact source |
| --- | --- | --- | --- |
| `ONESA_MODEL_MAX_OUTPUT_TOKENS` | `int`; ge=1; le=8192 | `1024` | model max output tokens; B field default/constraints |
| `ONESA_MODEL_CONTEXT_LENGTH` | `int`; ge=512; le=131072 | `8192` | model context length; B field default/constraints |
| `ONESA_MODEL_QUANTIZATION` | `str | None`; max_length=64; pattern='^[A-Za-z0-9_ .-]+$' | `None` | Optional model provenance |
| `ONESA_MODEL_REVISION` | `str | None`; max_length=128; pattern='^[A-Za-z0-9_.-]+$' | `None` | Optional public model provenance; not an Ollama/HF equivalence proof |
| `ONESA_MODEL_MODALITIES` | `list[Literal['text', 'vision', 'speech']]`; no additional field constraint | `['text']` | Advertised input modes, not proof of capability |
| `ONESA_MODEL_TEMPERATURE` | `float`; ge=0; le=2 | `0.7` | model temperature; B field default/constraints |
| `ONESA_SESSION_HOURS` | `int`; ge=1; le=168 | `24` | session hours; B field default/constraints |
| `ONESA_AUTH_RATE_LIMIT` | `int`; ge=1; le=1000 | `10` | auth rate limit; B field default/constraints |
| `ONESA_AUTH_HASH_CONCURRENCY` | `int`; ge=1; le=16 | `4` | auth hash concurrency; B field default/constraints |
| `ONESA_KNOWLEDGE_UPLOAD_CONCURRENCY` | `int`; ge=1; le=4 | `1` | knowledge upload concurrency; B field default/constraints |
| `ONESA_AUTH_PEER_RATE_LIMIT` | `int`; ge=1; le=10000 | `100` | auth peer rate limit; B field default/constraints |
| `ONESA_REGISTRATION_MODE` | `Literal['open', 'invitation']`; no additional field constraint | `'open'` | registration mode; B field default/constraints |
| `ONESA_ACCESS_OPERATOR_USER_IDS` | `list[str]`; no additional field constraint | `[]` | Operator allowlist; approved real AI user IDs only |
| `ONESA_INVITATION_HOURS` | `int`; ge=1; le=168 | `48` | invitation hours; B field default/constraints |
| `ONESA_RECOVERY_MINUTES` | `int`; ge=5; le=10 | `10` | recovery minutes; B field default/constraints |
| `ONESA_MODEL_USER_CONCURRENCY` | `int`; ge=1; le=32 | `2` | model user concurrency; B field default/constraints |
| `ONESA_MODEL_GLOBAL_CONCURRENCY` | `int`; ge=1; le=128 | `8` | model global concurrency; B field default/constraints |
| `ONESA_MODEL_USER_REQUESTS_PER_MINUTE` | `int`; ge=1; le=1000 | `20` | model user requests per minute; B field default/constraints |
| `ONESA_MODEL_GLOBAL_REQUESTS_PER_MINUTE` | `int`; ge=1; le=10000 | `120` | model global requests per minute; B field default/constraints |
| `ONESA_MODEL_USER_RESERVED_TOKENS_PER_MINUTE` | `int`; ge=1024 | `256000` | model user reserved tokens per minute; B field default/constraints |
| `ONESA_MODEL_GLOBAL_RESERVED_TOKENS_PER_MINUTE` | `int`; ge=1024 | `1024000` | model global reserved tokens per minute; B field default/constraints |
| `ONESA_KNOWLEDGE_MAX_DOCUMENTS` | `int`; ge=1; le=10000 | `100` | knowledge max documents; B field default/constraints |
| `ONESA_KNOWLEDGE_USER_TEXT_BYTES` | `int`; ge=256000 | `16 * 1024 * 1024` | knowledge user text bytes; B field default/constraints |
| `ONESA_KNOWLEDGE_GLOBAL_TEXT_BYTES` | `int`; ge=256000 | `256 * 1024 * 1024` | knowledge global text bytes; B field default/constraints |
| `ONESA_GENERATION_TIMEOUT` | `float`; ge=1; le=120 | `60` | generation timeout; B field default/constraints |
| `ONESA_DOCUMENTATION_SOURCES_DIRECTORY` | `str`; no additional field constraint | `'/app/docs-sources'` | Private indexed source mount; required to enable scoped internal retrieval |
| `ONESA_DOCUMENTATION_ENGINEERING_USER_IDS` | `list[str]`; no additional field constraint | `[]` | Private docs retrieval allowlist; approved real AI user IDs only |

## B. Known nonsecret values and prepared provider delta

Production Render backend:

```dotenv
ONESA_ENVIRONMENT=production
ONESA_PUBLIC_ORIGIN=https://platform.onesa.eu
ONESA_SECURE_COOKIES=true
ONESA_REGISTRATION_MODE=invitation
ONESA_AUTH_HASH_CONCURRENCY=1
ONESA_KNOWLEDGE_UPLOAD_CONCURRENCY=1
ONESA_MODEL_USER_CONCURRENCY=1
ONESA_MODEL_GLOBAL_CONCURRENCY=1
```

Vercel project `onesa-ai-platform`, **Production** target:

```dotenv
ONESA_API_URL=https://onesa-ai-platform-backend.onrender.com
ONESA_PROXY_TIMEOUT_SECONDS=135
NEXT_PUBLIC_ONESA_DOCUMENTATION_URL=https://docs.onesa.eu
NEXT_PUBLIC_MAX_UPLOAD_BYTES=5242880
```

These are a **prepared delta**, not a complete valid production environment.
Database, metrics, generation and embedding credentials/endpoints remain private
and unprovisioned. Do not deploy the blank example. `production.env.example` now
uses the verified API origin and preserves the semantic candidate instead of
silently selecting lexical search. Private `.env`/`.env.local`/`.env.prod` files
are not overwritten. The `infra/deployment/production.env.example` is a different
self-hosted Compose template; its service names are not hosted Render endpoints.

Staging has no confirmed Vercel project/origin or API resource in this inspection.
Keep `staging.env.example` separate and its required values blank/placeholders
until the owner identifies the staging deployment. Never apply the production
ONESA_API_URL to Preview as a convenience. Use one exact authorized staging origin,
not a wildcard `.vercel.app` trust rule.

## C. Actual existing resources

| Resource | Verified configuration | Running state |
| --- | --- | --- |
| Render `onesa-ai-platform-backend` | Owner `tea-d5h2r0p4tr6s739ae000`; environment ID `evm-db4ir3psrm7s73fsmlsg` (environment name/classification not independently read); Frankfurt, Free Docker web service; DruHustle/onesa-ai-platform, main, root onesa-ai-platform-backend; Docker context `.`, Dockerfile `Dockerfile`, command repaired previously to `sh /app/start.sh`, health `/core-ready`, native auto-deploy off | Latest deployment `update_failed`, revision `4db9c2b18064c5a21c85ef87a6d48d7098d41b85`; source repair revision872e2bc is not the running revision. `/core-ready` timed out in read-only provider check (HTTP0 denotes no response, not an HTTP status). |
| Vercel `onesa-ai-platform` | Same GitHub repo linked, Next.js, root onesa-ai-platform-frontend/apps/chat; production READY; platform.onesa.eu and onesa-ai-platform.vercel.app domains verified | Production revision `6e98c6d4cb0738fe4bd51caa124205914657280e`; frontend200 with verifiedTLS; frontend API503. No Vercel project env keys returned. |
| Same-owner Render PostgreSQL inventory | HTTP200, zero resources, not truncated | No database credentials/schema retrieved; no AI database exists in this inspected Render workspace. This does not claim an inventory of inaccessible Neon/other accounts. |
| Render groups and AI workers | HTTP200 lists, not truncated; no groups linked to this API; no matching AI background workers | No portal group leakage/conflicts found. No hosted identity worker found; mail remains disabled. |
| Hosted model / embedding host | No approved endpoint in deployed settings or approved resource inventory | No authorized external GPU account inventory available; no live approved host established. Local Ollama remains unchanged. |

Resource/project IDs stored as GitHub secrets are masked automatically in workflow
logs. Resolve them via the existing `RENDER_BACKEND_SERVICE_ID` and
`VERCEL_PROJECT_ID` secret references; do not expose credentials to obtain an ID.

## D. Concrete provisioning requests and approval boundaries

### Database: owner-created Neon staging resource

The owner reports creating **`onesa-ai-platform-backend-db-staging`** on Neon. The supplied
URL identifies AWS `eu-central-1` (Frankfurt), pooled host `ep-falling-thunder-b9x4ka3b-pooler.c-7.eu-central-1.aws.neon.tech`,
and SQL database **`neondb`**. The resource label is not the SQL database name.
This is an owner-reported resource, not an authenticated ownership/plan/schema check.
No new Render database should be provisioned for this staging setup. The former
Render Free request is superseded; same-owner Render inventory can remain empty
while the application uses this separate external Neon database. This external
connection is not a Render Internal Database URL.

The owner credential was disclosed in chat. It has not been stored, reused for a
connection test, copied into another product or submitted to Render. Rotate its
password in Neon → this project's staging branch → Postgres database → Roles.
Enter replacement credentials only in an approved private mechanism, not chat.
[Neon role/password management](https://neon.com/docs/manage/roles).

1. Verify the actual Neon project/branch belongs to Onesa AI staging only, its
   Free plan, PostgreSQL version (16 requested), contents and intended use. Preserve
   any pre-existing data; inventory and back up before modifying it.
2. Use a separate migration owner and a restricted API/worker runtime role.
   `neondb_owner` is not the runtime-role choice. Roles created in the Neon Console
   may inherit elevated membership; create restricted roles through reviewed SQL
   and verify no superuser, CREATEROLE/CREATEDB/BYPASSRLS, schema CREATE or elevated
   inherited membership. Bootstrap `vector` using the approved owner.
3. Privately save the actual restricted-role pooled URL as **ONESA_DATABASE_URL**
   in the **AI staging Render API** and appropriate staging worker. SQLAlchemy uses
   psycopg3; deliberately select scheme **postgresql+psycopg://**, retaining actual
   host/database, correctly encoded credentials and
   **sslmode=require&channel_binding=require**. Do not rename `neondb`, inject the
   owner role into runtime, reuse Portal credentials or modify production settings.
4. For migrations, obtain the actual direct connection from Neon Connect by
   disabling pooling; do not guess a direct hostname. Inject its fresh migration
   credential into **only the migration process's ONESA_DATABASE_URL**, preserving
   TLS and selecting the installed driver. [Neon connection guidance](https://neon.com/docs/get-started/connect-neon).
5. Once ownership/isolation and fresh secrets are verified, run from reviewed backend:

```sh
python -m alembic upgrade head
python -m alembic current
```

Required head `20261010_capacity`. Validate vector256dimensions, identity/upload
constraints, role isolation and TLS on the actual hosted connection. Runtime pool5,
overflow0, pooltimeout2s, connecttimeout3s, statementtimeout5s; migrations NullPool.
Verify pooled connection startup/session options against Neon before acceptance.
Perform a synthetic backup/isolated restoration test with mail/model suppressed.
No hosted connection, live migration, backup or ownership verification occurred.

Local ignored mode0600 `.env.staging` is prepared with ONESA_ENVIRONMENT=staging,
secure cookies and a newly generated private metrics token. ONESA_DATABASE_URL
remains blank until the exposed owner credential is rotated and a restricted runtime
URL is injected. Production origin/data and existing local `.env` remain unchanged.
The staging frontend origin is still unidentified; template placeholders are not
validated deployment values.

### Model: one concrete vLLM proposal, BLOCKED by free-only budget

Scaleway Paris `fr-par-1`, one `L4-1-24G`, NVIDIA L4 **24GB VRAM**, 8vCPU,48GBRAM.
Approved provider account/terms, quota, stock and purchase approval have not been
established. External GPU is not part of Render's private network. Proposed
runtime and checkpoint exactly match the preserved repository GPU definition:

- Image `vllm/vllm-openai:v0.27.0@sha256:07ea4e292adf3a26b05ac97114b28849cf4551a26beb1fbe7decd3842d752ed7`.
- Checkpoint `Qwen/Qwen3-4B-Instruct-2507`, revision `cdbee75f17c01a7cc42f958dc650907174af0554`.
- BF16, TP1, context8192, maximum sequences2, GPU utilization0.80; API global
  concurrency1 initially. Check driver/CUDA/image scan before execution.
- Estimated weights8GB + KV/runtime4–10GB =12–18GB VRAM. **Not measured**;
  this does not reserve room for a second GPU embedding model.
- 100GB encrypted boot/model cache plus one100GB snapshot allowance. Retained
  storage and IP cost money while stopped. Model licensing, image scan and local
  Ollama-vs-HF tokenizer/template/output compatibility acceptance required.

The provider's effective-June2026 price update gives the following ex-VAT planning
rates. Its rounded catalog monthly figure differs; require actual console quote
before any purchase. [Official effective price table](https://www.scaleway.com/en/blog/a-transparent-update-on-scaleway-pricing/),
[GPU specifications](https://www.scaleway.com/en/l4-gpu-instance/).

| Item | Assumption | Estimate |
| --- | --- | --- |
| GPU, including running idle time | €0.792/h ×730h | €578.16/month |
| 100GB block volume | €0.00013/GB-hour ×730h | €9.49/month |
| One IPv4 | €0.005/h ×730h | €3.65/month |
| One100GB snapshot | €0.000049/GB-hour ×730h | €3.58/month |
| Infrastructure subtotal | No dedicated paid load balancer; gateway on VM | €594.88/month |
| Limited qualification alternative | 50GPU hours plus retained items for730h | €56.32 ex-VAT |

Provider GPU bandwidth is advertised as included; Render egress/allowance, taxes,
extra snapshots/monitoring/support are additional and unquoted, not assertedzero.
**This paid option is not eligible under the owner's current free-only decision.**
No verified always-available free EU GPU/vLLM host serving this exact checkpoint
has been established. Free API alternatives in FREE_STAGING_SETUP.md require a
separate model/provider/data-location decision; no silent replacement is made.

#### Prepared startup and acceptance procedure (not executed)

A standalone GPU Compose proposal is in
[`compose.hosted-vllm.yaml`](../../infra/deployment/proposals/compose.hosted-vllm.yaml).
On an approved NVIDIA host, privately inject ONESA_MODEL_API_KEY through an ignored,
mode0600 host environment file; never print expanded Compose configuration.

```sh
docker compose --env-file /secure/onesa-gpu.env -f infra/deployment/proposals/compose.hosted-vllm.yaml up -d inference
curl --fail http://127.0.0.1:18000/health
```

The loopback health command runs on the GPU host only. Public port18000 must be
firewalled. Configure an authenticated TLS gateway on443 with generation and
embedding credentials scoped separately. Permit only authenticated
GET /v1/models and POST /v1/chat/completions for generation; embeddings uses its
separate upstream POST /v1/embeddings. Reject every other route including admin,
profiling, docs, metrics, management and public health. Keep vLLM bound behind
loopback publishing; do not rely on its API-key flag to protect all operations.
[Official vLLM security](https://docs.vllm.ai/en/stable/usage/security/).

After real DNS/TLS assignment, from the authorized Render staging environment use
its privately injected ONESA_MODEL_BASE_URL and key to test models discovery,
a real bounded completion, SSE text/done frames, disconnect cancellation with no
late stored response, outage503 and restarted recovery. No key in curl flags/logs.
Repeat through authenticated frontend chat paths with synthetic data. Record actual
GPU peak memory, first-token latency and concurrency. Startup health is not model
quality/capacity or frontend acceptance. Stop/restart the proposed GPU service only;
do not run the native Ollama failure script on the developer Mac for this test.

### Embeddings, storage and worker dependencies

Knowledge HTTP adapter calls a **separate** embedding endpoint. Preserve
Qwen3-Embedding-0.6B revision and256dimensions/query instruction above; verify actual
model/version/norm/dimensions, EN/DE retrieval and cross-owner isolation against
PostgreSQL. The backend does not load these weights automatically. A bounded CPU
embedding process on the proposed48GB host is a possible placement only after Linux
memory/latency acceptance; 512MB Render Free API is not assumed sufficient for0.6B
weights (about1.2GB16-bit weights before runtime). No second model was downloaded.

Actual upload path `app/knowledge.py` reads bounded TXT/PDF, extracts text, discards
raw source bytes, and persists owned text/chunks/vectors in PostgreSQL. `app/uploads.py`
stores bounded chunk staging in the database. Thus private PostgreSQL persistence,
backup/permissions/retention are the required implemented document storage; **there
is no AI S3 consumer** to configure with Portal's bucket credentials. Original-file
archival is not implemented or claimed. Private engineering retrieval additionally
requires an access-controlled `ONESA_DOCUMENTATION_SOURCES_DIRECTORY` mount and
approved user IDs; no such hosted mount/source ingestion was verified.

Identity delivery and expired bounded-upload cleanup run in
`python -m app.identity_worker`. No matching hosted worker exists. Render Free does
not offer background workers; use an explicitly approved existing free CPU process
or local isolated qualification worker. Do not invent a free Render worker/paid
service or claim invitations/account recovery mail works with mail disabled.

## E. Prepared versus applied

Applied: AI diagnostic code, disclosure tests, provider inspection workflow and
reviewable source templates/proposals/documentation. Diagnostic source was pushed
to main and its read-only provider workflow succeeded. No provider environment
values, service resources, plan, DNS, credentials, migrations or deployed application
were changed. The later owner-reported Neon resource is recorded below; its exposed
credential was not saved or used.

Prepared: exact production origin/proxy delta, complete redacted matrix, temporary
free Render PostgreSQL request and bounded paid GPU alternative (unapproved),
semantic endpoint requirements, worker/storage and hosted acceptance steps.

Before any future remote save, verify project/service/environment classification
and existing settings again; preserve existing secrets privately. Render Dashboard
Environment offers **Save only**, **Save, rebuild, and deploy**, and **Save and deploy**:
choose Save only during preparation, then reviewed exact-SHA workflow after gates.
Do not accidentally launch old failed4db9c2b or READY6e98c6d builds. Vercel project env
changes should apply only to the intended target and next approved build; do not
use a dashboard Redeploy of the old release to activate them. Check current provider
semantics immediately before mutation. [Render save modes](https://render.com/docs/configure-environment-variables).

Rollback: retain previous reviewed code/config privately, preserve database backups
and backward-compatible schema; rollback via reviewed workflow only. Never restore
exposed credentials or unsafe failed revisions. Keep native auto-deployment disabled
and release qualification guard intact. Secret rotation remains a separate verified
owner task; this inspection did not rotate/reuse exposed values.

## F. Checks passed and blocked

- PASS: correct AI repo/root/branch identities, actual backend URL, domains verified,
  no linked Portal groups/conflicting overrides found, read-only inventory200.
- PASS: platform.onesa.eu homepage GET200, certificate verification enabled, HTML,
  no observed auth redirect; intended production origin really is assigned in Vercel.
- PASS:8 existing hosting tests +3 new disclosure/boundary tests; Ruff on new scripts.
- PASS: local isolated real PostgreSQL suite **147 passed,4 skipped**, including
  schema upgrade/downgrade, runtime roles, identity/CSRF/isolation, uploads and
  core-vs-model readiness. One upstream TestClient deprecation warning. Initial
  sandbox-denied connection run was superseded by authorized local-network run.
- BLOCKED: hosted `/api/v1/health` and `/api/v1/ready` both503; direct `/core-ready`
  request timed out. The original hosted503 finding remains OPEN.
- BLOCKED: deployed revision is older than repaired source, runtime DB settings/env absent (Neon staging resource is owner-reported),
  mandatory model host unprovisioned, embeddings/worker delivery unconfigured.
- BLOCKED: hosted DB connectivity/schema/role/TLS, sessions/CSRF/proxy, real
  generation/stream/cancel/recovery, semantic retrieval and backups/restore cannot
  be accepted until isolated infrastructure is configured and reviewed code deployed.
- BLOCKED: production release qualification, operations and content/legal approval
  remain incomplete. `/health` is process liveness, `/core-ready` DB/core readiness,
  `/ready` DB+model readiness; none substitutes for public-release approval.

## G. Single next owner action and consolidated sequence

**Next owner action: rotate the exposed Neon owner password in the staging project
and privately configure separate migration and restricted runtime credentials for
`onesa-ai-platform-backend-db-staging`.** Do not create a duplicate database or paste
replacement credentials here. Hosted ownership/schema/TLS verification and migrations
can proceed once fresh credentials and the isolated target are available.

Then identify the isolated staging API/Vercel project + exact origin, inject that
DB's restricted runtime credentials and metrics token, and qualify the reviewed
source. Before enabling email, provision the free-approved worker placement and
AI-scoped delivery secrets. Hosted vLLM remains blocked by the free-only requirement;
choose a specifically approved free host/provider/model direction or a changed
budget policy before GPU provisioning. No request for an already-existing endpoint
is being made. Finally complete hosted tests and genuine release approvals before
production promotion. Production and staging must have separate data and credentials.

Diagnostic commit86ea737 full Platform checks [38065740456](https://github.com/DruHustle/onesa-ai-platform/actions/runs/38065740456) and repository hygiene38065740464 both passed. The new disclosure tests and standalone GPU Compose syntax validation are now included in subsequent CI.

## Isolated staging inspection — 2026-10-10

The owner confirmed rotation of the previously exposed Neon password and saving
the fresh value on Render staging. Read-only workflow `38075678487` connected to
that configured database successfully. No credential values were logged.

- Render: `srv-db56mju7bikc73950f60`, environment `evm-db56llvlot8c73dtjvhg`,
  actual origin `https://onesa-ai-platform-backend-staging.onrender.com`.
  Currently branch `main`, application root incorrect, only `ONESA_DATABASE_URL`
  present. This is an inspected configuration, not a successful staging deployment.
- Neon: actual SQL database `neondb`, PostgreSQL **18.6**, vector installed,
  zero public tables, Alembic schema not initialized. Preserve this existing
  database; the earlier PostgreSQL 16 suggestion is superseded by inspection.
- The current owner-role credential is unsuitable for application runtime.
  Controlled migration and restricted-role provisioning remain required.
- Vercel: existing `onesa-ai-platform` project, correct Next.js root, production
  branch `main`, Preview protection `all_except_custom_domains`. No staging
  branch variables existed at inspection. No production settings were changed.
- Probe's `pg_stat_ssl` concerns the pooler-to-server leg; it is not proof of
  client transport failure. The updated probe separately checks psycopg client TLS.

The staging-only repair workflow now supports protected Preview deployment,
gated by full CI and publication hygiene on the exact current staging SHA.
It configures only branch `staging` / target `preview` / `ONESA_API_URL` and
refuses conflicting existing values. It never requests a production deployment.

Owner prerequisite: save the fresh actual Neon **direct (pooling disabled)**
connection as GitHub repository secret `STAGING_MIGRATION_DATABASE_URL`.
This operator secret is supplied to migration processes as `ONESA_DATABASE_URL`;
it is not a new application configuration key. Do not paste credentials in chat.
Use a separately restricted credential for the Render runtime after migrations.
Until schema, runtime role and exact Preview origin are verified, do not deploy
the staging backend or count hosted database workflows as accepted.

The owner has now saved `STAGING_MIGRATION_DATABASE_URL` and
`VERCEL_AUTOMATION_BYPASS_SECRET` in GitHub environment **Staging**. Names were
verified without retrieving values. Environment deployment policy was restricted
to branch `staging` (actual provider readback); production was not changed.
The staging repair workflow binds that existing environment. Migration credentials
are injected only into initialization/acceptance steps, never the frontend build.

Controlled `deploy-staging` initializes only the identified empty Neon database,
within one transaction, and creates `onesa_ai_staging_app` without elevated roles,
schema creation or migration-table mutation. Existing unidentified data/roles cause
a refusal. Runtime credentials are generated privately and saved only on the
fixed Render staging service. Runtime TLS, actual application driver/pooling options,
permissions and migration revision are verified before requesting deployment.

Vercel Preview packaging on the first attempt failed with a traced Next runtime
module resolution error; native compilation had passed. Vercel builds now use
the framework's normal function tracing; standalone output/tracing remains enabled
for Docker. The repaired revision still needs exact-commit CI and hosted acceptance.

Rollback: keep automatic Render deploys off; retain the previous exact staging SHA
and deploy it only if compatible with the current schema. Keep the generated role,
private runtime URL and persistent database. Do not downgrade or drop the schema,
reuse production credentials, promote the Preview, or change `platform.onesa.eu`.
Hosted acceptance uses synthetic accounts with two-hour grants; credentials exist
only in a mode0600 ephemeral runner file removed after browser tests. Reports contain
check labels and public deployment origins, not passwords, cookies or bypass tokens.
Model-dependent workflows remain BLOCKED until real authenticated endpoints exist.
