# Hosted AI configuration inventory — 2026-10-10

## Save-only production startup verification — 2026-10-12

Use `gh workflow run repair-hosting.yml --ref dev -f production_startup=true` after current dev CI and hygiene pass. This separate job uses the repository's production provider binding and no Staging environment. Only the fixed existing Free Frankfurt AI API target is accepted, with native auto-deploy already off. A reviewed blank override or `sh /app/start.sh` is preserved; an unrecognized override is cleared for Dockerfile CMD. The operator verifies functional settings, all environment values and the latest deployment ID unchanged except the intended command. It never deploys or repairs database credentials. Full real-model staging, operations/legal approval and exact-main release qualification still apply. Do not select both production operations in one dispatch.

## Save-only production defaults — 2026-10-12

The owner authorized adding known settings, including `info@onesa.eu`, to the existing
production Render service. `repair-hosting.yml` has an explicit `production_defaults`
operation on reviewed `dev`, requiring successful exact-source CI/hygiene and first-attempt
owner dispatch. It saves missing nonsecret values only, preserves existing credentials
and custom profiles, verifies the production target/native auto-deploy off, and records
readback and unchanged deployment identity. It does not deploy, change Vercel, create
resources or supply missing production database/model/embedding credentials.

The retained Ollama tag and pinned semantic embedding metadata are prepared profiles,
not proof of a hosted model. Keep model/embedding endpoints unconfigured until real
approved services exist; email stays disabled pending worker/delivery qualification.
The historical inventory below does not describe the post-operation state. The workflow
receipt is the current evidence; production release gates remain mandatory.

Names only. Never paste credential values into chat, Git, generated reports or
frontend/public variables. The source of truth is backend `app/config.py`; all
**47** declared settings below use its existing `ONESA_` prefix. The read-only
hosting diagnostic derives names statically and emits nonempty booleans, without
importing application settings or returning values. A present key does not prove
rotation, scope, format, permissions or endpoint reachability.

The expanded authenticated readback returned **zero nonempty keys out of all 47**
application settings. Missing optional overrides still have code defaults; those
defaults do not satisfy the mandatory hosted prerequisites. Every credential and
operator decision must be separately scoped to staging and production. Do not use
Portal's connection string or global shared credential environment group.

