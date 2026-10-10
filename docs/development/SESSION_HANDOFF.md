# Session handoff

Current release focus (2026-10-10 v1.1): local remediation and release closure, independently NO-GO. The latest appended v1.1 results supersede historical totals/provider claims below. Do not push/deploy/rotate credentials/change DNS without the corresponding scoped authorization. Protected provider503 diagnosis/staging, operations, assurance/accessibility and legal/scope acceptance remain open; private release-closure ledger assigns every original finding. Prior milestone notes and user changes are preserved as history.

Date: 2026-10-10 (Europe/Berlin). Repository: `onesa-ai-platform`.
Current milestone M5; first incomplete ordered task **M5: authorized live travel providers**.
M3.2 local semantic retrieval is qualified on the documented synthetic EN/DE scope.
The user's M2 Apple Silicon request explicitly authorized native Ollama and only the
specified Qwen3 4B model after hardware checks. It supersedes earlier no-download/M2
NVIDIA-only directions. Source requests are preserved in MILESTONE_2_REQUEST.md.

## Active local state

- UI: **http://localhost:3100**, Compose project `onesa-platform`, API healthy.
- Private ignored `.env`: backend ollama; model `qwen3:4b-instruct-2507-q4_K_M`;
  base URL `http://host.docker.internal:11434/v1`; context 8192; Q4_K_M;
  revision digest `0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0`.
  Preserve generated secrets; never print the file or use `down -v` for routine work.
- Apple M3 MacBook Air, 24 GiB unified memory, macOS 27.0.1 arm64. Native Ollama
  0.40.2 lives in ignored `data/runtime/ollama`; official release checksum verified.
  Own daemon binds **127.0.0.1:11434**, models live in ignored `data/models/ollama`.
  Service is running; `scripts/local/ollama_service.py` start/status/stop/restart
  manages only this repository's daemon and refuses another listener/PID.
- Context/server settings: 8192, one loaded model, one generation worker, cloud disabled.
  No Docker Ollama, system-wide package install or alternative-model download occurred.
- Database schema remains `608f3f79f76e`; no M2 migration/dependency changes.
- All files remain local/reviewable; no commit, push, public deployment or training.

## Working architecture

FastAPI/PostgreSQL/pgvector with hashed sessions, CSRF/Origin and owner isolation;
Next.js same-origin proxy; shared OpenAI-compatible Ollama/vLLM client plus labelled
mock. Chat, knowledge, agents and travel share one configured model. No silent fallback.
Next.js `compress:false` fixes actual SSE buffering: deltas reach the browser before
completion, and disconnect aborts upstream without saving partial assistant history.
Safe model metadata and measured usage/timing persist additively; missing usage is null.
No URLs, credentials or raw errors appear in public model/error payloads or metrics.

Knowledge remains a lexical 256-dimensional baseline, despite successful real-model RAG.
Qualifying semantic embeddings is the next task; maintain ownership and index-version
boundaries. Tools have explicit grants and bounded local effects. Travel contains model
itineraries, no live prices/bookings/providers. Phase B has preparation/registry machinery
but no trained weights or promotion. European/international positioning is unchanged.

## Acceptance and reproducibility

`make check`: 41 passed, 21 skipped; Ruff/format/mypy passed.
`make integration`: 62 passed using the isolated `_test` PostgreSQL database.
Frontend lint/types/production build and main Docker rebuild passed. Browser and
real workflow evidence: [MILESTONE_2_REPORT](MILESTONE_2_REPORT.md).
One upstream HTTPX/TestClient deprecation warning remains. Earlier dependency audits
reported zero findings; dependencies are unchanged. Remote CI has not executed.

