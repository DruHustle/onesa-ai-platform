# Roadmap and milestone evidence

The independent Cybersecurity source module adds bounded evidence ingestion, owned
asset posture, versioned deterministic findings, human investigations and optional
read-only assistance. It defaults off and has no required peer, feed, 3D or model
service. Local synthetic checks and source availability do not establish hosted,
production, live OT or actual Smart Factory consumer acceptance. The
[capability matrix](../engineering/CYBERSECURITY.md#audit-and-capability-matrix)
separates these outcomes and retains the broader planned application-security scope.

Industrial Investigation V1.1 has a separately accepted protected synthetic demo;
normal AI production keeps it disabled. Current serving component identities and
qualified source scopes are maintained in README/CHANGELOG and protected release
receipts. The JSON evidence adapter, complete record navigation, Industrial account
export and attempt accounting are source changes undergoing their own qualification.
Independent domain review, a fair baseline comparison, measured useful-task economics
and real-customer processing remain outstanding. No live factory integration or
physical robotics is implied. See [the PRD](PRD.md) and
[evaluation protocol](INDUSTRIAL_EVALUATION.md).

> Historical hosted snapshot, reviewed 2026-10-13: [visual workflows and evidence limits](../ecosystem/VISUAL_WORKFLOWS.md). Workers AI staging generation/semantic embeddings and Oracle staging jobs/scanning are verified. Corrected database targets need new hosted acceptance; production, private documentation Access and physical hardware remain separately gated. Earlier dated milestone evidence below does not supersede this readback.

| Milestone | Delivered | Remaining evidence |
| --- | --- | --- |
| 0 Discovery/design | Continuation workflow, PRD/architecture/contracts, build/test baseline | No invented architecture sign-off |
| 1 Chat MVP | PostgreSQL/auth/persistence/Next.js/SSE/Compose and real browser flow | Broader UX/security review |
| 2 Local model | Shared Ollama/vLLM client, real Apple M3/Qwen3 serving, evaluation/benchmarks; pinned GPU/LoRA config | Actual compatible NVIDIA host loading/generation/memory/throughput |
| 3 Knowledge | TXT/PDF, versioned pgvector, lexical baseline/HTTP embedding adapter, sources/reindex/ownership | Local Qwen3-Embedding-0.6B/256-dimensional candidate qualified on synthetic EN/DE; hosted semantic endpoint, reindex and hostile-file isolation remain unverified |
| 4 Agent runtime | Shared-model planner interface, registered local tools, grants/limits/cancellation/history | Any future effectful tools require separate reviewed integrations |
| 5 Travel MVP | Typed saved/revisable mock/model itinerary planner and UI | Live maps/weather/flight/accommodation providers and their credentials |
| 6 Fine-tuning framework | Provenance/validation/splits/checksums/config dry-run, optional LoRA/QLoRA/evaluation/registry | Approved language datasets, CUDA runtime lock, actual training/baseline/release review |
| 7 Release controls | CI/audits/body bounds/logs/metrics/non-root/TLS template/restore/health probe | Actual TLS/host qualification, model load/stress, independent security, retention/alerts |

Milestone 2 acceptance now targets native Apple Silicon per the explicit request; NVIDIA
execution remains a separate unverified deployment qualification. Independent M3–M6 software
was implemented/tested without GPU dependency; no real-model or production acceptance is
inferred from mock passes. Phase B preserves public alias/API/UI while changing evaluated
weights/adapters. See the roadmap and engineering configuration inventory for exact tests and next actions.

Amendment 001 aligns every existing milestone with European-based general-purpose and
international positioning, preserving the order above. Phase B covers general/enterprise/
industrial/travel/multilingual and optional regional adaptations. Profile metadata is delivered;
actual specialized models, multimodal capabilities and enterprise integrations remain proposed.
No branding or specialization work delays the already working Chat MVP or M2 inference acceptance.

## Current unfinished work

### Applications powered by the platform

Planned application directions include recommendations and decision support for
travel, business feasibility and investment research, and smart farming for crop
selection and step-by-step cultivation. The farming workflow connects crop choice,
cultivation planning, condition monitoring, adapted activities and selling opportunities,
using soil, seasonal weather, water, production-cost and market-demand information.
Business/investment and farming workflows and their required data integrations remain
unimplemented and unqualified. Existing Travel itinerary features retain their current
scope. Public descriptions live in [Applications](../public/applications.md#application-directions).

### Existing qualification work

The earlier startup and optional-document corrections are included in independently
recorded application releases. Requalification of changed navigation/export/import
journeys is required; do not reopen a resolved startup defect without a regression.
Travel's live providers remain unconfigured; no paid provider or training experiment
is authorized by this roadmap. Current hosting, semantic endpoint, recovery and
monitoring receipts take precedence over older unverified milestone entries above.
A limited isolated pilot still needs the named customer/domain reviewer, permitted
inputs, identity and processing requirements, agreed acceptance and operating scope.

Organization ownership is still unverified: published repositories are under
DruHustle; do not claim an approved transfer to onesa-ug.

Completed instruction logs and duplicate handoffs have been removed; implementation
history remains in Git and `docs/development/CHANGELOG.md`. Agent policies live only
in root `AGENTS.md`.

The existing Neon AI staging database is migrated and connected through a verified
restricted runtime role. Protected Vercel Preview and the Render staging backend
deployed `898c224`; real hosted authentication, CSRF, isolation and restart persistence
passed. Final hosted run `38088509721` qualified application `43affff`: desktop,
tablet/mobile, automated accessibility, documentation links and scoped connection
recovery also passed. The proxy now strips provider headers/cookies while preserving
Onesa session/CSRF credentials; its regression and hosted authentication passed.
Manual accessibility review remains required. See
`docs/engineering/AI_CONFIGURATION_INVENTORY.md` for exact origins/revisions/evidence.
Hosted inference/embeddings and production acceptance remain blocked; do not recreate
the staging database, reuse portal credentials or promote staging to production.


## Branch protection acceptance

Private GitHub Free repositories remain unprotected. See [the verified governance report](../development/BRANCH_PROTECTION_REPORT.md). Public production qualification remains separate from isolated staging.

## Automated release qualification acceptance

Local evidence/approval automation and rejection tests are implemented. See
[qualification guide](../engineering/AUTOMATED_QUALIFICATION.md) for the trust model and owner actions. Remote CI/provenance validation, main
protection, encryption secret provisioning, complete hosted staging/production
acceptance and explicit owner operations/legal approval remain blocked.
The migration switch stays off and the original secret gate is retained.

## Private-Free release controls — 2026-10-11

Credential-free qualification and owner authorization are implemented locally. Remote installation, billing/visibility confirmation, production secret removal/rotation and independent provider auto-deploy verification remain pending owner actions. Direct pushes remain possible. See [the enforcement report](../development/PRIVATE_FREE_SAFEGUARDS.md).


## Local maintenance during Render credit hold — prepared 2026-10-16

The existing production baseline has since moved to Oracle; the Render hold remains.
The model-planned addition case produced a valid expected plan in one of the two
previously authorized synthetic diagnostics on 2026-10-16. No generated text was
retained and no application data changed. This does not establish the cause of the
historical hosted503 or replace the remaining source-bound hosted qualification.

Repository review reproduced a separate permission-path defect: with no registered
tool permission, model-backed requests could invoke inference and return503. The
development correction returns403 before planning, without saving an agent run.
Transport-level inference timeouts now retain the fixed `planning_timeout` diagnostic
category. Both permission cases and the timeout case failed before correction;
26 isolated agent/travel/planning tests pass afterward. These source corrections
are not yet deployed; production continues using its accepted migration baseline.

Render credits remain exhausted; Render deployment and Render-deploying qualification
are paused. The separate Oracle migration is authorized and accepted for the existing
production baseline. The historical hosted model-planned agent HTTP503 has no saved
provider/parse/timeout detail, so its cause cannot be asserted from that run.

Prepared changes distinguish fixed empty/oversize/JSON/shape/schema/provider/timeout
planning categories in protected metrics. Client errors stay generic, no prompt or
model output is logged, strict plan validation and tool authorization remain intact,
and no parsing fallback, model change or automatic retry is added.

The text-statistics screen sends its explicit permitted tool operation instead of
requesting model selection. It bounds initial history and run waits, preserves input,
separates unavailable history from an empty list, offers a read-only history retry,
keeps newly confirmed results through a late history response, and shows word/character
counts. A failed/uncertain submission is never automatically replayed. The standalone
model-planning acceptance workflow remains required; this UI change does not replace it.

Release scripts reject suspended/unverified Render metadata before deployment and
again before success; the staging producer checks before runtime configuration reads.
Offline checks and synthetic browser coverage are recorded in the existing restricted
release evidence. New-source hosted qualification/release remain pending source-bound
Oracle qualification; no local result establishes a production fix. Revert the focused maintenance commit
for source rollback, preserving the provider hold and historical evidence.
