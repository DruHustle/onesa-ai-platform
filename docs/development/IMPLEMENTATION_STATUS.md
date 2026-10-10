# Implementation status

Current release focus (2026-10-10 v1.1): local remediation and release closure, independently NO-GO. The latest appended v1.1 results supersede historical totals/provider claims below. Do not push/deploy/rotate credentials/change DNS without the corresponding scoped authorization. Protected provider503 diagnosis/staging, operations, assurance/accessibility and legal/scope acceptance remain open; private release-closure ledger assigns every original finding. Prior milestone notes and user changes are preserved as history.

Updated: 2026-10-10 (Europe/Berlin).
Current milestone: **M5 — External travel-provider acceptance**.
First incomplete ordered task: **M5 provider acceptance** with approved real integrations.
M3.2 is locally qualified on the stated synthetic EN/DE scope; production embedding
hosting/reindex remains part of M7 target acceptance. Preserve active lexical data.

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
- [x] M3.2 local: qualified Qwen3-Embedding-0.6B at 256 dimensions on fixed synthetic
  EN/DE retrieval, real owned pgvector isolation, safe reindex and native grounded chat.
  1024 comparison and failures retained; production/customer-language acceptance is separate.
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


## Final cross-project audit — 2026-10-09

This section supersedes earlier current-state readiness claims. Existing FastAPI / Next.js AI apps preserved; main baseline 6e98c6d4cb07, local uncommitted candidate only. No new push/deployment/publication. Local 105 backend tests passed, one Linux-only skipped and separately checked in Linux; 12 supported browser passes plus one real native model acceptance; frontend lint/type/production build passed. Firefox startup, conservative contract compatibility review, complete ASVS/a11y and hosted operations/legal acceptance remain incomplete. Production release is **NO-GO**, distinct from local passing checks.

Added exact-origin controls, nonce CSP, independent provider examples, standard generated clients/compatibility gate, strict release fingerprint/approval tooling, synthetic restore and current container scanning. Production mock/local inference endpoints now fail closed; bounded SSE runtime parser and non-forcing streaming scroll; core readiness separates model degradation; Python OS HIGH findings still block release. M3.2 semantic embedding remains incomplete.

Restricted release reports and evidence are ignored under docs/internal/release-audit. Read RELEASE_DECISION, RELEASE_BLOCKERS and VERCEL_RENDER_RUNBOOK before promotion. `python3 scripts/release/qualify.py decision` returns NO-GO. Actual provider credentials/origins/storage/inference/monitoring and human legal/content approvals remain required.

Current REST ownership verification: repository is private under DruHustle (User); onesa-ug remote redirects. Intended organization ownership is unverified and release-blocking. No ownership/remote/visibility changed.


## Application feature continuation — 2026-10-10 (current)

Implemented account settings (display name, password rotation, active sessions,
password-confirmed revoke-other-sessions), bounded consistent private JSON export and
explicit account deletion. Deletion rejects active runs and atomically cascades live
owned data including document chunks/vectors; other users and external backups are
not changed. Export scope and limits are explicit, with 413 instead of silent truncation.
Added extracted-document preview and reindex controls. Knowledge, agents, travel and
model endpoints now use strict runtime response models and generated browser types.
A malformed persisted tool outcome fails safely; disappearing cancelled runs do not
return an uninitialized result. Login/account mutation lock ordering protects password
changes and prevents revoked sessions from committing later profile changes.

Latest evidence: 112 backend tests passed, one Linux-only skip, one upstream TestClient
warning; Ruff/format/mypy passed. Frontend lint/types/production build passed. Twelve
Chromium/WebKit functional cases passed, including download/deletion and five-width
Settings axe/overflow checks. Public/internal documentation builds/assets validation
passed. Generated-client drift passes. Conservative baseline compatibility reports 18
response-schema review findings; the baseline was not reset or gate weakened.
Evidence commands/logs: ignored data/audit-20261009/evidence/features-*.{json,log}.

Next ordered model task remains M3.2: qualify an approved real semantic embedding
service; lexical search remains labelled. Email verification/recovery, AI MFA/SSO,
operator-assisted oversized export and external retention still need design/integration
and acceptance. Travel providers, training experiments and full production qualification
remain incomplete. The owner reports Render setup complete; deployed behavior was not
verified in this continuation. No new commit, push or deployment occurred. Release is
still NO-GO for outstanding security/image/API/host/operations/legal/ownership findings.


