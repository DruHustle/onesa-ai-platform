# Platform split report

2026-10-09, Europe/Berlin. **Local migration verified; production release remains blocked.**
The platform was migrated, not recreated. No remote deployment, publication, model
training, NVIDIA acceptance, penetration audit or legal approval is claimed.

## Baseline and inventory

Actual repository: `onesa-ug/onesa-ai-platform`, branch master, clean at `1ea8d54`.
The enclosing workspace resolves to an unrelated ancestor repository; all Git work
was scoped to this application's checkout. Baseline branch:
`baseline/platform-split-20261009`. Private tracked-file fingerprints, logs and
pre-migration Next output are preserved in `data/migration-baseline`. The private
custom-format database dump is `data/backups/platform-split-20261009.dump`.
Pre-split runtime images have explicit `pre-split-20261009` rollback tags.
No unrelated user changes, company portal or robotics source was modified.

| Original | New location |
| --- | --- |
| apps/chat | onesa-ai-platform-frontend/apps/chat |
| apps/docs | onesa-ai-platform-frontend/apps/docs |
| services/api | onesa-ai-platform-backend |
| training | onesa-ai-platform-backend/training |
| evaluation | onesa-ai-platform-backend/evaluation |
| infra/docker/chat.Dockerfile | onesa-ai-platform-frontend/Dockerfile |
| infra/docker/api.Dockerfile | onesa-ai-platform-backend/Dockerfile |

All tracked source/asset moves used `git mv`, retaining one repository/history.
Ignored dependencies and scoped docs outputs moved with their applications. Root
scripts, infrastructure, classified Markdown/exports, security backports, `.env`,
virtual environment, model weights/native runtime and `data` artifacts remain.

The actual Next application implements `/`, `/knowledge`, `/agents`, `/travel`,
English/German auth/navigation and local locale preference. Registration/login,
history, streaming, knowledge ingestion, bounded local agents and saved itineraries
remain implemented. There is no separate admin app, arbitrary settings service,
live travel provider, trained Onesa model or deployed semantic embedding service.
The docs portal has separately classified public/internal builds and existing-session
engineering authorization. FastAPI owns versioned `/api/v1` APIs, DB access, auth,
model orchestration and observability. Entry point remains `app.main:create_app`;
Alembic remains a one-shot migration entry point. Chat stays port 3100; API stays
8000/private; docs stay loopback 3200/3201; native Ollama stays loopback 11434.
Existing root Make and Compose commands are preserved with migrated paths.

## Implemented changes

Independent frontend/backend Docker contexts, digest-pinned multi-stage builds,
non-root health-checked runtimes and bounded graceful shutdown. Root Compose keeps
its project/service/volume identity. Production adds resource limits, read-only
filesystems, tmpfs, dropped capabilities and private DB/inference; the local rehearsal
uses those application controls. The existing PostgreSQL/pgvector dependencies and
model adapters are retained. vLLM gets a private readiness probe and configurable
GPU count; hardware execution remains pending.

The frontend now reads private API origin at runtime in a BFF, preserving streaming
bodies, abort signals, Origin/CSRF and separate Set-Cookie headers. It validates the
configured destination, removes caller forwarding headers, restricts routes and
rewrites backend redirects to same-origin relative locations. Deadline defaults to
135 seconds. Shared API transport and generated OpenAPI TypeScript contracts live
in `packages/api-client`; typed session discovery uses them. Existing loosely typed
response dictionaries are honestly represented as unknown fields, not invented types.
Caddy supplies direct same-origin API routing with flushing and no encoding buffer.

Backend DB readiness moves off the async event loop with bounded probes/SQL timeout.
Protected metrics include separate model/database availability gauges. Existing JSON
logs/correlation IDs and inference latency/outcome metrics are preserved. Private
Prometheus scrape/alert templates are added; operator delivery remains unqualified.
PDF extraction now uses a disposable isolated interpreter with empty environment,
temporary directory, CPU/FD/file limits, Linux address-space cap and wall timeout.
It remains within the API container's identity/network; full worker confinement
is outstanding. Model/user/document authorization is unchanged.

Paths in Make, CI, scripts, documentation, package scripts and generators are updated.
CI includes API-client drift, secret patterns, existing audits, container builds/startup
and backend/frontend/docs/browser checks. Manual independent image packaging produces
reviewable artifacts without deployment. Environment examples cover development,
test, TLS staging and production. Backup verification, preview-first retention,
restart rehearsal and operational/rollback instructions are implemented.

## APIs, schema and preservation

No public endpoint, request/response contract or schema revision changed. Exported
OpenAPI is byte-identical. All Alembic files are byte-identical to baseline and head
remains `608f3f79f76e`; no downgrade/reset/new migration was applied. Private `.env`
fingerprint matched after upgrade. Native model/runtime/data paths remain unchanged.