| Actual key | Purpose | Requirement | Scope | Provider/source | Observed configuration |
| --- | --- | --- | --- | --- | --- |
| `ONESA_MODEL_BACKEND` | Inference adapter (vllm hosted; preserve Ollama locally) | Required staging/production | Separate staging/production API; worker validation also reads Settings | Approved model/operator configuration → Render | Missing (authenticated readback) |
| `ONESA_MODEL_NAME` | Exact generation checkpoint identifier | Required staging/production | Separate staging/production API; worker validation also reads Settings | Approved model/operator configuration → Render | Missing (authenticated readback) |
| `ONESA_MODEL_MAX_OUTPUT_TOKENS` | Output token ceiling | Optional bounded default; review before release | Separate staging/production API; worker validation also reads Settings | Approved model/operator configuration → Render | Missing explicit override (authenticated readback); default is not qualification |
| `ONESA_MODEL_CONTEXT_LENGTH` | Context/admission token budget | Optional bounded default; review before release | Separate staging/production API; worker validation also reads Settings | Approved model/operator configuration → Render | Missing explicit override (authenticated readback); default is not qualification |
| `ONESA_MODEL_QUANTIZATION` | Model provenance metadata | Optional bounded default; review before release | Separate staging/production API; worker validation also reads Settings | Approved model/operator configuration → Render | Missing explicit override (authenticated readback); default is not qualification |
| `ONESA_MODEL_REVISION` | Pinned generation revision metadata | Optional bounded default; review before release | Separate staging/production API; worker validation also reads Settings | Approved model/operator configuration → Render | Missing explicit override (authenticated readback); default is not qualification |
| `ONESA_MODEL_MODALITIES` | Declared model modalities; current input remains text | Optional bounded default; review before release | Separate staging/production API; worker validation also reads Settings | Approved model/operator configuration → Render | Missing explicit override (authenticated readback); default is not qualification |
| `ONESA_MODEL_TEMPERATURE` | Sampling temperature | Optional bounded default; review before release | Separate staging/production API; worker validation also reads Settings | Approved model/operator configuration → Render | Missing explicit override (authenticated readback); default is not qualification |
| `ONESA_DATABASE_URL` | Dedicated AI SQLAlchemy/psycopg3 database connection | Required staging/production | Separate staging/production API + worker | Actual isolated AI database URL and scoped role → Render | Missing (authenticated readback) |
| `ONESA_PUBLIC_ORIGIN` | Exact frontend HTTPS origin | Required staging/production | Separate staging/production API + worker | Approved model/operator configuration → Render | Missing (authenticated readback) |
| `ONESA_SECURE_COOKIES` | Secure browser-session cookie policy | Required staging/production | Separate staging/production API + worker | Approved model/operator configuration → Render | Missing explicit override (authenticated readback); default is not qualification |
| `ONESA_SESSION_HOURS` | Session lifetime | Optional bounded default; review before release | Separate staging/production API; worker validation also reads Settings | Approved model/operator configuration → Render | Missing explicit override (authenticated readback); default is not qualification |
| `ONESA_AUTH_RATE_LIMIT` | Account authentication throttle | Optional bounded default; review before release | Separate staging/production API; worker validation also reads Settings | Approved model/operator configuration → Render | Missing explicit override (authenticated readback); default is not qualification |
| `ONESA_AUTH_HASH_CONCURRENCY` | Bounded expensive password hashing | Optional bounded default; review before release | Separate staging/production API; worker validation also reads Settings | Approved model/operator configuration → Render | Missing explicit override (authenticated readback); default is not qualification |
| `ONESA_KNOWLEDGE_UPLOAD_CONCURRENCY` | Bounded simultaneous document extraction | Optional bounded default; review before release | Separate staging/production API; worker validation also reads Settings | Approved model/operator configuration → Render | Missing explicit override (authenticated readback); default is not qualification |
| `ONESA_AUTH_PEER_RATE_LIMIT` | Peer authentication throttle | Optional bounded default; review before release | Separate staging/production API; worker validation also reads Settings | Approved model/operator configuration → Render | Missing explicit override (authenticated readback); default is not qualification |
| `ONESA_REGISTRATION_MODE` | Explicit open/invitation registration policy | Explicit owner decision | Separate staging/production API; worker validation also reads Settings | Approved model/operator configuration → Render | Missing explicit override (authenticated readback); default is not qualification |
| `ONESA_ACCESS_OPERATOR_USER_IDS` | Approved invitation-operator UUID allowlist | Required for invitation administration | Separate staging/production API; worker validation also reads Settings | Approved model/operator configuration → Render | Missing explicit override (authenticated readback); default is not qualification |
| `ONESA_AUTH_DELIVERY_KEY` | Persistent identity-token delivery derivation secret | Required with mail | Separate staging/production API + worker | Approved secret manager → Render | Missing explicit override (authenticated readback); default is not qualification |
| `ONESA_MAIL_PROVIDER` | Identity-mail transport switch | Required for invitation/recovery delivery | Separate staging/production API + worker | Approved model/operator configuration → Render | Missing explicit override (authenticated readback); default is not qualification |
| `ONESA_RESEND_API_KEY` | Product/environment-scoped sending credential | Required with Resend | Separate staging/production API + worker | New separately scoped Resend credential → Render | Missing explicit override (authenticated readback); default is not qualification |
| `ONESA_MAIL_FROM` | Verified identity-mail sender | Required with mail | Separate staging/production API + worker | Approved model/operator configuration → Render | Missing explicit override (authenticated readback); default is not qualification |
| `ONESA_MAIL_REPLY_TO` | Approved monitored reply-to | Optional bounded default; review before release | Separate staging/production API + worker | Approved model/operator configuration → Render | Missing explicit override (authenticated readback); default is not qualification |
| `ONESA_INVITATION_HOURS` | Invitation expiry | Optional bounded default; review before release | Separate staging/production API + worker | Approved model/operator configuration → Render | Missing explicit override (authenticated readback); default is not qualification |
| `ONESA_RECOVERY_MINUTES` | Recovery expiry, at most ten minutes | Optional bounded default; review before release | Separate staging/production API + worker | Approved model/operator configuration → Render | Missing explicit override (authenticated readback); default is not qualification |
| `ONESA_MODEL_USER_CONCURRENCY` | Per-user generation leases | Optional bounded default; review before release | Separate staging/production API; worker validation also reads Settings | Approved model/operator configuration → Render | Missing explicit override (authenticated readback); default is not qualification |
| `ONESA_MODEL_GLOBAL_CONCURRENCY` | Shared generation leases; qualify against GPU capacity | Optional bounded default; review before release | Separate staging/production API; worker validation also reads Settings | Approved model/operator configuration → Render | Missing explicit override (authenticated readback); default is not qualification |
| `ONESA_MODEL_USER_REQUESTS_PER_MINUTE` | Per-user generation request quota | Optional bounded default; review before release | Separate staging/production API; worker validation also reads Settings | Approved model/operator configuration → Render | Missing explicit override (authenticated readback); default is not qualification |
| `ONESA_MODEL_GLOBAL_REQUESTS_PER_MINUTE` | Shared generation request quota | Optional bounded default; review before release | Separate staging/production API; worker validation also reads Settings | Approved model/operator configuration → Render | Missing explicit override (authenticated readback); default is not qualification |
| `ONESA_MODEL_USER_RESERVED_TOKENS_PER_MINUTE` | Per-user reserved-token quota | Optional bounded default; review before release | Separate staging/production API; worker validation also reads Settings | Approved model/operator configuration → Render | Missing explicit override (authenticated readback); default is not qualification |
| `ONESA_MODEL_GLOBAL_RESERVED_TOKENS_PER_MINUTE` | Shared reserved-token quota | Optional bounded default; review before release | Separate staging/production API; worker validation also reads Settings | Approved model/operator configuration → Render | Missing explicit override (authenticated readback); default is not qualification |
| `ONESA_KNOWLEDGE_MAX_DOCUMENTS` | Per-user document quota | Optional bounded default; review before release | Separate staging/production API; worker validation also reads Settings | Approved model/operator configuration → Render | Missing explicit override (authenticated readback); default is not qualification |
| `ONESA_KNOWLEDGE_USER_TEXT_BYTES` | Per-user retained extracted-text quota | Optional bounded default; review before release | Separate staging/production API; worker validation also reads Settings | Approved model/operator configuration → Render | Missing explicit override (authenticated readback); default is not qualification |
| `ONESA_KNOWLEDGE_GLOBAL_TEXT_BYTES` | Shared retained extracted-text quota | Optional bounded default; review before release | Separate staging/production API; worker validation also reads Settings | Approved model/operator configuration → Render | Missing explicit override (authenticated readback); default is not qualification |
| `ONESA_GENERATION_TIMEOUT` | Bounded generation wall time | Optional bounded default; review before release | Separate staging/production API; worker validation also reads Settings | Approved model/operator configuration → Render | Missing explicit override (authenticated readback); default is not qualification |
| `ONESA_MODEL_BASE_URL` | Actual authenticated TLS generation API base | Required staging/production | Separate staging/production API; worker validation also reads Settings | Approved model/operator configuration → Render | Missing (authenticated readback) |
| `ONESA_MODEL_API_KEY` | Generation gateway bearer credential | Required staging/production | Separate staging/production API; worker validation also reads Settings | Approved secret manager → Render | Missing (authenticated readback) |
| `ONESA_EMBEDDING_BACKEND` | Separate embedding adapter; http for qualified semantic profile | Optional bounded default; review before release | Separate staging/production API; worker validation also reads Settings | Approved model/operator configuration → Render | Missing explicit override (authenticated readback); default is not qualification |
| `ONESA_EMBEDDING_NAME` | Pinned embedding model identifier | Required for semantic profile | Separate staging/production API; worker validation also reads Settings | Approved model/operator configuration → Render | Missing explicit override (authenticated readback); default is not qualification |
| `ONESA_EMBEDDING_BASE_URL` | Actual authenticated TLS embedding API base | Required for semantic profile | Separate staging/production API; worker validation also reads Settings | Approved model/operator configuration → Render | Missing explicit override (authenticated readback); default is not qualification |
| `ONESA_EMBEDDING_API_KEY` | Separate embedding gateway bearer credential | Required for semantic profile | Separate staging/production API; worker validation also reads Settings | Approved secret manager → Render | Missing explicit override (authenticated readback); default is not qualification |
| `ONESA_METRICS_TOKEN` | Protected metrics bearer credential | Required staging/production | Separate staging/production API + worker | Approved secret manager → Render | Missing explicit override (authenticated readback); default is not qualification |
| `ONESA_EMBEDDING_REVISION` | Embedding revision plus protocol/index version | Required for semantic profile | Separate staging/production API; worker validation also reads Settings | Approved model/operator configuration → Render | Missing explicit override (authenticated readback); default is not qualification |
| `ONESA_EMBEDDING_QUERY_INSTRUCTION` | Versioned retrieval query instruction | Required for Qwen retrieval profile | Separate staging/production API; worker validation also reads Settings | Approved model/operator configuration → Render | Missing explicit override (authenticated readback); default is not qualification |
| `ONESA_DOCUMENTATION_SOURCES_DIRECTORY` | Private packaged documentation source directory | Optional bounded default; review before release | Separate staging/production API; worker validation also reads Settings | Approved model/operator configuration → Render | Missing explicit override (authenticated readback); default is not qualification |
| `ONESA_DOCUMENTATION_ENGINEERING_USER_IDS` | Documentation-engineering UUID allowlist | Optional bounded default; review before release | Separate staging/production API; worker validation also reads Settings | Approved model/operator configuration → Render | Missing explicit override (authenticated readback); default is not qualification |
| `ONESA_ENVIRONMENT` | Explicit staging/production environment | Required staging/production | Separate staging/production API + worker | Approved model/operator configuration → Render | Missing (authenticated readback) |

