# Implementation status

Updated: 2026-10-09 (Europe/Berlin).
Current milestone: **M3 — Knowledge retrieval qualification**.
First incomplete task: **M3.2 — qualify a real semantic embedding service** against
owned-document retrieval and the existing versioned 256-dimensional pgvector contract.
Preserve the implemented lexical baseline until a measured compatible replacement exists.

## Ordered task list

- [x] M0: architecture, product/stack/ADRs and persistent continuation workflow.
- [x] M1: PostgreSQL migrations; Argon2id authentication, opaque hashed sessions,
  CSRF/rotation/throttling; owned conversations; durable generation leases;
  bounded streaming/cancellation; responsive Next.js chat and private Compose services.
- [x] M2.1: shared configurable mock/Ollama/vLLM model interface, discovery,
  safe errors, strict SSE parsing, request-owned token/timing accounting and metadata.
- [x] M2.2: native Apple Silicon Ollama setup and explicitly authorized Qwen3 4B
  installation, 8192 context; preserved optional pinned Linux/NVIDIA vLLM configuration.
- [x] M2.3: actual Apple M3 model loading, direct and authenticated platform generation,
  visible streaming/cancellation, history/context, grounded chat, tools/travel and restart
  recovery; synthetic evaluation and concurrency benchmarks recorded. This completes the
  user's revised Apple Silicon M2 acceptance. NVIDIA/vLLM execution remains unverified.
- [x] M3.1: owned bounded TXT/PDF uploads, extraction/deduplication, versioned
  256-dimensional pgvector retrieval/reindexing and persisted sources/knowledge UI.
  Default vectors are a labelled lexical baseline; an HTTP semantic adapter exists.
- [ ] M3.2: qualify real semantic embeddings, retrieval quality/isolation and reindex
  behavior on approved evaluation documents. A dimensional change needs a migration.
- [x] M4 software: shared-model planner, local registered tools, explicit grants,
  validation/time/step bounds, cancellation and owned history/UI. Real text_stats planning
  and ungranted-tool rejection were checked during M2.
- [x] M5 software: typed model/mock itinerary planning, saved trips and revision UI.
  Real Berlin itinerary generation passed. External provider results remain unavailable.
- [ ] M5 provider acceptance: actual authorized travel integrations and verified live data.
- [x] M6 framework: extensible provenance/consent/approval metadata, deterministic
  dataset splits/manifests, dry-run, optional CUDA LoRA/QLoRA runner and candidate registry.
- [ ] M6 experiments: approved datasets, qualified training environment, actual fine-tuning,
  held-out base/candidate regression and reviewed release. No training has occurred.
- [x] M7 local controls: non-root containers, bounded bodies/safe logs/protected metrics,
  restricted production DB/TLS templates, CI and isolated backup/restore verification.
- [ ] M7 production acceptance: target-host TLS/security/load/retention/alerts, hostile-PDF
  worker isolation and ingress tuning. No remote CI, publication or deployment is claimed.

## Verification evidence

- `make check`: Ruff/format, strict mypy (17 application files), **41 passed, 21 skipped**
  without the integration database.
- `make integration`: **62 passed** against the isolated real PostgreSQL test database.
- Frontend lint/type/production build and rebuilt Docker startup passed. Original four
  Chromium mock flows and explicit real-model browser acceptance are recorded in the
  [M2 report](MILESTONE_2_REPORT.md). One upstream TestClient deprecation warning remains.
- Real Qwen3 baseline: **12/13 mechanical checks passed**; the arithmetic response got
  10 but violated exact-only formatting. Native function-call probe passed once. These
  synthetic probes require human review and do not establish broad quality or safety.
- Six-request concurrency 1/2 runs: mean first text 0.0717/2.8894 s; mean full-request
  completion 3.2292/6.1877 s; mean output tokens/full-request-second 29.7600/16.4833.
  One Ollama worker; concurrency 2 measures queueing. See stored raw baseline reports.
