# System architecture

Onesa AI is European-based, general-purpose and applicable to European and international
markets. Shared services have no geographic routing or country/language whitelist.
African/regional use cases are optional specializations. See ADR 0003 and AI_SOVEREIGNTY.md.

Onesa is a modular monorepo with three ordinary deployables: Next.js, FastAPI, and
PostgreSQL/pgvector. A one-shot Alembic service applies migrations before API startup.
Next.js proxies `/api/v1`, `/health`, and `/ready` to the private API, maintaining a
same-origin cookie boundary. Only the loopback web port is published in development.

FastAPI modules separate sessions/auth, conversations, chat, knowledge, bounded
agents, structured travel, model serving, and observability. SQLAlchemy repositories
live within these small domain modules. Stable UUIDs and ownership predicates guard
all content; PostgreSQL constraints, row locks and leases coordinate concurrent requests.
No Redis, Kubernetes, robotics, or separate model per application is introduced.

## Model and application independence

ModelClient defines async health and cancellable text streaming. MockModelClient is
deterministic and explicitly labelled. OllamaModelClient and VLLMModelClient share a private OpenAI-compatible
protocol with bounded timeouts, configured generation settings, discovery and strict
stream termination. It never falls back to mock on failure. The public model alias is
`default`; safe model identifier, backend, context, modalities, quantization and revision
are additive public metadata. Credentials, URLs and filesystem paths remain private.
Native loopback Ollama runs the installed Qwen3 4B Q4_K_M on this Apple M3 host;
Docker Desktop reaches it through host.docker.internal. Context is 8192 tokens.

Travel uses an ItineraryPlanner interface, choosing deterministic mock planning or
JSON-validated planning through the shared ModelClient. Agents use explicit steps or
a planner (deterministic mock/model proposal); only registered permitted tools execute.
The initial tools are local arithmetic and text statistics, with no arbitrary code/network.

Knowledge stores bounded extracted text and versioned 256-dimensional vectors. The
CPU baseline hashes lexical terms; a configured HTTP embedding endpoint can provide
real model embeddings of the same dimension. A dimension change requires a migration.
Retrieval filters ownership and embedding version before ordering by cosine distance.
Sources persist with assistant messages. Documents/model outputs are untrusted data.

## Failure and deployment boundaries

A chat transaction commits a user turn and generation lease before streaming. One
active run is allowed per conversation. A successful response commits assistant text
before `message_end`; cancellation/failure saves no successful partial assistant.
Leases expire after the generation deadline plus 10 seconds, allowing restart recovery.
Trips use typed JSONB itineraries and optimistic revisions. Sessions are opaque,
hashed in storage, expiring/revocable, and CSRF protected. Agents have bounded planning
and execution; unfinished stale runs are classified failed on inspection.

Readiness checks the configured model and expected Alembic revision. Health is process
liveness. Metrics require a separate bearer credential and stay outside the web proxy.
Request logs contain route templates/status/correlation IDs, not user content or tokens.

Optional GPU serving runs on a Linux/NVIDIA host, possibly separate from the application
host. Production override adds a same-origin Caddy TLS proxy and hardened app containers.
Phase B training is a separate environment/workload with local weights and approved data.
These profiles are configuration-validated; actual GPU/TLS deployment remains unverified.
Separate machines/GPUs do not implicitly pool VRAM. Scale inference by replication first;
tensor parallelism requires explicit compatible GPU/network resources.

See ADR 0002 for the bounded MVP's JSONB and storage choices. Full production qualification,
semantic-embedding execution, NVIDIA/vLLM execution and external provider integration remain pending.

## Generalization without contract changes

Training language tags and domain metadata now support international, enterprise and industrial
adaptation. Candidate records describe proposed model families and preserve evaluation evidence;
one active model remains configured behind default. No database migration or public API change
was required. Per-user document IDs select independent knowledge sets; named collections and
typed flexible metadata (languages/domains/tags/regions/provenance) are future storage extensions.
They must inherit ownership/isolation rather than fixed continent or country categories.

