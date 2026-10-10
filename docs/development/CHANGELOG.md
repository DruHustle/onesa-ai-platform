# Development changelog

## 2026-10-10 — Transaction-pooled runtime timeout

- Apply the five-second query limit inside each transaction, preserving bounded
  pooling and TLS without relying on a session startup option rejected by poolers.
- Read-only staging probes now use the actual application engine and report its
  timeout; regression coverage checks new transactions after commit and rollback.

## 2026-10-10 — Staging optional provider settings

- Preserve initialized staging data on retries; omit absent optional Render settings,
  retain unrelated settings and bound transient provider retries.
- Unconfigured model/embedding URLs default to empty instead of invented service hosts;
  Compose continues supplying its explicit internal service URLs. Hosted inference stays blocked.

## 2026-10-10 — Render startup regression

- Made Dockerfile CMD authoritative in AI configuration and added final-image startup,
  PORT, liveness, dependency failure and SIGTERM verification to CI.
- Added safe provider command classifications and staging revision readback.
- Local backend integration: 147 passed, four platform-dependent skips; hosted repair
  remains unverified. No push/deployment or inference-readiness claim.

## 2026-10-10 — Local semantic retrieval qualification

- Added optional private pinned Qwen3-Embedding-0.6B serving, 256/1024 normalized outputs,
  bearer/body/token/queue bounds, offline loading, weight verification and safe errors.
- Added fixed synthetic EN/DE evaluation and raw rankings; 256 passed declared thresholds
  with 45/48 top-1 versus 47/48 at 1024. Retained failures and dimension tradeoff.
- Explicit 256 requests and query-only instructions; HTTPS/key validation for production
  HTTP embedding services. Real pgvector isolation/reindex-failure/native grounded-chat
  acceptance passed; original live documents/configuration preserved. No deployment.


## 2026-10-10 — Account controls and typed feature workflows

- Added profile/password/session settings; password-confirmed bounded owner-scoped JSON
  export and atomic live account deletion, including document embeddings. External
  backups remain outside self-service deletion; oversized exports fail rather than truncate.
- Added extracted-document preview/reindex UI and strict runtime response models for
  knowledge, agents, trips and model discovery; feature pages use generated types.
- Serialized login/account locks, rechecked revoked tokens, fixed missing cancelled-run
  outcomes; verified cross-user isolation, derived-data deletion and malformed output denial.
- 112 PostgreSQL/backend passes, one Linux skip; frontend lint/types/build, 12 supported
  browser cases and public/internal docs builds passed. Conservative API review and
  production release gates remain unresolved. No new publication/deployment occurred.


## 2026-10-09 — Preserved frontend/backend split

- Moved the existing Next.js/docs apps, FastAPI/migrations and training/evaluation into
  separately buildable frontend/backend directories within the original Git history.
- Added runtime same-origin streaming BFF, generated typed API client, independent
  pinned Docker contexts, unbuffered Caddy routing, resource limits and env templates.
- Bounded PDF parsing and async readiness dependency probes; added availability metrics,
  private scrape/alert templates, backup integrity/retention and restart/rollback tools.
- Updated Make, CI, manual image packaging, classified documentation paths and runbooks.
  Verified database content preservation, existing regressions and real model stop/retry.
- Kept schema, OpenAPI, private credentials, native model/data and sibling projects intact.
  Local migration is verified; external production acceptance remains explicitly pending.

## 2026-10-09 — Documentation dependency blocker resolved

- Backported depth/AST guards for braces and bounded numeric formatting for sprintf-js into explicit private local forks; retained upstream licenses, reviewable diffs and source/archive integrity records.
- Added twelve mandatory security/consumer compatibility tests covering hostile nesting/precision, direct ASTs/cycles, real file watching, micromatch, argparse and Markdown rendering; clean install and npm audit now show zero findings.
- Enforced all-severity audit and installed backport integrity in CI/release gates. Qualified docs with repo-local official SHA-verified Node 24 and mutually supported React 18 peers; existing application React and data contracts are unchanged.
- Extended live Swagger testing to actual Try it out/Execute and response rendering, rebuilt isolated portals and regenerated classified artifacts. No remote publishing or model download occurred.


## 2026-10-09 — Amendment 002.2 documentation ecosystem

- Added independent public/internal Docusaurus builds, existing-identity gateway and retrieval-time engineering authorization; explicit public source/asset allowlists and negative exposure checks.
- Integrated desktop/mobile Documentation, conditional Engineering links and contextual help without changing existing application contracts or migrations.
- Added scoped search, interactive architecture/database/API exploration, local authenticated playground, seven public/twelve internal manuals, twenty-eight SVG/PNG diagrams, seven actual synthetic screenshot views and fifteen guided procedures.
- Added existing-model documentation assistance, validated integration/streaming examples, deployment checklists, local feedback, classified media/download libraries, release metadata and CI build/security/browser checks.
- Verified 84 PostgreSQL tests, 61 CPU tests, frontend/docs types/builds, four original mock and one real browser regression plus live documentation authorization/navigation/assistant checks. Recorded initial failures and unresolved upstream documentation audit findings; publication remains blocked.
- Preserved source/private configuration/installed model and database volumes during the user-directed repository move; deleted the explicitly authorized old directory and restarted managed local services at the new path.