- Native daemon binds loopback only; Docker Desktop host access verified; credentials
  and model weights remain ignored. Only the requested Qwen3 4B weights were downloaded.
- Earlier dependency audits, isolated backup restore and schema head `608f3f79f76e`
  remain valid historical evidence; dependency graphs/schema were unchanged by M2.

## Product and continuation boundaries

Amendment 001 retains European-based, general-purpose, international positioning.
African languages/regions are optional specializations. Interface catalogs and candidate
profiles do not prove model coverage; Qwen3.5 comparison candidates are metadata only.
No license, certification, funding eligibility or regulatory compliance claim is made.

Read this ordered list, SESSION_HANDOFF.md, architecture and existing code. Continue
M3.2 without rewriting working components. A real embedding service/new weights or
external integrations need explicit authorization when outside current approved scope.
NVIDIA deployment can be separately qualified on a compatible host; it does not block
this completed Apple Silicon M2. Update status, handoff, changelog and affected contracts.

## Amendment 002.2 — documentation implementation

The requested documentation work is a parallel application capability; M3.2 remains the next model/retrieval qualification task.

- [x] Stage 1: preserved existing applications; centralized desktop/mobile documentation navigation and contextual help; independent public/internal builds and existing-identity authorization on every internal asset.
- [x] Stage 2: substantive dashboards, categorized source content, full-text/API/component/table search, keyboard shortcuts, responsive light/dark design.
- [x] Stage 3: selectable architecture explorer with zoom/pan/fit/enlargement and SVG/PNG exports; actual ten-table explorer, FK detail and five schema relationship groups; classified gallery.
- [x] Stage 4: generated scoped OpenAPI; explicit loopback-only authenticated playground; seven public and twelve restricted A4 manuals with preview/download and source/hash metadata.
- [x] Stage 5: seven actual synthetic screenshot views, fifteen guided procedures, contextual application help, local checklists, Python/TypeScript/cURL examples including streaming, safe local feedback, permission-scoped real-model documentation assistance.
- [x] Stage 6 software: reproducible extraction/render/build/validation, version metadata, source/schema/link/asset drift checks, negative public exposure test, CI scope builds and browser checks, existing app regressions.
- [x] Dependency release blocker: both root advisories remediated with reviewed local backports, twelve attack/compatibility/integrity checks and clean installation; npm audit now reports zero findings. Docs builds use supported Node 24/React peers.
- [ ] Remote publication acceptance: no approved remote target/workflow has been executed. No remote deployment, publication or CI run is claimed.

Latest software evidence: 84 real PostgreSQL tests passed; 61 CPU passed/23 integration tests skipped without a test database; Ruff/format and strict mypy (18 application files) passed. Frontend lint/types/production build and documentation type checking passed. Original mock browser regressions: 4 passed; real local model browser acceptance: 1 passed. Live documentation browser checks verified search, diagram selection/enlargement, public/internal PDF counts, direct private asset denial, engineering identity, logout revocation, desktop/mobile navigation, real grounded assistance and local playground routing. Build and generated-artifact/security results are recorded in [the documentation report](AMENDMENT_002_2_REPORT.md).

Repository moved by the user to `onesa-ug/onesa-ai-platform`. Source, ignored private configuration, database volumes and the installed Qwen model were preserved. Obsolete checkout directory deleted on explicit request; native inference and gateways restarted with corrected paths. See updated handoff for commands and limitations.

Dependency remediation evidence and maintenance: [documentation dependencies](../security/DOCUMENTATION_DEPENDENCIES.md). The all-severity audit and backport security tests remain mandatory; no suppression or weakened gate is used.


## Frontend/backend split — 2026-10-09

- [x] Migrated existing applications using Git moves into `onesa-ai-platform-frontend`
  and `onesa-ai-platform-backend`; retained one project/history and preserved private data.
- [x] Independent digest-pinned multi-stage builds, runtime same-origin BFF/shared typed
  client, unbuffered ingress, bounded readiness/PDF parsing, deployment/monitoring templates,
  backup verification/retention and updated CI/docs/source generation.
