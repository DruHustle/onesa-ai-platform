# Architecture & Workflows — visual source index

Open the [interactive Architecture & Workflows hub](/architecture) or [Engineering Onboarding](/onboarding). Both are adjacent persistent navigation entries in the internal build. The public hub serves only the reviewed simplified catalog.

## Status and source conventions

Solid arrows show implemented source connections; dashed arrows identify optional, planned or unqualified dependencies. Node text carries status so meaning does not depend on color. Green indicates verified staging service evidence, amber an outstanding qualification, and dashed gray planned components. Source implementation is distinct from deployed, staging-verified and production-qualified state. Review date: 2026-10-13. Exact documentation revision and source hashes come from the generated provenance, not an invented deployment ID.

## Diagram index

| Diagram | Editable source | Interactive view | What to understand |
| --- | --- | --- | --- |
| Complete Onesa Ecosystem Architecture | `docs/diagrams/ecosystem-current.mmd` | [Open](/architecture?diagram=ecosystem-current) | Source implemented; Oracle and Workers AI verified in staging; production acceptance pending |
| Infrastructure and environment boundaries | `docs/diagrams/infrastructure-current.mmd` | [Open](/architecture?diagram=infrastructure-current) | Provider roles verified; corrected staging database bindings require new hosted acceptance |
| dev to staging to main deployment and recovery | `docs/diagrams/delivery-current.mmd` | [Open](/architecture?diagram=delivery-current) | Actual workflows and mandatory gates; owner authorization accepted, technical qualification still required |
| Company Portal website CMS and private administration | `docs/diagrams/portal-current.mmd` | [Open](/architecture?diagram=portal-current) | Implemented API boundaries; staging scanner and jobs verified, production remains separately qualified |
| Upload quarantine scanning release and failure | `docs/diagrams/portal-scan-current.mmd` | [Open](/architecture?diagram=portal-scan-current) | Actual quarantine gates and clean-only download; scanner failure never releases files |
| Durable Portal jobs retries and restart recovery | `docs/diagrams/portal-jobs-current.mmd` | [Open](/architecture?diagram=portal-jobs-current) | Existing PostgreSQL queue implementation; scanner errors remain quarantined |
| Authenticated chat streaming persistence and outage | `docs/diagrams/ai-chat-current.mmd` | [Open](/architecture?diagram=ai-chat-current) | Workers AI native and hosted inference previously verified; corrected DB requalification pending |
| Ingestion semantic embeddings RAG and citations | `docs/diagrams/ai-rag-current.mmd` | [Open](/architecture?diagram=ai-rag-current) | Source implemented; real Workers AI semantic path tested against prior DB, corrected target acceptance pending |
| Robot cloud simulation and local edge boundary | `docs/diagrams/robot-current.mmd` | [Open](/architecture?diagram=robot-current) | Simulation implemented; Turso staging journal rolling handoff fix awaits hosted verification; physical actuation disabled |
| Product identities sessions roles and documentation access | `docs/diagrams/identity-current.mmd` | [Open](/architecture?diagram=identity-current) | Independent product auth; application MFA differs from separately required documentation MFA |
| Public and protected engineering documentation | `docs/diagrams/docs-access-current.mmd` | [Open](/architecture?diagram=docs-access-current) | Public live; Pages placeholder exists, engineering Access app MFA and owner-login acceptance not verified |
| Data lifecycle and environment separation | `docs/diagrams/data-current.mmd` | [Open](/architecture?diagram=data-current) | Distinct corrected staging targets configured; synthetic-only staging and production acceptance enforced |
| Monitoring incident response and evidence | `docs/diagrams/operations-current.mmd` | [Open](/architecture?diagram=operations-current) | Heartbeat and scanner health verified in staging; delivered alerts and production operations still need evidence |
| Backup restore rollback and disaster recovery | `docs/diagrams/recovery-current.mmd` | [Open](/architecture?diagram=recovery-current) | Source runbooks and isolated verification tools exist; production backup/restore acceptance pending |
| Product maturity and evidence required for release | `docs/diagrams/maturity-current.mmd` | [Open](/architecture?diagram=maturity-current) | Source and historical staging evidence do not establish complete production acceptance |
| First safe engineering contribution | `docs/diagrams/first-contribution.mmd` | [Open](/architecture?diagram=first-contribution) | Current three retained branches; no additional branches or discretionary reviewer requirements |
| Day 1 — Understand Onesa | `docs/diagrams/day-one.mmd` | [Open](/architecture?diagram=day-one) | Day 1: company products infrastructure documentation; learning completion is not release qualification |
| Day 2 — Understand the software | `docs/diagrams/day-two.mmd` | [Open](/architecture?diagram=day-two) | Day 2: repositories APIs storage identity; learning completion is not release qualification |
| Day 3 — Understand delivery | `docs/diagrams/day-three.mmd` | [Open](/architecture?diagram=day-three) | Day 3: dev staging main and qualification; learning completion is not release qualification |
| Day 4 — Understand operations | `docs/diagrams/day-four.mmd` | [Open](/architecture?diagram=day-four) | Day 4: providers monitoring incidents and recovery; learning completion is not release qualification |