## 2026-10-09 — Milestone 2: native Apple Silicon real inference

- Installed checksum-verified native Ollama and the explicitly requested Qwen3 4B Q4_K_M;
  loopback only, context 8192, private repo-local runtime/model storage.
- Added shared Ollama/vLLM streaming, request-owned usage/timing and safe model metadata;
  preserved public alias, authentication, schema, conversations and all applications.
- Fixed observed web SSE compression buffering; verified real browser/API cancellation,
  context/history, sources, model tools/travel and managed-daemon failure/recovery.
- Stored 13-case evaluation (12 strict passes, exact-format arithmetic failure), one
  native tool-schema probe and measured concurrency 1/2 benchmark reports with limits.
- Verified 62 PostgreSQL tests, 41 CPU tests, frontend lint/type/build, main Docker startup,
  four original mock browser tests and one explicit real-model browser test.
- Updated setup/contracts/architecture/status/handoff. Apple Silicon M2 is complete;
  M3 semantic embeddings are next. NVIDIA, alternative models, training and production
  qualification remain unverified. See MILESTONE_2_REPORT.md.

## 2026-10-09 — Amendment 001: European and international alignment

- Applied European-based general-purpose positioning, retained optional African/regional
  adaptation, and recorded ADR 0003 without changing the milestone order.
- Updated product/architecture/model/training/privacy/deployment documentation and added
  market/use-case/innovation/sovereignty/customization references with explicit evidence limits.
- Removed the training language enum; added extensible language/domain labels and logical
  candidate-profile/licensing/provenance/evaluation metadata with report/config hashes.
- Added unchanged-base paired regression reporting and English/German navigation/sign-in
  catalogs, configuration and persisted preference; other workspace copy remains English.
- Preserved existing public APIs, database schema, model alias and application implementation.
- Verified 47 PostgreSQL tests, 27 CPU tests, frontend lint/type/build, Docker startup,
  4 Chromium tests and unchanged OpenAPI. Evidence is recorded in SESSION_HANDOFF.md. Rechecked M2.3 hardware: NVIDIA/CUDA execution is pending.

## 2026-10-09 — Complete local platform and continuation handoff

- Delivered authenticated PostgreSQL-backed chat, migrations, session/CSRF protection,
  per-user isolation, SSE generation leases/cancellation and responsive Next.js UI.
- Added configurable vLLM adapter, pinned model/GPU images, diagnostics and LoRA override.
- Added TXT/PDF knowledge ingestion, versioned pgvector search and saved chat sources;
  lexical baseline and real embedding adapter remain clearly distinguished.
- Added bounded registered tools with explicit grants, shared-model planning and run
  history; structured saved/revisable travel with explicit provider availability.
- Added provenance-aware dataset preparation, split verification, training dry-run,
  gated local LoRA/QLoRA runner, evaluation and immutable candidate registry.
- Added safe logs/body bounds/protected metrics, non-root containers, TLS and restricted
  production database templates, backup/restore/load scripts and full CI configuration.
- Reconciled API/OpenAPI/schema/ERD/design/deployment/security/training/operations docs
  with actual implementation; retained engineering attachment as reference material.
- Verified 44 real-PostgreSQL tests, host lint/type/build, 3 real Chromium flows,
  Node 24.21.0 container startup, backup restoration and zero dependency audit findings.
- Started local platform on port 3100 with private generated secrets, preserving the
  earlier verification database. M2 NVIDIA hardware acceptance is the next incomplete
  task; real-model/provider/training/production qualification remains explicit.


## 2026-10-09 — Milestone 0 foundation

- Initialized the empty project without renaming the user's repository.
- Installed the supplied continuation prompt in AGENTS.md and a dedicated document.
- Preserved engineering input as reference and captured screenshots in architecture,
  PRD, roadmap, design decisions, API contracts and proposed PostgreSQL schema/ERD.
- Implemented FastAPI configuration/application factory, server-generated request
  UUIDs, health and bounded readiness with sanitized errors.
- Added a model-client protocol and labelled deterministic cancellable mock stream.
- Added dependency pins/lock, Make commands, Ruff, mypy, Pytest and CI configuration.
- Generated OpenAPI and documented local operation and verification limitations.
- Verified install/editable build, dependency checks, lint/format/type checks and
  11 passing tests. Fixed timeout-test lint and OpenAPI output-directory handling.
- Recorded current milestone M1 with PostgreSQL models/migrations as the first task.

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

GitHub plan compatibility: deployment workflows consume repository-level Actions
secrets without paid deployment-environment features.
AI documentation browser builds now generate diagrams/manuals before testing actual
assets; the standalone documentation and TLS/operations jobs passed remotely.

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

### 2026-10-10 — deployment review