## Semantic retrieval continuation — 2026-10-10 (supersedes M3.2 pending)

Qwen3-Embedding-0.6B local qualification completed at the pinned revision and 256-dimensional
schema. Fixed synthetic EN/DE benchmark: 45/48 top-1 and 47/48 recall@3; 1024 gives 47/48
and 47/48. Three real pgvector/embedding/native-chat integration cases passed. The separate
loopback runtime is bearer-protected and bounded; startup checksum/offline loading,
no-store responses and safe upstream failure are verified. Final optional runtime audit
has zero known findings after packaging-tool remediation. Core API dependencies unchanged.

Read SEMANTIC_RETRIEVAL_QUALIFICATION.md and embedding_service/README.md. Weights/runtime/
keys remain ignored under data; the active .env, port3100, existing user databases,
Ollama chat weights and document indexes are preserved. No cloud service, push, paid
hosting or production reindex occurred. Production release remains NO-GO; target-host
embedding security/capacity, approved corpora/languages and controlled reindex/rollback
remain necessary. Next ordered incomplete task is M5 authorized live travel providers;
M6 training and M7 target operations remain separately gated. Historical earlier
M3.2-pending notes are superseded by this narrowly scoped local qualification.


Final semantic continuation checks: 116 backend tests passed with four explicit
optional/platform skips; three opt-in real embedding/pgvector/native-chat cases
passed separately. Generated-client drift and source/history hygiene pass. The exact
50-distribution macOS runtime graph is hash-locked and pip's ignore-installed dry-run
validated it without modifying the tested runtime. Optional runtime vulnerability
findings: zero. The only new download was the approved Qwen embedding model plus its
separate runtime packages. Owned temporary test services are stopped after acceptance.

Real semantic UI acceptance: Chromium/WebKit 2 passed; native answer and source
persistence verified after reopening the conversation. Frontend lint/types and
public/internal documentation/assets validation passed. Synthetic screenshots and
private raw evidence remain ignored under data/embeddings and data/audit-20261009.


## Domain configuration — 2026-10-10

Owner selected `platform.onesa.eu` for the AI chat frontend. The production example
now uses this exact `ONESA_PUBLIC_ORIGIN`; Vercel `ONESA_API_URL` remains the actual
Render API URL. Company and private administration use `onesa.eu` and
`portal.onesa.eu` in the independent portal repository. Future robot host is
`robot.onesa.eu`; the robot application is not implemented. Provider assignments,
DNS/TLS qualification and production delivery remain pending; populated `.env`,
models, indexes, cookies and API contracts were not changed. No push/deploy here.


## Private environment files — 2026-10-10

Created root `.env.local` and `.env.prod`, both ignored by Git and mode 0600.
Local variables preserve the existing `.env` values and add documented defaults.
Production settings use `platform.onesa.eu`, Secure cookies and a separately
generated metrics token; provider DB/inference credentials remain placeholders.
Lexical retrieval remains the production baseline pending hosted embedding
qualification. Files parse with the supported Node runtime. Select the files
explicitly; existing startup defaults and running services were not changed.
No API contracts, models, indexes, architecture or deployment changed.

## Cross-project review — 2026-10-10

Added Resend/Neon credential detection to source/history checks and explicit missing
Vercel secret names to deployment diagnostics; no credential values are logged.
Current isolated verification: backend Ruff/format/mypy and 116 tests pass, four
skipped (Linux-only/opt-in real provider tests). Frontend lint/types/production build
and 14 Chromium/WebKit functional/accessibility cases pass; four opt-in real-model
browser cases skipped in this explicitly labelled mock regression run. Previous real
semantic/model qualification is separate evidence. Generated API client drift passes.
Regenerated ignored documentation after detecting source drift; full asset/source
validation passes in the review copy. All three repository source/history scans pass.

18 conservative response-contract compatibility findings remain. The Python audit
runtime has unresolved vendor HIGH advisories; release security gates remain intact.
Hosted staging, operations, manual accessibility and legal/content approval remain
blocked or unverified. Release qualification remains NO-GO.