## Processes and provider settings

- **API:** reads all Settings above; Render injects `RENDER=true` and `PORT` for
  the Docker command. `RENDER` enforces an explicit hosted environment. Port is
  provider-owned, not a secret or frontend setting.
- **Identity worker:** `python -m app.identity_worker` reads the same Settings;
  operational use is database, identity-delivery key, mail provider/from/reply-to
  and Resend credentials. Full production Settings validation still runs, so
  mirror the scoped validated base configuration rather than inventing worker
  aliases. It does not need public inbound HTTP. An actual AI worker is not
  provisioned/qualified; approve its cost separately. Its key must match the
  corresponding API's persistent delivery key, never the other product's key.
- **Migrations:** only `ONESA_DATABASE_URL`, injected into a one-off reviewed
  process with migration-role credentials. Same key, different least-privilege
  process scope. Alembic uses NullPool and the installed psycopg3 driver; no
  hosted inference credential is needed for schema initialization.
- **Separate embedding service:** `ONESA_EMBEDDING_API_KEY`; model path/device/port
  are explicit CLI parameters (`--model-directory`, `--device cpu`, `--port 8364`).
  It binds loopback; TLS ingress is a separately secured gateway. Existing macOS
  dependency lock is not a qualified Linux lock. No new public model port.
- **Vercel chat frontend:** server-only `ONESA_API_URL` is **missing**. Supply only
  the actual qualified Render origin. Never place any of the secret keys above
  in `NEXT_PUBLIC_*`. `NEXT_PUBLIC_ONESA_DOCS_URL` is an optional public docs URL,
  not an inference endpoint; a deployed documentation service is not established.