Stored synthetic raw reports: `docs/models/baselines/` contains 13-case evaluation,
concurrency 1/2 measurements, cold direct call and authenticated platform acceptance.
Ignored `data/evaluation` holds original reports; screenshots in `data/screenshots`.
Evaluation: 12/13 strict checks; arithmetic exact-format failure retained, human review
required. Native function-call schema probe passed without executing tools. Token rate
uses full request wall time; model allocation is not peak unified memory. HTTP closure
is verified; exact GPU-compute cessation is not. No broad language/safety claims.

Repeat checks with `make check`, `make integration`, `make frontend-check`, `make openapi`.
The isolated `onesa-platform-test-db` is stopped with data preserved after acceptance;
start it before integration checks. The isolated mock `onesa-platform-m2-regression`
and older verification stacks are also stopped with their data preserved. Main app
and native real-model service remain running for use.

For real browser checks: from onesa-ai-platform-frontend/apps/chat, set ONESA_REAL_INFERENCE=1 and
ONESA_BROWSER_URL=http://localhost:3100, then run `npm run test:e2e -- tests/real.spec.ts`.
Original chat.spec.ts expects mock; use a separate mock project/port instead of changing
this real runtime. No unscheduled model downloads or expensive training are authorized.
NVIDIA/vLLM, semantic embeddings, Qwen3.5 comparisons, provider integrations and production
TLS/security/load/retention qualification remain explicit unverified work.

## Amendment 002.2 handoff (supersedes earlier dependency/state statements)

Current checkout: `/Users/andrewgotora/Software Development/GitHub/onesa-ug/onesa-ai-platform`. The explicitly authorized old directory was deleted after preservation checks. Main real-inference app remains http://localhost:3100; public docs http://localhost:3200; internal docs http://localhost:3201. Internal access uses existing Onesa sessions and the private engineering-user-ID allowlist. Only the synthetic documentation demonstration account was added for local verification; ordinary accounts remain denied. Never print ignored demo credentials or .env.

`make up-docs` uses the optional docs Compose override and preserves scope-specific read-only retrieval mounts. `ONESA_DOCS_API_URL=http://localhost:3100 make docs-serve` enables explicitly configured development playground execution; leaving it unset keeps schema exploration read-only. Gateways enforce internal identity for all HTML/JS/CSS/images/PDFs/indexes/manifests. Stop/start uses strictly verified repository scripts and the observed macOS interpreter; native model storage remains in the moved repository.

Generation: `npm --prefix onesa-ai-platform-frontend/apps/docs ci`; `make docs-assets docs-public docs-internal docs-validate`; `make docs-check`; `.venv/bin/python scripts/docs/validate.py --negative-test`; `make docs-browser`. Screenshot refresh: `make docs-screenshots`, using the actual local application and synthetic account. Shared Markdown sources are maintained once; staging/build outputs are ignored. Reviewable exports reside in docs/generated/public and docs/generated/internal. Internal exports must never be served directly by an unrestricted static host.

Latest results: 84 PostgreSQL tests passed; 61 CPU passed/23 skipped; Ruff/format/mypy 18 application files; frontend lint/types/build; documentation types and both scope builds; four original mock and one real-model browser test; live docs authorization/search/navigation/PDF/assistant/playground checks passed. The upstream TestClient warning remains. CI workflows are configured but have not run remotely. The earlier 33 documentation dependency findings were resolved with explicit local security backports; current npm audit reports zero findings. Twelve installed-source/integrity, attack-input and real consumer compatibility tests pass and are required by `make docs-release-check`. Docs now use supported Node 24 and React 18 peers; the application React version is unchanged. Local release checks pass, with no remote publication claimed.

An interrupted isolated mock startup initially caused four connection-refused browser failures; recovering that stack and rerunning produced four passes. Initial vague real agent planning failed safe validation during screenshot capture; the explicit statistics task succeeded. The documentation generator's initial lazy-route lookup was corrected to validate examples with actual request models. These failures do not change the measured M2 model quality limitations.