A real restore into `onesa_split_20261009_restore` verified all eleven public tables
using sorted content fingerprints and counts, including users/sessions, conversations,
messages, documents/chunks, agent/inference runs, trips and rate buckets. Verification
was repeated after the main local upgrade and before synthetic real-browser registration;
all content still matched. Snapshot: 22 users, 26 conversations, 67 messages, 7 documents,
7 trips, 7 agent runs. Subsequent synthetic browser acceptance deliberately adds an
account/messages; it is not a data-loss or schema change. Knowledge extracted content
and vectors live in PostgreSQL; no public frontend document storage was introduced.
Stored evaluation artifacts/model metadata/document exports are preserved at root.

## Verification results

| Check | Actual result |
| --- | --- |
| Baseline CPU + lint/format/strict typing | 61 passed, 23 DB-dependent skipped; 18 app files |
| Baseline real PostgreSQL/migrations | 84 passed |
| Baseline frontend lint/types/production build | Passed after preserving stale .next output |
| Baseline Chromium mock workflows | 4 passed on verified port 3101 |
| Split CPU + lint/format/strict typing | 64 passed, 23 DB-dependent skipped; 19 app files |
| Split real PostgreSQL/security/migrations | 87 passed |
| Frontend production lint/types/build | Passed with App Router BFF/shared API package |
| Independent frontend/backend Docker builds | Passed; actual runtime startup healthy |
| Production/GPU Compose + production Caddy config | Validated without public launch |
| Mock browser through Caddy direct API | 5 passed on loopback 3120 |
| Mock browser through Next BFF + Caddy | 5 passed on loopback 3121 |
| Real Ollama browser through migrated BFF | 1 passed: streaming/context/history/stop/retry |
| Isolated service restart | Session/history unchanged; ready in 1.85 seconds |
| Baseline image rollback and forward recovery | Same isolated session/full conversation survived both switches |
| Real backup restore + content integrity | All 11 public tables match, repeated after upgrade |
| Scoped docs builds/types/assets/PDFs/security | Passed; 12 installed backport security checks |
| Dependency audits | Backend no known vulnerabilities; frontend/docs zero findings |
| Secret patterns/private env/source checks | Passed; private .env unchanged; 26 browser JS files contain no configured private credentials |
| API/type drift | OpenAPI unchanged; generated client drift check passes |

One upstream Starlette/HTTPX TestClient deprecation warning remains. The initial
frontend baseline build hit a stale-output ENOTEMPTY; preserved output and clean build
passed. An initial browser invocation used wrong port 3110 and failed connection;
correct verified mock port 3101 passed. Initial post-move formatter/import/type checks
and a container type check exposed path/typing errors; fixed and final checks passed.
The added redirect check initially assumed FastAPI 307; accepting Next.js canonical
308 and checking the same origin produced five passes on both paths. A docs browser
run against a deliberately read-only build lacked Try it out; the explicitly configured
loopback playground build was regenerated before final acceptance. These failures are
retained in private logs and are not presented as successful runs.

## Deployment status and production gates

The existing local real-model platform has been upgraded; DB/inference remain private.
Protected documentation remains on ports 3200/3201. An isolated mock rehearsal verified
hardening, both routing paths, startup and restart; its volume and baseline dump are
preserved. This is not remote staging or live production acceptance.

Passed locally: separate builds, implemented feature regressions, auth/owner/CSRF/tool
checks, database preservation, real streaming/cancellation, private inference topology,
container startup, backup restore, reproducible contracts/docs and JSON/metrics controls.

Outstanding release blockers: target-host DNS/TLS/Secure-cookie acceptance and remote
staging; NVIDIA/vLLM hardware and load/performance qualification; real semantic embeddings
(M3.2) and provider acceptance where required; per-target ingress capacity/auth limits;
stronger hostile-PDF worker confinement and independent security review; production
retention/encrypted off-host backups and measured RPO/RTO; live monitoring/alert delivery,
GPU diagnostics/host storage metrics; comprehensive accessibility/security/load checks;
target-host release rollback acceptance; recorded legal/privacy/ownership
and deployment/residency release decisions. No project license was added.

## Rollback and continuation

Keep the baseline branch, tagged images and private dump until target acceptance.
Use a separate baseline checkout and preserved secrets with the existing project/volume
identity and tagged images (`--no-build`, `pull_policy: never`); never hard-reset the
migration or run `down -v`. No schema rollback is needed. Restore data only into a new
`_restore` database and verify before manual promotion. See
[deployment runbook](../deployment/PRODUCTION_DEPLOYMENT.md) and
[backup instructions](../database/BACKUP_RESTORE.md). Isolated restart/restore were tested;
baseline-image rollback and forward recovery were also verified on the isolated stack;
main-service rollback was deliberately not performed. No commit, push or remote release occurred.
Continue M3.2 qualification after reviewing this split; do not rewrite implemented features.