- **GitHub Actions:** `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`,
  `RENDER_API_KEY`, `RENDER_BACKEND_SERVICE_ID` exist as repository secrets.
  `RELEASE_QUALIFICATION_JSON` is absent; populate only with real exact-commit
  acceptance/approvals. Account secrets authorize diagnostics, not paid purchases.

For semantic retrieval, deliberately configure `ONESA_EMBEDDING_BACKEND=http`, the
verified Qwen model/revision/protocol and 256-dimensional endpoint after Linux
qualification and backed-up per-owner reindex acceptance. Lexical is the current
default; do not silently describe that cloud default as semantic retrieval.

Save environment changes without deployment while native auto-deploy remains off.
Confirm the immutable reviewed SHA before any authorized staging deploy. Do not
restart the older revision by saving-and-deploying incomplete settings. Production
promotion retains the four qualification gates, actual model/database/embedding
path tests, and separately verified exposed-credential revocation/replacement.

The owner now requires free services only. See [free staging setup](FREE_STAGING_SETUP.md).
The historical [database/GPU proposal](HOSTED_AI_PROPOSAL.md) preserves permissions,
TLS, restore procedures and the exact paid-resource approvals still needed.

## Owner-created Workers AI endpoint — verified 2026-10-12

Authenticated readback confirms `onesa-ai-platform-worker-ai` exists in the selected
owner account and has an `AI` binding. Its URL is
`https://onesa-ai-platform-worker-ai.andrewgotora.workers.dev`. The deployed module
is the Cloudflare example: every request runs two hardcoded prompts against
`@cf/meta/llama-3-8b-instruct` and returns their responses. It does not check a bearer
credential, accept the Onesa chat request, expose an OpenAI-compatible API, or run an
embedding model. Anonymous root, health, readiness and model-list checks returned
HTTP 500. Correct resource identity and an AI binding do not establish real serving
readiness. No Worker code, binding, model or backend provider setting was changed.

The prepared Cloudflare backend transport expects authenticated account API bases:
`https://api.cloudflare.com/client/v4/accounts/<ACCOUNT_ID>/ai/v1` for inference and
`https://api.cloudflare.com/client/v4/accounts/<ACCOUNT_ID>/ai` for embeddings.
It validates the reviewed Qwen3 generation model and Qwen3 embedding/MRL256 profile;
the demo's Llama model and URL do not satisfy that configuration. Keep provider tokens
server-side. Actual authenticated streaming, embedding shape, ingestion/retrieval and
user isolation acceptance remain required before hosted AI is qualified. See
[Workers AI REST API](https://developers.cloudflare.com/workers-ai/get-started/rest-api/)
and [OpenAI compatibility](https://developers.cloudflare.com/workers-ai/configuration/open-ai-compatibility/).