Current model milestone remains M3.2: qualify an approved real semantic embedding service while preserving the 256-dimensional contract and owner isolation. Existing documentation assistance uses lexical retrieval and real Ollama generation; it does not qualify semantic embeddings. NVIDIA execution, new model downloads, training, live travel providers, production security/load and remote publication remain outstanding. Next docs release task is to review an explicitly authorized publication target and public exports; continue monitoring official fixes for the maintained local backports. No remote tracking, SDK proliferation or automatic issue submission is introduced.


## Dependency blocker resolution

See [dependency security](../security/DOCUMENTATION_DEPENDENCIES.md). Patched source packages, precise diffs and provenance live in packages/security; portable local tarballs are under onesa-ai-platform-frontend/apps/docs/vendor. Do not remove these artifacts while the lockfile references them. Repacking changed sources requires a new local version and lock update to avoid cached archives. Original third-party licenses are preserved.

Optional official SHA-verified Node 24.21.0 is installed in ignored data/runtime/node24. Make prefers it; direct commands need its bin directory on PATH. The system Node executable was not replaced. Twelve security/compatibility checks pass after clean installation; both scoped builds and live Swagger execution/response rendering are verified with the final supported docs dependency combination. Audit and release checks pass with no ignored advisory. No models, DB migrations, app contracts, authentication, training or remote deployment changed during this remediation.


## Frontend/backend split handoff — 2026-10-09 (current paths)

The existing working sources now live under `onesa-ai-platform-frontend/apps/chat`,
`onesa-ai-platform-frontend/apps/docs` and `onesa-ai-platform-backend`. Training and
evaluation tools are within the backend; root docs/scripts/data/security forks remain.
All earlier commands in this document were updated to these paths. Root Make still
works; frontend npm scripts and backend Make/Docker entrypoints support independent
builds. Run `make api-client contract-check` for generated browser contracts.

The main real-model app is upgraded at http://localhost:3100 with preserved DB volume,
.env and native Ollama. Protected docs gateways were restarted at 3200/3201.
Baseline branch `baseline/platform-split-20261009`, tagged old runtime images and
private backup/isolated restored DB remain available. Never run `down -v` or delete
baseline artifacts before acceptance. See PLATFORM_SPLIT_REPORT.md for test evidence,
rollback commands and explicit production blockers. No schema/new model/training or
remote deployment changed. M3.2 remains the next model milestone.

`make check`: 64 CPU passed/23 DB-dependent skipped, Ruff/format/19-file strict mypy;
`make integration`: 87 real PostgreSQL tests. Browser acceptance covers both proxy
paths and real native Ollama stop/retry. Both scope docs and all dependency/security
checks passed. Private verification logs live in ignored data/migration-baseline.
The upstream TestClient deprecation warning remains. Local rehearsal is not target-host
TLS/GPU/load/security/legal acceptance; release gates are listed in the split report.


Final split acceptance adds five mock browser checks on each direct/BFF ingress path,
including same-origin canonical redirects and private metrics denial. Baseline-image
rollback and forward recovery were rehearsed on the isolated stack: the same session
and full conversation persisted. Run `scripts/verify_restart.py --rollback` after
setting the isolated API origin to 3121. Twenty-six browser JavaScript files were
checked against configured private credentials with no match. Final documentation
builds explicitly use ONESA_DOCS_API_URL=http://localhost:3100 for the existing local
playground; omit it for read-only production/static exports. Use the optional repo
Node 24 bin directory on PATH for direct docs commands; do not replace system Node.

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


Cancellation acceptance addendum: native Firefox uncovered a late-response persistence race after browser Stop. Added owned/CSRF-protected run-specific cancellation acknowledgement, preserved replay/ownership and prevented late completion from persisting. Browser Stop now waits for server acknowledgement; transient errors remain honest. Strict SSE start frames carry validated conversation/run IDs. Two new cancellation-negative regressions pass; final full results are in the private closure report. No baseline change or weaker Stop assertion.

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