- [x] Local acceptance: 87 PostgreSQL tests; 64 CPU passed/23 DB-dependent skipped;
  lint/format/strict types, frontend build, both healthy images, Caddy/GPU config,
  scoped docs/PDF/security builds, dependency audits, real model streaming/cancellation,
  both proxy paths and isolated restart/restore verification.
- [ ] Production release: target TLS/staging, hardware/load/security/worker confinement,
  monitored backup retention/alerts and legal/privacy decisions remain outstanding.

The local app remains on 3100 and docs on 3200/3201; native Ollama and credentials
are preserved. No schema/API contract change or remote release occurred. Review
[split report](PLATFORM_SPLIT_REPORT.md) before production acceptance. M3.2 semantic
embedding qualification remains the next model task after the requested split.

## Organization preparation — 2026-10-09

Prepared `onesa-ug/onesa-ai-platform` as an independent private GitHub repository.
Renamed local `master` to `main` as requested; preserved baseline commit `1ea8d54`,
the baseline branch, all staged renames and unstaged work. Created the empty online
repository and configured `origin`; no code was pushed or committed in this session.
The parent `onesa-ug` workspace remains without a `.git` directory. Portal and robot
have separate Git roots; robotics remains outside the platform application boundary.

Added CONTRIBUTING/SECURITY/GITHUB_SETUP, application environment examples, separate
build/deployment guides and an offline publication-hygiene CI gate. Existing CI now
runs on every push/PR with read-only contents permission; manual candidate packaging
also requires hygiene. New ignores cover private/generated/runtime content, but do
not untrack existing files. Publication is blocked by 119 generated document paths
already in history/index, including 92 internal paths; owner classification and an
explicit remediation decision are required. No credential-pattern matches were found
in publishable worktree/index/reachable history, including decoded PDF text; this is
not a proof that confidential prose or unsupported credential formats are absent.

Current local checks: frontend lint/types/production build passed in an isolated
copy with local Node 24; backend wheel build, Ruff/format, strict mypy (20 source
files), and pytest passed (65 passed, 30 database-dependent skipped). Root scripts
and operations Ruff/format passed. Remote CI, Docker images, browser and live database
integration were not re-run. Work remains on M3.2; no unrelated milestone was advanced.
See `docs/engineering/BUILD_AND_TEST.md`, `DEPLOYMENT.md`, and `GITHUB_SETUP.md`.

## Source publication and Vercel/Render target — 2026-10-09

The owner authorized pushes to main, removal of workspace readiness-report artifacts,
and Vercel frontends with Render backends. History was explicitly deprioritized.
Prepared fresh source-only main while retaining original Git metadata/staged work
and patch backups locally. Generated manuals, credentials, uploads, records and
model artifacts remain local and excluded from publication. This supersedes the
prior tracked-history blocker for the new publication history only.

Database integration: 94 passed, one optional skipped; frontend cloud changes are
under verification. Added Render app-only build context/database/health configuration
and Vercel build configuration with 150-second API duration and a 3 MiB upload budget.
Mock is explicitly labelled until a qualified remote inference endpoint is configured;
native Mac Ollama is not exposed to the Internet. Provider authentication, final
origins, target-host checks and organizational privacy decisions remain incomplete.
No production readiness or actual remote deployment is claimed from local checks.

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

## Publication follow-up — 2026-10-09

Fixed the documentation search race after session revocation: access-denied HTML is
never parsed as JSON, pending fetches are canceled on unmount and unavailability is
shown without unhandled promise errors. Added denied-response/malformed-index regression
coverage. Removed the obsolete original-history backup and Ruff caches after source
commits were verified on GitHub, as requested. The owner chose to leave provider
Actions secrets empty, so actual Vercel/Render deployment remains pending configuration.
Portal full GitHub verification passed; its deployment workflow safely failed for
missing provider configuration. No cloud deployment or production qualification claimed.
