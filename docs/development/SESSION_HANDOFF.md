# Session handoff

Date: 2026-10-09 (Europe/Berlin). Repository: `onesa-ai-platform`.
Current milestone M3; first incomplete task **M3.2: real semantic embedding qualification**.
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