GitHub main remains 6e98c6d with passing checks, and Vercel reports the older frontend
deployment successful. Anonymous live /api/v1/auth/me and /api/v1/models return 503.
GitHub lacks VERCEL_PROJECT_ID and a passing exact-commit release qualification.
Render/Vercel integrations and authenticated local CLI access are unavailable.
No commit, push or production deployment occurred. Preserve private configuration,
models, indexes and user data. Evidence: ignored data/audit-20261009/evidence/review-*.

## Diagnostic current-state audit — 2026-10-10

This dated diagnostic supersedes historical readiness/coverage statements where different. Application code/configuration/migrations/dependencies and robot were unchanged. Both releases remain independently NO-GO. Current findings, exact dirty-snapshot identity, test totals/limitations, hosted503s and next steps are in docs/internal/release-audit/CURRENT_STATE_AUDIT.md (path relative to repository root). The protected EVIDENCE_INDEX.json records executed commands; NEXT_STEP_CODEX_PROMPT.md contains a bounded continuation. No public deploy/push, DNS, credential rotation, email or real-user mutation occurred. Source tests used disposable synthetic databases; real-model checks used only approved existing local resources.

AI:116backend pass/4skip; separate3real-semantic tests,2native and2semantic browser cases,14mock regression cases,5SSE and13docs-security tests pass; Linux PDF probe passes. Fresh API image44HIGH,18contract reviews, hosted503/inference/ops/legal and recovery/invitation gaps remain. New320px sign-in overflow is measured; no code fix was made during audit.

Generated documentation validation applies to the pre-addendum snapshot; release documentation must be regenerated after future implementation/status changes. Prior successful storage/deployment/model statements are explicitly dated historical evidence rather than current hosted qualification.


## Remediation and release closure — 2026-10-10 v1.1

This dated continuation supersedes earlier current-result statements, preserving their historical evidence. Targeted upload/security/contract/UI/operational changes are implemented locally; current application builds and synthetic checks are recorded in the restricted release-closure ledger. No remote mutation, commit, push, email, DNS or public-release approval occurred. Company Portal and AI Platform remain independently **NO-GO** for hosted503s, credential containment, operations/legal and remaining security/manual acceptance. Do not represent the older deployed revision as this dirty candidate.

Portal preserves10MiB private-file capability through bounded transport; fresh MFA/private provenance controls remain intact and two intentional compatibility changes await client/version approval. AI preserves5MiB ingestion and existing real local models; adds explicit invitation gating, one-use recovery/outbox worker, shared DB admission quotas and honest bootstrap errors. AI runtime uses pinned Python3.11.17 Alpine and build-only pinned uv; native Linux PDF restrictions remain enforced. Compatibility18→0 is a proved schema refinement, not baseline reset. Private STAGING_OPERATIONS_DELTA.md and SECURITY_ACCEPTANCE.md specify hosted/manual/policy gaps. Exact refreshed results/source hashes are in RELEASE_CLOSURE.md/EVIDENCE_INDEX.json, not old milestone totals.

Next executable bounded task: qualify native AMD64 PDF denial and prepared candidate staging after owner-approved target/access, then diagnose503 from actual Vercel/Render logs; separately implement the reviewed password-blocklist/session-assurance policy. M5 live travel, training, paid access, hosted inference/capacity and human multilingual quality are still unqualified; no speculative provider integration introduced. Preserve original ordered milestone requirements and all prior dirty work. Robot unchanged.

## GitHub review and deployment follow-up — 2026-10-10

The owner has now authorized reviewing, committing and pushing to `main`, and
monitoring deployments. Production qualification remains mandatory; this permission
does not establish staging, operations or content/legal acceptance. Company record
files awaiting publication approval remain local and are excluded from Git and
documentation artifacts. The manual `Inspect hosting configuration` workflow uses
existing provider secrets for read-only service, configuration and deployment
checks; it emits only required-variable presence and allowlisted status fields.
Paired releases now wait for the backend (and portal worker) before promoting the
frontend. Remote CI and provider results will be recorded after the push; they are
not implied by the earlier local test results.