- Expanded offline secret gates for Resend and Neon; repository/history scans pass.
- Added explicit missing Vercel secret diagnostics without exposing values.
- Verified backend/frontend/browser checks and regenerated stale ignored documentation.
- Hosted API 503s and release/security/compatibility gates remain unresolved.


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


## Documentation favicon correction — 2026-10-10

Added the owner-approved Onesa orbit ICO as an independent docs static asset and
configured Docusaurus to emit its favicon link. The publication workflow now
checks the emitted index and exact bundled icon before upload. No API contracts,
internal source policy or application release guards changed. Hosted verification
will be recorded after the deployment completes; company branding is already
fixed in source but its production deployment remains independently gated.

## Public docs Git deployment safeguard (2026-10-10)

Added `git.deploymentEnabled: false` in the docs app `vercel.json`. The public
documentation hosting workflow copies this configuration into its isolated Vercel
deployment directory. Automatic Git deployments are disabled; the existing checked
GitHub Actions prebuilt deployment remains available. This does not prevent an
authorized administrator from connecting Git. JSON validation and diff checks passed;
no provider settings, deployment or release approval were changed.

## AI Render startup command correction (2026-10-10)

The reported exit 127 treats the quoted Uvicorn command as one executable.
Replaced nested `sh -c` overrides with `sh /app/start.sh` in both Render
blueprints and the hosting repair helper. The image includes this startup script
and uses it as CMD; it expands PORT (default 8000) and execs python -m uvicorn
with existing concurrency, logging and graceful-shutdown settings. Seven hosting
regressions, shell syntax, default/custom-port argv and diff checks passed.
The local Docker image builds successfully. Hosted settings and deployment have
not been changed; production remains gated.

## Shared Onesa interface identity (2026-10-10)

Public/internal documentation and the AI application now use the company homepage
navy (#081b32), cyan (#53dbe8), blue (#2366d1), neutral surfaces and Arial typography.
Docs retain light/dark reading modes and use a navy public hero; application layout,
security states, retrieval and API contracts are unchanged. Portal lint, platform
lint/typecheck, docs typecheck and the public docs build passed. Local locked
platform dependencies were restored after a missing axe test dependency was found.
These are local source changes, not a hosted release or legal/operations approval.

Final theme acceptance: desktop (1440px) and mobile (390px) browser checks
passed for docs and the platform signed-out interface, including horizontal
overflow and keyboard reachability of the docs skip link. The signed-out backend
remains honestly unavailable in the isolated preview; no authentication bypass
was used. The docs skip-link and hero spacing overflow were corrected. Robot
static preview checks passed at the same widths. Authenticated application styling
was updated in source but not verified against a live signed-in session.

Pre-push review: Docker health check now reads PORT consistently with startup.
Eight provider/startup regression tests and the rebuilt image pass. History hygiene
scans report zero findings in all three repositories. The generated Next.js route
declaration was restored to its production form; generated framework agent guidance
is included. Provider production readiness remains independent of a source push.

## 2026-10-10 — AI configuration inventory

Added AI-only, read-only provider inventory for actual backend origin, provider identity, linked environment groups, overrides, worker inventory, Vercel domain assignment and redacted configuration validity. No provider configuration or resource provisioning is performed by this workflow. Disclosure and scope tests pass locally.

Prepared complete source-backed AI configuration matrix, verified origin/proxy values, temporary free Render PostgreSQL staging proposal and standalone loopback-only vLLM host proposal. Corrected production example to retain semantic embedding candidate; no private environment files or other projects modified. Local isolated PostgreSQL147passed4skipped; hosted API503 remains open.

## 2026-10-10 — Instruction documentation cleanup

Removed completed GitHub setup instructions and duplicate status/session-handoff
logs. Consolidated contribution, security, repository governance and agent policies
in one root AGENTS.md per independent repository. Preserved unfinished work in
existing roadmap/release documentation, updated links and documentation tooling.

## 2026-10-10 — Owner-created AI staging database

Recorded the owner-reported isolated Neon resource `onesa-ai-platform-backend-db-staging`, superseding the Render staging database creation request. Updated staging template and private ignored staging profile without copying the disclosed owner password. Preserved local/production/Portal configuration. Hosted ownership/schema/TLS/roles and migrations remain unverified until fresh private credentials are available.

### Isolated AI staging configuration

Added a scope-checked staging diagnostic and Preview-only configuration/deployment path.
CI and publication hygiene must pass on the current staging SHA before deployment.
Recorded actual PostgreSQL 18.6, empty staging schema and privileged-role blocker;
client TLS is checked separately from the Neon pooler internal connection.
Production branch and provider settings remain unchanged.

Prepared staging-only controlled migrations, restricted runtime-role provisioning,
exact-origin configuration and real hosted security/persistence/restart tests.
Bound the existing GitHub Staging environment and restricted its deployment branch.
Corrected Vercel tracing separately from Docker standalone packaging.
Hosted results remain unverified until the new revision passes CI and deployment.
