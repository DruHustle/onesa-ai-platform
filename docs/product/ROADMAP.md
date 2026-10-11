# Roadmap and milestone evidence

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

Continue M5 authorized live travel-provider acceptance, followed by M6 approved
training experiments and M7 hosted production acceptance. No provider credentials,
training run, GPU host or production approval is implied by delivered software.
The [AI configuration inventory](../engineering/AI_CONFIGURATION_INVENTORY.md)
records the latest source-backed environment matrix, actual resources and free-only
staging proposal. Hosted API503, isolated database provisioning/roles/migrations,
generation and embedding hosting, identity worker delivery, backup/restore,
manual security/accessibility and operations/content/legal acceptance remain open.
Verify the current hosted state before closing any finding.
Organization ownership is still unverified: published repositories are under
DruHustle; do not claim an approved transfer to onesa-ug.

Completed instruction logs and duplicate handoffs have been removed; implementation
history remains in Git and `docs/development/CHANGELOG.md`. Agent policies live only
in root `AGENTS.md`.

Owner reports Neon staging resource `onesa-ai-platform-backend-db-staging` created. Verify project/branch ownership, Free plan, PostgreSQL version/schema and isolated role permissions; rotate the disclosed owner credential before any connection. No duplicate Render database is needed. Runtime URL and actual staging origin remain unconfigured.


## Render startup failure follow-up — 2026-10-10

Local implementation and isolated regression verification passed; hosted repair remains
open. See [the exact evidence, changes and reviewed configuration procedure](../engineering/VERCEL_RENDER.md)
for current source/deployment revisions and outstanding provider checks. No push or
deployment, production secret change, DNS/resource/plan change or readiness acceptance.

## Branch protection acceptance — 2026-10-10

Private personal GitHub repositories remain **BLOCKED, NOT ENFORCED** after attempted ruleset/classic protection returned plan-denial HTTP 403. See [verified evidence and prepared policy](../development/BRANCH_PROTECTION_REPORT.md). Production environment approval and native integration gaps remain unresolved; no merge/deployment authorization is implied.
