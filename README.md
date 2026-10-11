# Onesa AI

> Current private-Free release policy: [safeguards and external owner authorization](docs/development/PRIVATE_FREE_SAFEGUARDS.md). Legacy JSON approval is retired; native protection requirements below apply only to a verified supported configuration.

Onesa AI is a European-based, general-purpose, modular artificial intelligence platform
for enterprise, developer, institutional and consumer applications across European and
international markets. Shared self-hosted infrastructure serves Chat, Knowledge, Agents
and Travel using configurable open-weight models.

African languages and regional knowledge are optional international specializations;
they do not define or limit the platform. See [market scope](docs/product/MARKET_SCOPE.md)
and [customization strategy](docs/models/MODEL_CUSTOMIZATION_STRATEGY.md).

## Run the platform

Requires Docker with Compose. Generate private development secrets once:

```sh
python3 scripts/bootstrap_env.py
make up
```

Open http://localhost:3000 and create an account. If port 3000 is occupied, change
**both** `ONESA_CHAT_PORT` and `ONESA_PUBLIC_ORIGIN` in `.env` (for example, `3100`
and `http://localhost:3100`). `make down` stops the stack without deleting data.
This workspace is currently configured and running at **http://localhost:3100**.
PostgreSQL and the API are private; only the loopback Chat port is published.

## Implemented

- FastAPI, PostgreSQL/SQLAlchemy, reversible Alembic migrations, secure sessions,
  CSRF protection, authentication throttling and per-user ownership.
- Next.js/TypeScript/Tailwind Chat with streamed Markdown/code responses, history,
  conversation editing/deletion, cancellation, mobile and keyboard navigation.
- Configurable mock/Ollama/vLLM inference behind a stable model-client interface.
- Validated text/PDF ingestion, versioned pgvector retrieval, reindexing and chat sources.
- Registered bounded tools, permission checks, execution history and cancellation.
- Structured, saved and revisable travel itineraries.
- Provenance-aware dataset preparation, evaluation, dry-run training checks, optional
  LoRA/QLoRA execution, base-versus-candidate evaluation and profile-aware candidate metadata.
- Configurable English/German navigation and sign-in catalogs; other workspace copy
  remains English. Interface translations do not assert model-language performance.
- Protected Prometheus metrics, correlation IDs, structured request logs, request
  size limits, non-root containers, backup/restore scripts, CI and deployment templates.

Fresh installations default to labelled **mock** inference. This workspace now uses verified
native Ollama with Qwen3 4B Q4_K_M at an 8192-token context; Chat at port 3100 generates real
responses. See [Ollama setup](docs/models/OLLAMA_SETUP.md) and
[measured inference results](docs/models/INFERENCE_BENCHMARKS.md).
Default retrieval is a **lexical vector baseline**, not semantic model embeddings.
A configured local vLLM/embedding server can replace these without frontend changes.
Travel providers are unconfigured; no live prices, availability or bookings are claimed.

## Verify and continue

```sh
make install
make check
npm --prefix onesa-ai-platform-frontend/apps/chat ci
make frontend-check
make openapi
```

Real PostgreSQL tests need the isolated database documented in
[local development](docs/deployment/LOCAL_DEVELOPMENT.md); use `make integration`.
Original browser checks expect a mock stack; real-model checks require
`ONESA_REAL_INFERENCE=1 ONESA_BROWSER_URL=http://localhost:3100 npm --prefix onesa-ai-platform-frontend/apps/chat run test:e2e -- tests/real.spec.ts`.
See [local development](docs/deployment/LOCAL_DEVELOPMENT.md) for isolated mock regression commands.
GPU and production overrides are documented separately; neither is started by default.

[Engineering policies](AGENTS.md) contain the continuation workflow.
Use the [roadmap](docs/product/ROADMAP.md) for unfinished milestones.
The [documentation index](docs/README.md) maps implementation and operations.

Phase A uses an open-weight foundation model. Phase B substitutes evaluated Onesa
weights/adapters behind the same API and applications. Robotics is a future downstream
client. The explicitly requested Qwen3 4B weights were downloaded for native Mac inference.
No model fine-tuning or external deployment occurred.
Project software ownership/licensing remains unresolved; no license has been invented.


## Separately buildable applications

Frontend: `onesa-ai-platform-frontend` (shared Chat/Knowledge/Agents/Travel Next.js
application, docs app and generated typed API client). Backend:
`onesa-ai-platform-backend` (existing FastAPI, migrations, tests and separate
training/evaluation tools). Both have independent Dockerfiles/build contexts.
The parent retains Git history, Compose, docs, scripts, security backports and private data.
`docker build -t onesa-chat:local onesa-ai-platform-frontend` and
`docker build -t onesa-api:local onesa-ai-platform-backend` need no sibling source.
Native Ollama and persisted state remain at their existing root data paths.

`make api-client contract-check` regenerates/checks browser types against unchanged
OpenAPI. Development/test/staging/production examples live in `.env.example` and
`infra/deployment`; target secrets must be supplied privately. The local application
remains at http://localhost:3100. See [split report](docs/development/PLATFORM_SPLIT_REPORT.md)
for verified checks, baseline/restore/rollback evidence and outstanding production gates.
A verified local migration does not constitute a verified live production deployment.

## Onesa UG repository governance

Organization repository: `onesa-ug/onesa-ai-platform`; primary branch: `main`.
This project has its own Git root; the surrounding `onesa-ug` workspace is not its
repository root. Frontend/backend retain this history and deploy independently.

[Separate build/test guide](docs/engineering/BUILD_AND_TEST.md),
[deployment guide](docs/engineering/DEPLOYMENT.md), [Engineering policies](AGENTS.md) and [Engineering policies](AGENTS.md).
Runtime environment examples are available in both application directories and
`infra/deployment/`; existing root examples remain the Compose development reference.

The initial local baseline included generated internal/public manuals. The owner
subsequently deprioritized history and authorized source publication. A fresh source-only
`main` excludes those artifacts while the original Git metadata and work remain in
private local backup. See [Vercel/Render deployment](docs/engineering/VERCEL_RENDER.md).
Live deployment and production acceptance must be verified on the actual providers.

## Selected cloud deployment

Vercel hosts the frontend; Render hosts the backend. See
[provider setup](docs/engineering/VERCEL_RENDER.md) and root `render.yaml`.
Configuration is prepared; account provisioning and remote acceptance are not yet verified.

[Contributing](CONTRIBUTING.md) · [Security](SECURITY.md) · [Verified branch protection status](docs/development/BRANCH_PROTECTION_REPORT.md). Main protection is currently **BLOCKED — NOT ENFORCED** by GitHub plan eligibility.

The selected policy is [GitHub Free with private repositories](docs/development/FREE_GITHUB_PLAN.md). PR and check discipline is voluntary until server protection is supported; no upgrade or visibility change is proposed.

[Hosted public Actions and private runner operations](docs/engineering/SELF_HOSTED_RUNNER.md).