Every major figure exposes rendered SVG, PNG, PDF and Mermaid exports, a text alternative, related reference, node selection, keyboard panning, zoom and enlarged viewing. Source and rendered hashes are validated in CI. Generated assets are ignored and rebuilt rather than maintained separately.

## Authorization matrix

| Boundary | Who / proof | Enforcement | Source reference |
| --- | --- | --- | --- |
| Portal public content | Visitor, public allowlisted paths | Published-state and host-aware API boundary | Portal `src/api` |
| Portal private records | Authenticated role; ownership where required | Server session, CSRF, role policies and fresh proof for sensitive changes | Portal `src/auth` |
| AI conversations, knowledge, agents, trips | Enabled user and owned resource | FastAPI dependency and resource ownership filters | AI `app/auth.py`, `app/knowledge.py` |
| Robot tasks | Existing single configured operator | Server operator/session checks plus independent SafetyGate | Robot `robot_api/main.py`, `robot_api/safety.py` |
| Private storage | Authorized API and scoped worker | Private bucket; clean-only download; quarantine retained on scan failure | Portal `src/services`, `src/jobs/worker.ts` |
| Engineering Pages | Approved identity, MFA, verified assertion and host | Access policy plus fail-closed server JWT check; hosted acceptance pending | `infra/cloudflare-docs/worker.mjs` |

MFA is not implied for every product login by documentation Access policy. Hosted Pages protection cannot hide publicly committed source. Full provider identifiers, credentials and actual user records are excluded from public artifacts.

## API and database source of truth

The [API explorer](/api-explorer) uses FastAPI OpenAPI and pinned actual Portal Fastify/Robot FastAPI contracts. The [Database explorer](/database) uses AI SQLAlchemy metadata and pinned Portal migrations/Robot journal DDL. Related schema pages retain actual columns, foreign keys, indexes and constraints. These are schema definitions, not live records. CI regenerates API/AI schema and checks drift; cross-product hashes pin the reviewed source revision.

## Current acceptance limits

Oracle staging worker/scanner and actual bounded queue probes passed. Workers AI native generation and semantic embeddings and an earlier hosted acceptance passed. Staging database scope corrections are configured but require fresh application deployment and hosted tests. Robot rolling journal lease handoff has a reviewed source fix awaiting hosted acceptance; durable production hosting remains unqualified. Production legacy Portal worker is retained until a qualified replacement exists. Engineering Pages has only a harmless staging placeholder. Origin/preview Access policies and MFA are configured; fifteen actual anonymous path probes redirect to Access login. Authorized-user acceptance remains pending. Earlier generic HTTP 403 was not proof of protection. No confidential build may be published until direct-origin, preview, static asset, index, download and authorized-user checks pass.

Owner release authorization is accepted. Production operations, backups/restores, delivered notifications, privacy disclosures and applicable statutory particulars must still be evidenced. No diagram sets release gates to PASS.