CI follow-up: clean GitHub runners exposed root-owned Trivy report permissions;
image scans now use an exported image archive and the runner UID, retaining all
vulnerability/secret checks. The platform development dependency declaration now
includes pinned pip-audit, with the lock regenerated from source. Hosting readback
found missing provider configuration and failed native Render deployments. The
manual repair workflow only updates existing matched-repository Docker layout,
health paths, disables native auto-deploy and adds absent approved public origins
or portal S3 aliases. It never deploys, migrates data, copies/rotates credentials,
changes plans, creates resources or marks qualification gates as passed.

Browser CI repairs: portal blob download anchors are attached to the document and
object URLs are retained until WebKit starts downloading; the exact 10 MiB private
CV upload/download and SHA-256 check passed native Linux WebKit. Documentation
test grants accept only the old fixed or new randomized synthetic example.com
fixtures. Render AI configuration now rejects implicit development/test defaults
and suppresses input values in configuration validation errors. Fresh platform
backend checks passed (146 passed, 4 conditional skips); remote full checks remain
in progress. No production qualification record was fabricated.

Staging infrastructure follow-up (owner direction 2026-10-10): reuse an existing
qualified AI-specific Render database if found; otherwise prepare separate staging
and production PostgreSQL proposals without provisioning or selecting a paid plan.
The diagnostic workflow now inventories AI-named database candidates and the actual
backend region without retrieving connection credentials. Hosted vLLM and semantic
embedding infrastructure remain blocked pending a costed, approved host; preserve
native Ollama and local data. Database/core readiness now requires an actual current
schema even in development; `/health` stays process liveness, while `/core-ready`
may remain available during an inference outage only with a healthy database.


## Dedicated hosted AI preparation — 2026-10-10

The owner requires a dedicated AI Render PostgreSQL database and separately approved
European GPU/vLLM host, with staging first and no unapproved paid provisioning.
Read-only inventory found the backend in Frankfurt and no AI-named database
candidate; ownership/schema verification of differently named resources is not
implied. HOSTED_AI_PROPOSAL.md prepares isolated PostgreSQL 16/vector-256 proposals,
scoped roles/TLS/pooling/restoration and one costed Paris L4 GPU/CPU-embedding plan.
Separate staging/production JSON proposals are not applied Blueprints or live URLs.
HOSTED_AI_CONFIGURATION.md inventories all 47 actual Settings names and process
scopes without secret values. Expanded diagnostics report only presence booleans.

Alembic now reads ONESA_DATABASE_URL directly instead of requiring complete hosted
application/model settings. Full application validation remains strict. Fresh
Ruff/format/mypy passed; 147 backend tests passed, four conditional skips and one
upstream TestClient deprecation warning. A new isolated PostgreSQL regression proves
migration independence while invalid production inference configuration is refused.
GitHub verification for the preceding readiness revision completed successfully
across all eight jobs. The proposed migration/docs revision still needs fresh CI.
Hosted model, semantic embedding Linux lock/capacity, actual dedicated database,
original-file archive requirements, real delivery worker, credential rotation and
staging/operations/legal qualification remain open. Production remains NO-GO.


Expanded hosting readback: the authorized same-owner Render inventory returned zero
PostgreSQL resources without page truncation, and zero of all 47 AI application
settings were explicitly nonempty. Optional defaults do not qualify hosted services.
The proposal and full names-only matrix now record these actual observations. The
new diagnostic required Ruff formatting on the clean CI runner; formatting repaired
and the full repository make check is rerun before push. No runtime gate weakened.


## Owner free-only staging direction — 2026-10-10

The owner rejected paid database/GPU budgets and will establish staging. Added
staging.env.example with real application variable names, blank credential/endpoint
fields and isolated origins; existing populated env files remain untouched.
FREE_STAGING_SETUP.md documents ongoing free Neon/Render/Netlify/Resend/conditional
Zoho options, exact product setup/migration commands, limitations and owner steps.
Paid proposals/Blueprints are historical and explicitly not to be applied. No paid
resource, account subscription, DNS cutover, live migration or model switch occurred.
Vercel Hobby commercial restrictions, expiring Render free database, missing free
workers, EU model/privacy/capacity and restored backup limits remain material.
Free inference candidates are unconfigured, not a deployed real-model endpoint.
Production remains NO-GO; preserve independent products and all original data.


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