Registered tools and explicit grants can serve enterprise, industrial and travel use cases.
No external business/industrial tool integration is present. Interface locale catalogs and
non-sensitive preferences are separate from training labels and model coverage. Vision/speech
remain future adapters; portability does not imply verified performance or legal compliance.

## Documentation ecosystem

A shared Docusaurus framework creates independent public and internal builds with separate input directories, approved assets, search and retrieval collections. Loopback delivery gateways enforce existing Onesa identity on every internal request, including PDFs, diagrams, scripts and indexes. The API repeats engineering authorization at internal retrieval time and uses the existing Knowledge embedding/model adapters. Public sources and artifacts are allowlisted; no database migration or second AI runtime is introduced. See [documentation system](../development/DOCUMENTATION_SYSTEM.md).

## Frontend/backend split

The parent project retains one Git history. `onesa-ai-platform-frontend` owns the shared
Next.js app, documentation app and typed browser API package. `onesa-ai-platform-backend`
owns the unchanged domain package/migrations and separate training/evaluation tools.
Each directory is a self-contained Docker build context with a pinned multi-stage
non-root runtime. Root scripts, Compose, native model/data storage, classified sources,
exports and shared security backports stay at the parent. No schema or public API
change accompanies the move. Same-origin access works through a runtime-configured
BFF or direct Caddy API routing; both are verified in the local split rehearsal.
See [migration report](../development/PLATFORM_SPLIT_REPORT.md) and
[plan](../development/PLATFORM_SPLIT_PLAN.md).

## Acceptance 005 deployment

The application architecture and public API are unchanged. Production-like local TLS staging
adds an isolated Compose namespace, Caddy internal CA, separate DB roles/secrets, Prometheus,
Alertmanager and an authenticated encrypted backup/alert worker. See the executed inventory
and diagram in `deployment/ACCEPTANCE_STAGING.md`. Security qualification bounds hash/parser
concurrency, enforces TLS redirects at configured ingress and adds Linux PDF syscall restrictions.
The native adapter supports absent local credentials without issuing an invalid Bearer header.
These operational controls add no new AI feature, provider or training pipeline.

## GitHub release verification — 2026-10-09

Source-only main is now published to the private Onesa UG repository. Added manual
GitHub Actions deployments with exact-commit CI/hygiene gates, pinned Vercel CLI and
Render live-status/commit verification. Native provider auto-deploys are disabled in
the deployment standard. Provider projects/secrets and actual target acceptance are
still required; no cloud deployment or production qualification is claimed.

Resolved first remote CI failures by generating synthetic screenshots in clean docs
builds, waiting for documentation gateways to listen, updating operations cryptography
and its lockfile dependencies, and skipping cleanup when staging was never created.
Patched operations encryption regression passed; its dependency audit has zero findings.
M3.2 semantic retrieval qualification remains pending. Original Git metadata backup
is temporary and will be removed at the owner’s request after remote source verification.


## Public documentation hosting — 2026-10-10

The owner selected docs.onesa.eu and confirmed Vercel public-use eligibility.
Prepared separate GitHub-built preview/production hosting for the allowlisted
Docusaurus public site. Only build-public is uploaded; internal engineering stays
behind its authenticated gateway. Static mode honestly disables documentation
assistance. Fresh isolated mock screenshots resolve clean-build missing images;
existing generated local files and the application on port 3100 are preserved.
The clean build rendered four public diagrams and seven public manuals, passed
source classification, 13 dependency-security tests, zero npm vulnerabilities,
TypeScript, and desktop/mobile static acceptance. See
../engineering/DOCUMENTATION_HOSTING.md for deployment and actual DNS readback.
Hosting/domain verification is not yet completed at this recorded source state.
No API/model/data configuration, application production guard or paid plan changed.
Application release remains NO-GO; internal authentication qualification is pending.
