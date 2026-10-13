# Architecture & Workflows — visual source index

> Purpose: explain implemented trust boundaries and qualification. Audience: engineers and reviewers. Classification: internal engineering design. Owner: Onesa repository maintainers. Verified: 2026-10-13 against source and cited staging evidence; production acceptance remains incomplete. Applicable revisions are identified below and in generated provenance.

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
| Engineering Pages | Approved identity, MFA, verified assertion and host | Access policy plus fail-closed server JWT check; owner/MFA and anonymous hosted acceptance passed in staging | `infra/cloudflare-docs/worker.mjs` |

MFA is not implied for every product login by documentation Access policy. Hosted Pages protection cannot hide publicly committed source. Full provider identifiers, credentials and actual user records are excluded from public artifacts.

## API and database source of truth

The [API explorer](/api-explorer) uses FastAPI OpenAPI and pinned actual Portal Fastify/Robot FastAPI contracts. The [Database explorer](/database) uses AI SQLAlchemy metadata and pinned Portal migrations/Robot journal DDL. Related schema pages retain actual columns, foreign keys, indexes and constraints. These are schema definitions, not live records. CI regenerates API/AI schema and checks drift; cross-product hashes pin the reviewed source revision.

## Current acceptance limits

Portal hosted staging workflow 38328994648 passed at `5062f7f`, including corrected database/bucket isolation and private upload/scanner/download integrity. The same-source Oracle worker/scanner passed real benign/EICAR/quarantine/error and bounded queue/recovery probes. AI hosted staging workflow 38331890487 passed at `8c576371` against the corrected isolated database with actual Cloudflare generation, streaming and embeddings. These results qualify their cited staging scope only.

Robot's reviewed ordering and redacted handoff fixes passed staging CI at `97a84bf8`. Hosted workflow 38330809449 reports operator-login HTTP401; no journal change, password reset or physical operation occurred. Production durability remains unqualified. Production legacy Portal worker is retained until a qualified production Oracle replacement exists.

Engineering Pages actually serves revision `8c576371` at protected staging. Owner identity and MFA, hosted content, asset/index/download authorization and fifteen anonymous origin/preview redirects passed. The unchanged UI's full hosted suite covered 16 architecture sections, four learning days, 292 diagram exports and 18 layouts. Earlier placeholder-only and pending-owner-login statements are superseded. Production/custom internal hostname publication and overall operational acceptance remain incomplete.

Owner release authorization is accepted. Production operations, backups/restores, delivered notifications, privacy disclosures and applicable statutory particulars must still be evidenced. No diagram sets release gates to PASS.

## Critical workflow catalogue

The profiles below cover discovered business and operational paths, including failures and source tests. A referenced automated test is not a claim that every corresponding production route or UI state was executed. The restricted review manifest separately discovers all static/dynamic route patterns and API operations, leaving unmatched coverage explicit. Shared observability/privacy preconditions remain part of each profile.

### portal-browse — Public website and EN/DE browsing

**Workflow:** portal-browse

**Purpose:** Public website and EN/DE browsing

**Trigger:** Visitor navigation

**Actors:** Visitor or authorized staff, Portal frontend/API, PostgreSQL and relevant worker/storage provider

**Preconditions:** Correct environment and bounded validated inputs; enable external integrations only after their own health/isolation checks.

**Authentication and authorization:** Public host/path allowlist, bounded validation and request/account throttles; published-state filtering.

**Normal sequence:** Resolve locale/content route → read published CMS projection → render public page

**Data interactions:** Published pages/menus; draft and private records excluded

**Failure paths:** Missing locale/slug, unpublished content, API outage

**Retry or recovery:** 404 or bounded error state; explicit retry after health recovers

**Logs and monitoring:** Correlated application errors and applicable audit/metrics; never emit credentials or document contents. Delivered alerts are separately unqualified.

**Security and privacy:** Synthetic staging only until verified processing approval; scope identities and private records; never replay physical commands.

**Implementation and hosted status:** Implemented; staging critical paths verified, full route coverage requires the route inventory.

**Automated test source:** `onesa-company-portal/onesa-company-portal-backend/tests/integration.test.ts`

**Visualization:** [Open diagram](/architecture?diagram=portal-current) · editable source `docs/diagrams/portal-current.mmd`

**Implementation source:** `onesa-company-portal/onesa-company-portal-backend/src/app.ts`

### portal-enquiry — Customer/partner enquiries and contact delivery

**Workflow:** portal-enquiry

**Purpose:** Customer/partner enquiries and contact delivery

**Trigger:** Contact form submit

**Actors:** Visitor or authorized staff, Portal frontend/API, PostgreSQL and relevant worker/storage provider

**Preconditions:** Correct environment and bounded validated inputs; enable external integrations only after their own health/isolation checks.

**Authentication and authorization:** Public host/path allowlist, bounded validation and request/account throttles; published-state filtering.

**Normal sequence:** Validate fields/anti-abuse → persist enquiry/outbox → worker attempts notification

**Data interactions:** Enquiries, jobs and mail idempotency keys

**Failure paths:** Invalid input, quota, DB failure, missing/rejecting mail provider

**Retry or recovery:** Bounded outbox retry/failure cap; actual delivered mail is not qualified

**Logs and monitoring:** Correlated application errors and applicable audit/metrics; never emit credentials or document contents. Delivered alerts are separately unqualified.

**Security and privacy:** Synthetic staging only until verified processing approval; scope identities and private records; never replay physical commands.

**Implementation and hosted status:** Implemented; mail delivery remains unqualified.

**Automated test source:** `onesa-company-portal/onesa-company-portal-backend/tests/integration.test.ts`

**Visualization:** [Open diagram](/architecture?diagram=portal-jobs-current) · editable source `docs/diagrams/portal-jobs-current.mmd`

**Implementation source:** `onesa-company-portal/onesa-company-portal-backend/src/app.ts`

### portal-cms — CMS editing and bilingual publication

**Workflow:** portal-cms

**Purpose:** CMS editing and bilingual publication

**Trigger:** Authorized staff save/publish

**Actors:** Visitor or authorized staff, Portal frontend/API, PostgreSQL and relevant worker/storage provider

**Preconditions:** Correct environment and bounded validated inputs; enable external integrations only after their own health/isolation checks.

**Authentication and authorization:** Server session, CSRF on mutations, per-route role/ownership policy; fresh proof for sensitive actions.

**Normal sequence:** Authenticate → role check → validate draft → preserve revision → explicitly publish

**Data interactions:** CMS pages, revisions, company facts, menus and audit

**Failure paths:** Unauthorized role, stale/invalid content, missing publication facts

**Retry or recovery:** Keep prior published revision; correct draft and explicitly retry

**Logs and monitoring:** Correlated application errors and applicable audit/metrics; never emit credentials or document contents. Delivered alerts are separately unqualified.

**Security and privacy:** Synthetic staging only until verified processing approval; scope identities and private records; never replay physical commands.

**Implementation and hosted status:** Implemented; production CMS synchronization not attested.

**Automated test source:** `onesa-company-portal/onesa-company-portal-backend/tests/integration.test.ts`

**Visualization:** [Open diagram](/architecture?diagram=portal-current) · editable source `docs/diagrams/portal-current.mmd`

**Implementation source:** `onesa-company-portal/onesa-company-portal-backend/src/app.ts`

### portal-auth-mfa — Login, MFA, logout, renewal and revocation

**Workflow:** portal-auth-mfa

**Purpose:** Login, MFA, logout, renewal and revocation

**Trigger:** Staff authentication/session operation

**Actors:** Visitor or authorized staff, Portal frontend/API, PostgreSQL and relevant worker/storage provider

**Preconditions:** Correct environment and bounded validated inputs; enable external integrations only after their own health/isolation checks.

**Authentication and authorization:** Server session, CSRF on mutations, per-route role/ownership policy; fresh proof for sensitive actions.

**Normal sequence:** Rate-limit → validate password and TOTP/recovery atomically → create scoped session/CSRF → revoke on logout

**Data interactions:** Users, sessions, MFA step/recovery and audit records

**Failure paths:** Bad credentials/reused TOTP, disabled account, expired session, CSRF

**Retry or recovery:** Reject without privilege change; authorized recovery; no automatic account reset

**Logs and monitoring:** Correlated application errors and applicable audit/metrics; never emit credentials or document contents. Delivered alerts are separately unqualified.

**Security and privacy:** Synthetic staging only until verified processing approval; scope identities and private records; never replay physical commands.

**Implementation and hosted status:** Hosted synthetic staging login and denial verified.

**Automated test source:** `onesa-company-portal/onesa-company-portal-backend/tests/integration.test.ts`

**Visualization:** [Open diagram](/architecture?diagram=identity-current) · editable source `docs/diagrams/identity-current.mmd`

**Implementation source:** `onesa-company-portal/onesa-company-portal-backend/src/app.ts`

### portal-recruitment — Recruitment and applicant intake

**Workflow:** portal-recruitment

**Purpose:** Recruitment and applicant intake

**Trigger:** Published vacancy application

**Actors:** Visitor or authorized staff, Portal frontend/API, PostgreSQL and relevant worker/storage provider

**Preconditions:** Correct environment and bounded validated inputs; enable external integrations only after their own health/isolation checks.

**Authentication and authorization:** Public host/path allowlist, bounded validation and request/account throttles; published-state filtering. Private review/download additionally requires staff authorization.

**Normal sequence:** Validate vacancy/application → quarantine upload → retain private applicant references → queue notifications

**Data interactions:** Vacancies, applications, applicant-classified files and outbox

**Failure paths:** Closed/missing vacancy, invalid/oversized upload, storage/DB outage

**Retry or recovery:** Reject safely; retain quarantine and retry only scoped jobs

**Logs and monitoring:** Correlated application errors and applicable audit/metrics; never emit credentials or document contents. Delivered alerts are separately unqualified.

**Security and privacy:** Synthetic staging only until verified processing approval; scope identities and private records; never replay physical commands.

**Implementation and hosted status:** Implemented; real applicant processing remains privacy-gated.

**Automated test source:** `onesa-company-portal/onesa-company-portal-backend/tests/integration.test.ts`

**Visualization:** [Open diagram](/architecture?diagram=portal-scan-current) · editable source `docs/diagrams/portal-scan-current.mmd`

**Implementation source:** `onesa-company-portal/onesa-company-portal-backend/src/app.ts`

### portal-upload — Private upload and clean-only download

**Workflow:** portal-upload

**Purpose:** Private upload and clean-only download

**Trigger:** Authorized upload/download request

**Actors:** Visitor or authorized staff, Portal frontend/API, PostgreSQL and relevant worker/storage provider

**Preconditions:** Correct environment and bounded validated inputs; enable external integrations only after their own health/isolation checks.

**Authentication and authorization:** Server session, CSRF on mutations, per-route role/ownership policy; fresh proof for sensitive actions.

**Normal sequence:** Validate bytes/type/size → private object store → quarantine row → scan → clean-only authorized download

**Data interactions:** Files, versions, storage key/digest and private objects

**Failure paths:** Content mismatch, non-clean scan, unauthorized viewer, missing object

**Retry or recovery:** Deny download; preserve private quarantine and report bounded failure

**Logs and monitoring:** Correlated application errors and applicable audit/metrics; never emit credentials or document contents. Delivered alerts are separately unqualified.

**Security and privacy:** Synthetic staging only until verified processing approval; scope identities and private records; never replay physical commands.

**Implementation and hosted status:** Hosted synthetic storage/scanner/download integrity and viewer denial verified.

**Automated test source:** `onesa-company-portal/onesa-company-portal-backend/tests/integration.test.ts`

**Visualization:** [Open diagram](/architecture?diagram=portal-scan-current) · editable source `docs/diagrams/portal-scan-current.mmd`

**Implementation source:** `onesa-company-portal/onesa-company-portal-backend/src/app.ts`

### portal-scan — Oracle ClamAV benign/infected/failure scanning

**Workflow:** portal-scan

**Purpose:** Oracle ClamAV benign/infected/failure scanning

**Trigger:** Worker scans quarantined file

**Actors:** Visitor or authorized staff, Portal frontend/API, PostgreSQL and relevant worker/storage provider

**Preconditions:** Correct environment and bounded validated inputs; enable external integrations only after their own health/isolation checks.

**Authentication and authorization:** Server session, CSRF on mutations, per-route role/ownership policy; fresh proof for sensitive actions. Scanner socket is private; no public TCP endpoint.

**Normal sequence:** Read scoped quarantine → bounded private object → Unix-socket scan → clean/rejected result

**Data interactions:** File scan state, digests and signature volume

**Failure paths:** EICAR/infection, unavailable scanner, signature/transport failure

**Retry or recovery:** Reject infected content; leave unknown/error state quarantined

**Logs and monitoring:** Correlated application errors and applicable audit/metrics; never emit credentials or document contents. Delivered alerts are separately unqualified.

**Security and privacy:** Synthetic staging only until verified processing approval; scope identities and private records; never replay physical commands.

**Implementation and hosted status:** Actual ARM64 staging benign/EICAR/failure/quarantine verified.

**Automated test source:** `onesa-company-portal/onesa-company-portal-backend/tests/scanner.test.ts`

**Visualization:** [Open diagram](/architecture?diagram=portal-scan-current) · editable source `docs/diagrams/portal-scan-current.mmd`

**Implementation source:** `onesa-company-portal/onesa-company-portal-backend/src/services/storage.ts`

### portal-jobs — Job submission, execution, retries and restart recovery

**Workflow:** portal-jobs

**Purpose:** Job submission, execution, retries and restart recovery

**Trigger:** Outbox insert or periodic worker tick

**Actors:** Visitor or authorized staff, Portal frontend/API, PostgreSQL and relevant worker/storage provider

**Preconditions:** Correct environment and bounded validated inputs; enable external integrations only after their own health/isolation checks.

**Authentication and authorization:** Server session, CSRF on mutations, per-route role/ownership policy; fresh proof for sensitive actions.

**Normal sequence:** Claim bounded work → perform idempotent transport → acknowledge or schedule retry → recover stale locks

**Data interactions:** Jobs, storage-deletion outbox, heartbeats and attempt counters

**Failure paths:** Provider rejection, crash, stale lock, retry exhaustion

**Retry or recovery:** Limited retries for transport jobs; failed state after cap; scan errors stay quarantine

**Logs and monitoring:** Correlated application errors and applicable audit/metrics; never emit credentials or document contents. Delivered alerts are separately unqualified.

**Security and privacy:** Synthetic staging only until verified processing approval; scope identities and private records; never replay physical commands.

**Implementation and hosted status:** Actual staging deduplication, retries, stale locks, cap and restart verified; production unqualified.

**Automated test source:** `onesa-company-portal/onesa-company-portal-backend/tests/worker-startup.test.ts`

**Visualization:** [Open diagram](/architecture?diagram=portal-jobs-current) · editable source `docs/diagrams/portal-jobs-current.mmd`

**Implementation source:** `onesa-company-portal/onesa-company-portal-backend/src/jobs/worker.ts`

### portal-retention — Document retention and deletion

**Workflow:** portal-retention

**Purpose:** Document retention and deletion

**Trigger:** Authorized deletion/retention job

**Actors:** Visitor or authorized staff, Portal frontend/API, PostgreSQL and relevant worker/storage provider

**Preconditions:** Correct environment and bounded validated inputs; enable external integrations only after their own health/isolation checks.

**Authentication and authorization:** Server session, CSRF on mutations, per-route role/ownership policy; fresh proof for sensitive actions.

**Normal sequence:** Authorize → preserve required metadata/history → enqueue scoped object deletion → retry bounded transport

**Data interactions:** File references/versions and deletion outbox

**Failure paths:** Referenced object, transport outage, concurrent operations

**Retry or recovery:** Idempotent scoped deletion; never reset a database or delete unrelated objects

**Logs and monitoring:** Correlated application errors and applicable audit/metrics; never emit credentials or document contents. Delivered alerts are separately unqualified.

**Security and privacy:** Synthetic staging only until verified processing approval; scope identities and private records; never replay physical commands.

**Implementation and hosted status:** Implemented; production retention/legal policy not independently verified.

**Automated test source:** `onesa-company-portal/onesa-company-portal-backend/tests/integration.test.ts`

**Visualization:** [Open diagram](/architecture?diagram=data-current) · editable source `docs/diagrams/data-current.mmd`

**Implementation source:** `onesa-company-portal/onesa-company-portal-backend/src/services/workflows.ts`

### portal-documents — Document generation/export and audit

**Workflow:** portal-documents

**Purpose:** Document generation/export and audit

**Trigger:** Authorized administrative export

**Actors:** Visitor or authorized staff, Portal frontend/API, PostgreSQL and relevant worker/storage provider

**Preconditions:** Correct environment and bounded validated inputs; enable external integrations only after their own health/isolation checks.

**Authentication and authorization:** Server session, CSRF on mutations, per-route role/ownership policy; fresh proof for sensitive actions.

**Normal sequence:** Validate template/options → retrieve authorized data → bounded export → record audit

**Data interactions:** Templates and authorized document metadata

**Failure paths:** Permission failure, malformed input, unavailable source data

**Retry or recovery:** Deny or return bounded error; retry only after correcting preconditions

**Logs and monitoring:** Correlated application errors and applicable audit/metrics; never emit credentials or document contents. Delivered alerts are separately unqualified.

**Security and privacy:** Synthetic staging only until verified processing approval; scope identities and private records; never replay physical commands.

**Implementation and hosted status:** Implemented; production export acceptance not attested.

**Automated test source:** `onesa-company-portal/onesa-company-portal-backend/tests/integration.test.ts`

**Visualization:** [Open diagram](/architecture?diagram=portal-current) · editable source `docs/diagrams/portal-current.mmd`

**Implementation source:** `onesa-company-portal/onesa-company-portal-backend/src/documents/export.ts`

### ai-identity — Invitation, login, recovery, session and account deletion

**Workflow:** ai-identity

**Purpose:** Invitation, login, recovery, session and account deletion

**Trigger:** Account/identity request

**Actors:** Account holder, same-origin frontend, FastAPI, owned database records and configured provider

**Preconditions:** Correct environment and bounded validated inputs; enable external integrations only after their own health/isolation checks.

**Authentication and authorization:** Enabled account, scoped secure session, CSRF on mutations and resource ownership filters; engineering allowlist for private documentation.

**Normal sequence:** Validate invitation/credentials and bounded delivery proof → issue/revoke session → enforce account ownership

**Data interactions:** Users, invitations, sessions, recovery/delivery records and owned data

**Failure paths:** Invalid/expired proof, throttling, mail disabled, revoked account

**Retry or recovery:** Deny access; bounded delivery retries; delete only owned resources

**Logs and monitoring:** Correlated application errors and applicable audit/metrics; never emit credentials or document contents. Delivered alerts are separately unqualified.

**Security and privacy:** Synthetic staging only until verified processing approval; scope identities and private records; never replay physical commands.

**Implementation and hosted status:** Implemented; hosted synthetic auth/denial/isolation verified; mail delivery remains separate.

**Automated test source:** `onesa-ai-platform/onesa-ai-platform-backend/tests/test_identity.py`

**Visualization:** [Open diagram](/architecture?diagram=identity-current) · editable source `docs/diagrams/identity-current.mmd`

**Implementation source:** `onesa-ai-platform/onesa-ai-platform-backend/app/identity.py`

### ai-chat — Chat lifecycle and conversation persistence

**Workflow:** ai-chat

**Purpose:** Chat lifecycle and conversation persistence

**Trigger:** Authenticated message submit

**Actors:** Account holder, same-origin frontend, FastAPI, owned database records and configured provider

**Preconditions:** Correct environment and bounded validated inputs; enable external integrations only after their own health/isolation checks.

**Authentication and authorization:** Enabled account, scoped secure session, CSRF on mutations and resource ownership filters; engineering allowlist for private documentation.

**Normal sequence:** Authorize owned conversation → persist input → route configured model → stream/store bounded output

**Data interactions:** Conversations, messages and citations

**Failure paths:** Unknown conversation, provider timeout/error, capacity exhausted

**Retry or recovery:** Return correlated error; preserve owned history; no automatic tool/physical replay

**Logs and monitoring:** Correlated application errors and applicable audit/metrics; never emit credentials or document contents. Delivered alerts are separately unqualified.

**Security and privacy:** Synthetic staging only until verified processing approval; scope identities and private records; never replay physical commands.

**Implementation and hosted status:** Real Cloudflare synthetic staging chat, streaming and ownership verified.

**Automated test source:** `onesa-ai-platform/onesa-ai-platform-backend/tests/test_chat_integration.py`

**Visualization:** [Open diagram](/architecture?diagram=ai-chat-current) · editable source `docs/diagrams/ai-chat-current.mmd`

**Implementation source:** `onesa-ai-platform/onesa-ai-platform-backend/app/chat.py`

### ai-stream-cancel — Streaming, cancellation and disconnect recovery

**Workflow:** ai-stream-cancel

**Purpose:** Streaming, cancellation and disconnect recovery

**Trigger:** Stream/stop/navigation event

**Actors:** Account holder, same-origin frontend, FastAPI, owned database records and configured provider

**Preconditions:** Correct environment and bounded validated inputs; enable external integrations only after their own health/isolation checks.

**Authentication and authorization:** Enabled account, scoped secure session, CSRF on mutations and resource ownership filters; engineering allowlist for private documentation.

**Normal sequence:** Open bounded provider stream → relay approved chunks → detect cancel/disconnect → fence late writes

**Data interactions:** Owned conversation/output and capacity leases

**Failure paths:** Connection loss, malformed provider event, timeout

**Retry or recovery:** Cancel provider task and release resources; preserve terminal state

**Logs and monitoring:** Correlated application errors and applicable audit/metrics; never emit credentials or document contents. Delivered alerts are separately unqualified.

**Security and privacy:** Synthetic staging only until verified processing approval; scope identities and private records; never replay physical commands.

**Implementation and hosted status:** Implemented; real staging streaming and source cancellation regressions verified.

**Automated test source:** `onesa-ai-platform/onesa-ai-platform-backend/tests/test_cancel_generation.py`

**Visualization:** [Open diagram](/architecture?diagram=ai-chat-current) · editable source `docs/diagrams/ai-chat-current.mmd`

**Implementation source:** `onesa-ai-platform/onesa-ai-platform-backend/app/chat.py`

### ai-provider — Modular model routing and Cloudflare inference

**Workflow:** ai-provider

**Purpose:** Modular model routing and Cloudflare inference

**Trigger:** Model-client call

**Actors:** Account holder, same-origin frontend, FastAPI, owned database records and configured provider

**Preconditions:** Correct environment and bounded validated inputs; enable external integrations only after their own health/isolation checks.

**Authentication and authorization:** Enabled account, scoped secure session, CSRF on mutations and resource ownership filters; engineering allowlist for private documentation.

**Normal sequence:** Select configured adapter/model → authenticated bounded HTTPS request → validate provider output

**Data interactions:** Versioned provider/model settings; no provider keys in browser

**Failure paths:** HTTP401/429/5xx, malformed body, missing model, quota exhaustion

**Retry or recovery:** Fail closed with bounded timeout/error; no silent mock fallback

**Logs and monitoring:** Correlated application errors and applicable audit/metrics; never emit credentials or document contents. Delivered alerts are separately unqualified.

**Security and privacy:** Synthetic staging only until verified processing approval; scope identities and private records; never replay physical commands.

**Implementation and hosted status:** Real Workers AI staging verified; production serving credentials/provider tests verified separately, with exact application rollout and operating acceptance pending.

**Automated test source:** `onesa-ai-platform/onesa-ai-platform-backend/tests/test_cloudflare.py`

**Visualization:** [Open diagram](/architecture?diagram=ai-chat-current) · editable source `docs/diagrams/ai-chat-current.mmd`

**Implementation source:** `onesa-ai-platform/onesa-ai-platform-backend/app/inference.py`

### ai-ingestion — Knowledge upload and document processing

**Workflow:** ai-ingestion

**Purpose:** Knowledge upload and document processing

**Trigger:** Owned knowledge/document upload

**Actors:** Account holder, same-origin frontend, FastAPI, owned database records and configured provider

**Preconditions:** Correct environment and bounded validated inputs; enable external integrations only after their own health/isolation checks.

**Authentication and authorization:** Enabled account, scoped secure session, CSRF on mutations and resource ownership filters; engineering allowlist for private documentation.

**Normal sequence:** Validate content/size/type → bounded PDF/text extraction → chunk → embed → store owned document/version

**Data interactions:** Uploads, knowledge documents/chunks and owner identity

**Failure paths:** Malformed PDF, forbidden parsing capability, body deadline, embedding failure

**Retry or recovery:** Reject or preserve explicit failure; never index an unverified partial document

**Logs and monitoring:** Correlated application errors and applicable audit/metrics; never emit credentials or document contents. Delivered alerts are separately unqualified.

**Security and privacy:** Synthetic staging only until verified processing approval; scope identities and private records; never replay physical commands.

**Implementation and hosted status:** Implemented; synthetic staging semantic document indexing verified.

**Automated test source:** `onesa-ai-platform/onesa-ai-platform-backend/tests/test_uploads.py`

**Visualization:** [Open diagram](/architecture?diagram=ai-rag-current) · editable source `docs/diagrams/ai-rag-current.mmd`

**Implementation source:** `onesa-ai-platform/onesa-ai-platform-backend/app/knowledge.py`

### ai-embeddings — Embedding projection and pgvector indexing

**Workflow:** ai-embeddings

**Purpose:** Embedding projection and pgvector indexing

**Trigger:** Chunk embedding/reindex

**Actors:** Account holder, same-origin frontend, FastAPI, owned database records and configured provider

**Preconditions:** Correct environment and bounded validated inputs; enable external integrations only after their own health/isolation checks.

**Authentication and authorization:** Enabled account, scoped secure session, CSRF on mutations and resource ownership filters; engineering allowlist for private documentation.

**Normal sequence:** Call configured embedding adapter → validate dimensions/finite values → versioned normalized 256 projection → index

**Data interactions:** Embedding revision, vectors and document chunks

**Failure paths:** Provider quota/error, wrong dimension/revision, zero/nonfinite vector

**Retry or recovery:** Reject incompatible vectors; explicit reindex after approved provider change

**Logs and monitoring:** Correlated application errors and applicable audit/metrics; never emit credentials or document contents. Delivered alerts are separately unqualified.

**Security and privacy:** Synthetic staging only until verified processing approval; scope identities and private records; never replay physical commands.

**Implementation and hosted status:** Cloudflare Qwen3 native1024 → normalized256 staging path verified.

**Automated test source:** `onesa-ai-platform/onesa-ai-platform-backend/tests/test_embedding_service.py`

**Visualization:** [Open diagram](/architecture?diagram=ai-rag-current) · editable source `docs/diagrams/ai-rag-current.mmd`

**Implementation source:** `onesa-ai-platform/onesa-ai-platform-backend/app/knowledge.py`

### ai-rag — Permission-filtered retrieval, RAG and citations

**Workflow:** ai-rag

**Purpose:** Permission-filtered retrieval, RAG and citations

**Trigger:** Authenticated knowledge query/chat

**Actors:** Account holder, same-origin frontend, FastAPI, owned database records and configured provider

**Preconditions:** Correct environment and bounded validated inputs; enable external integrations only after their own health/isolation checks.

**Authentication and authorization:** Enabled account, scoped secure session, CSRF on mutations and resource ownership filters; engineering allowlist for private documentation.

**Normal sequence:** Scope documents to account → semantic vector search → bounded source context → answer/citations

**Data interactions:** Owned chunks, documents, source URLs and conversation citations

**Failure paths:** No matches, unauthorized document, provider error

**Retry or recovery:** Return explicit no-source/error state; do not broaden ownership filters

**Logs and monitoring:** Correlated application errors and applicable audit/metrics; never emit credentials or document contents. Delivered alerts are separately unqualified.

**Security and privacy:** Synthetic staging only until verified processing approval; scope identities and private records; never replay physical commands.

**Implementation and hosted status:** Actual staging retrieval of newly stored synthetic owned document verified.

**Automated test source:** `onesa-ai-platform/onesa-ai-platform-backend/tests/test_knowledge.py`

**Visualization:** [Open diagram](/architecture?diagram=ai-rag-current) · editable source `docs/diagrams/ai-rag-current.mmd`

**Implementation source:** `onesa-ai-platform/onesa-ai-platform-backend/app/knowledge.py`

### ai-agents — Agent orchestration and authorized tools

**Workflow:** ai-agents

**Purpose:** Agent orchestration and authorized tools

**Trigger:** Owned agent run

**Actors:** Account holder, same-origin frontend, FastAPI, owned database records and configured provider

**Preconditions:** Correct environment and bounded validated inputs; enable external integrations only after their own health/isolation checks.

**Authentication and authorization:** Enabled account, scoped secure session, CSRF on mutations and resource ownership filters; engineering allowlist for private documentation.

**Normal sequence:** Validate tool registry/permission → execute bounded authorized steps → record/cancel run

**Data interactions:** Agent runs, tool authorization and owned history

**Failure paths:** Unapproved tool, timeout, cancelled authority, malformed output

**Retry or recovery:** Reject tool action; record terminal state; no uncontrolled retries

**Logs and monitoring:** Correlated application errors and applicable audit/metrics; never emit credentials or document contents. Delivered alerts are separately unqualified.

**Security and privacy:** Synthetic staging only until verified processing approval; scope identities and private records; never replay physical commands.

**Implementation and hosted status:** Implemented/source tested; individual hosted tools are not all attested.

**Automated test source:** `onesa-ai-platform/onesa-ai-platform-backend/tests/test_agents_travel.py`

**Visualization:** [Open diagram](/architecture?diagram=agents) · editable source `docs/diagrams/agents.mmd`

**Implementation source:** `onesa-ai-platform/onesa-ai-platform-backend/app/agents.py`

### ai-travel — Travel planning, revision and saved itinerary

**Workflow:** ai-travel

**Purpose:** Travel planning, revision and saved itinerary

**Trigger:** Owned planning request

**Actors:** Account holder, same-origin frontend, FastAPI, owned database records and configured provider

**Preconditions:** Correct environment and bounded validated inputs; enable external integrations only after their own health/isolation checks.

**Authentication and authorization:** Enabled account, scoped secure session, CSRF on mutations and resource ownership filters; engineering allowlist for private documentation.

**Normal sequence:** Validate preferences → route structured planner → validate/save itinerary → revise within ownership

**Data interactions:** Trips, itineraries and owned revisions

**Failure paths:** Provider failure or invalid structured itinerary

**Retry or recovery:** Bounded retry/error; no actual booking, live price or availability claim

**Logs and monitoring:** Correlated application errors and applicable audit/metrics; never emit credentials or document contents. Delivered alerts are separately unqualified.

**Security and privacy:** Synthetic staging only until verified processing approval; scope identities and private records; never replay physical commands.

**Implementation and hosted status:** Implemented/source tested; commercial travel-provider integration unconfigured.

**Automated test source:** `onesa-ai-platform/onesa-ai-platform-backend/tests/test_agents_travel.py`

**Visualization:** [Open diagram](/architecture?diagram=travel) · editable source `docs/diagrams/travel.mmd`

**Implementation source:** `onesa-ai-platform/onesa-ai-platform-backend/app/travel.py`

### ai-quota — Rate limits and capacity recovery

**Workflow:** ai-quota

**Purpose:** Rate limits and capacity recovery

**Trigger:** Bounded API/concurrency request

**Actors:** Account holder, same-origin frontend, FastAPI, owned database records and configured provider

**Preconditions:** Correct environment and bounded validated inputs; enable external integrations only after their own health/isolation checks.

**Authentication and authorization:** Enabled account, scoped secure session, CSRF on mutations and resource ownership filters; engineering allowlist for private documentation.

**Normal sequence:** Apply request/account limits → claim scoped capacity → execute → release/recover lease

**Data interactions:** Capacity slots and rate-limit counters

**Failure paths:** Quota exhaustion, crashed lease holder, provider limit

**Retry or recovery:** Reject bounded capacity; recover expired leases without replay

**Logs and monitoring:** Correlated application errors and applicable audit/metrics; never emit credentials or document contents. Delivered alerts are separately unqualified.

**Security and privacy:** Synthetic staging only until verified processing approval; scope identities and private records; never replay physical commands.

**Implementation and hosted status:** Implemented/source tested; free allocation is bounded, production load unqualified.

**Automated test source:** `onesa-ai-platform/onesa-ai-platform-backend/tests/test_capacity.py`

**Visualization:** [Open diagram](/architecture?diagram=ai-chat-current) · editable source `docs/diagrams/ai-chat-current.mmd`

**Implementation source:** `onesa-ai-platform/onesa-ai-platform-backend/app/capacity.py`

### ai-delete — Account, conversation and document deletion

**Workflow:** ai-delete

**Purpose:** Account, conversation and document deletion

**Trigger:** Authorized owned-resource delete

**Actors:** Account holder, same-origin frontend, FastAPI, owned database records and configured provider

**Preconditions:** Correct environment and bounded validated inputs; enable external integrations only after their own health/isolation checks.

**Authentication and authorization:** Enabled account, scoped secure session, CSRF on mutations and resource ownership filters; engineering allowlist for private documentation.

**Normal sequence:** Recheck owner → remove owned references and retained resources under constraints → revoke applicable authority

**Data interactions:** Account/conversations/documents, vectors and sessions

**Failure paths:** Forbidden ownership, concurrent references or storage error

**Retry or recovery:** Transaction rollback/bounded error; no cross-user deletion

**Logs and monitoring:** Correlated application errors and applicable audit/metrics; never emit credentials or document contents. Delivered alerts are separately unqualified.

**Security and privacy:** Synthetic staging only until verified processing approval; scope identities and private records; never replay physical commands.

**Implementation and hosted status:** Implemented/source tested; production retention/privacy policy unverified.

**Automated test source:** `onesa-ai-platform/onesa-ai-platform-backend/tests/test_account_data.py`

**Visualization:** [Open diagram](/architecture?diagram=data-current) · editable source `docs/diagrams/data-current.mmd`

**Implementation source:** `onesa-ai-platform/onesa-ai-platform-backend/app/account.py`

### robot-login — Existing operator login/logout

**Workflow:** robot-login

**Purpose:** Existing operator login/logout

**Trigger:** Operator login

**Actors:** Existing operator, simulator API, independent SafetyGate and applicable edge/journal

**Preconditions:** Correct environment and bounded validated inputs; enable external integrations only after their own health/isolation checks.

**Authentication and authorization:** Existing configured operator session, strict deployed Origin, CSRF for mutation, independent SafetyGate; edge token/device binding where applicable. No ordinary cloud workflow enables physical actuation.

**Normal sequence:** Check deployed origin → throttle → validate unchanged credentials → issue scoped session

**Data interactions:** Operator configuration and process-local sessions

**Failure paths:** Wrong origin/password, expiry, storage unavailable

**Retry or recovery:** Deny; preserve account/password; reconcile only approved test secret

**Logs and monitoring:** Correlated application errors and applicable audit/metrics; never emit credentials or document contents. Delivered alerts are separately unqualified.

**Security and privacy:** Synthetic staging only until verified processing approval; scope identities and private records; never replay physical commands.

**Implementation and hosted status:** Implemented; current hosted test credential returns HTTP401.

**Automated test source:** `onesa-ai-robot/onesa-ai-robot-backend/tests/test_simulation.py`

**Visualization:** [Open diagram](/architecture?diagram=identity-current) · editable source `docs/diagrams/identity-current.mmd`

**Implementation source:** `onesa-ai-robot/onesa-ai-robot-backend/robot_api/main.py`

### robot-task — Submission, expiration, cancel and task-state execution

**Workflow:** robot-task

**Purpose:** Submission, expiration, cancel and task-state execution

**Trigger:** Authorized task request

**Actors:** Existing operator, simulator API, independent SafetyGate and applicable edge/journal

**Preconditions:** Correct environment and bounded validated inputs; enable external integrations only after their own health/isolation checks.

**Authentication and authorization:** Existing configured operator session, strict deployed Origin, CSRF for mutation, independent SafetyGate; edge token/device binding where applicable. No ordinary cloud workflow enables physical actuation.

**Normal sequence:** Validate bounded task → recheck authority/safety → persist acknowledged event → simulate → terminal history

**Data interactions:** Task queue/events, stop latch and owned writer lease

**Failure paths:** Expired command, stop/fault, persistence loss, revoked authority

**Retry or recovery:** Latch stop/cancel unfinished work; no replay after restart

**Logs and monitoring:** Correlated application errors and applicable audit/metrics; never emit credentials or document contents. Delivered alerts are separately unqualified.

**Security and privacy:** Synthetic staging only until verified processing approval; scope identities and private records; never replay physical commands.

**Implementation and hosted status:** Source/isolated simulation verified; current hosted release is blocked at login.

**Automated test source:** `onesa-ai-robot/onesa-ai-robot-backend/tests/test_simulation.py`

**Visualization:** [Open diagram](/architecture?diagram=robot-current) · editable source `docs/diagrams/robot-current.mmd`

**Implementation source:** `onesa-ai-robot/onesa-ai-robot-backend/robot_api/main.py`

### robot-telemetry — Telemetry, device state and connection loss

**Workflow:** robot-telemetry

**Purpose:** Telemetry, device state and connection loss

**Trigger:** Periodic state/heartbeat or edge report

**Actors:** Existing operator, simulator API, independent SafetyGate and applicable edge/journal

**Preconditions:** Correct environment and bounded validated inputs; enable external integrations only after their own health/isolation checks.

**Authentication and authorization:** Existing configured operator session, strict deployed Origin, CSRF for mutation, independent SafetyGate; edge token/device binding where applicable. No ordinary cloud workflow enables physical actuation.

**Normal sequence:** Validate device/session → update bounded state → evaluate independent freshness/safety → publish authorized telemetry

**Data interactions:** Ephemeral state, heartbeat and bounded journal history

**Failure paths:** Unknown device, stale heartbeat, disconnect, malformed telemetry

**Retry or recovery:** Fail safe and require authorized restart; never retain sessions as recovered authority

**Logs and monitoring:** Correlated application errors and applicable audit/metrics; never emit credentials or document contents. Delivered alerts are separately unqualified.

**Security and privacy:** Synthetic staging only until verified processing approval; scope identities and private records; never replay physical commands.

**Implementation and hosted status:** Implemented/source tested with synthetic edge; physical integration unqualified.

**Automated test source:** `onesa-ai-robot/onesa-ai-robot-backend/tests/test_edge.py`

**Visualization:** [Open diagram](/architecture?diagram=robot-current) · editable source `docs/diagrams/robot-current.mmd`

**Implementation source:** `onesa-ai-robot/onesa-ai-robot-backend/robot_api/edge.py`

### robot-journal — Turso handoff and restart recovery

**Workflow:** robot-journal

**Purpose:** Turso handoff and restart recovery

**Trigger:** Rolling staging deployment or process restart

**Actors:** Existing operator, simulator API, independent SafetyGate and applicable edge/journal

**Preconditions:** Correct environment and bounded validated inputs; enable external integrations only after their own health/isolation checks.

**Authentication and authorization:** Existing configured operator session, strict deployed Origin, CSRF for mutation, independent SafetyGate; edge token/device binding where applicable. No ordinary cloud workflow enables physical actuation.

**Normal sequence:** Login existing operator → stop/drain → fence observed lease → bind next Preview → deploy → recover stopped history

**Data interactions:** Staging remote history/lease; process-local safety and sessions

**Failure paths:** HTTP401, concurrent owner, unavailable journal, active physical/task state

**Retry or recovery:** Do not overwrite another owner; halt deployment on failed proof; preserve history

**Logs and monitoring:** Correlated application errors and applicable audit/metrics; never emit credentials or document contents. Delivered alerts are separately unqualified.

**Security and privacy:** Synthetic staging only until verified processing approval; scope identities and private records; never replay physical commands.

**Implementation and hosted status:** Source ordering/diagnostics verified; hosted handoff blocked at operator login.

**Automated test source:** `onesa-ai-robot/onesa-ai-robot-backend/tests/test_turso.py`

**Visualization:** [Open diagram](/architecture?diagram=robot-current) · editable source `docs/diagrams/robot-current.mmd`

**Implementation source:** `onesa-ai-robot/onesa-ai-robot-backend/robot_api/turso.py`

### robot-safety — Independent command validation and fault recovery

**Workflow:** robot-safety

**Purpose:** Independent command validation and fault recovery

**Trigger:** Any accepted command or watchdog event

**Actors:** Existing operator, simulator API, independent SafetyGate and applicable edge/journal

**Preconditions:** Correct environment and bounded validated inputs; enable external integrations only after their own health/isolation checks.

**Authentication and authorization:** Existing configured operator session, strict deployed Origin, CSRF for mutation, independent SafetyGate; edge token/device binding where applicable. No ordinary cloud workflow enables physical actuation.

**Normal sequence:** Validate authorization/expiry → independent safety gate → execute simulation → stop on fault

**Data interactions:** Safety limits, stop state, command expiry and fault reason

**Failure paths:** Boundary violation, stale authority, connection/persistence loss

**Retry or recovery:** Stop/cancel and explicit fresh authorization for recovery

**Logs and monitoring:** Correlated application errors and applicable audit/metrics; never emit credentials or document contents. Delivered alerts are separately unqualified.

**Security and privacy:** Synthetic staging only until verified processing approval; scope identities and private records; never replay physical commands.

**Implementation and hosted status:** Source tested; real actuators and emergency-stop hardware not assessed.

**Automated test source:** `onesa-ai-robot/onesa-ai-robot-backend/tests/test_simulation.py`

**Visualization:** [Open diagram](/architecture?diagram=robot-current) · editable source `docs/diagrams/robot-current.mmd`

**Implementation source:** `onesa-ai-robot/onesa-ai-robot-backend/robot_api/safety.py`

### robot-ros-contract — ROS2 message interface build

**Workflow:** robot-ros-contract

**Purpose:** ROS2 message interface build

**Trigger:** Isolated Jazzy contract CI

**Actors:** Existing operator, simulator API, independent SafetyGate and applicable edge/journal

**Preconditions:** Correct environment and bounded validated inputs; enable external integrations only after their own health/isolation checks.

**Authentication and authorization:** Credential-free isolated CI; physical deployment is separately authorized.

**Normal sequence:** Build reviewed interface package → validate generated contracts; runtime sensor/VLA/controller integration remains planned

**Data interactions:** Source interface definitions only

**Failure paths:** Contract build failure or incompatible interface

**Retry or recovery:** Reject incompatible artifact; no hardware deployment

**Logs and monitoring:** Correlated application errors and applicable audit/metrics; never emit credentials or document contents. Delivered alerts are separately unqualified.

**Security and privacy:** Synthetic staging only until verified processing approval; scope identities and private records; never replay physical commands.

**Implementation and hosted status:** ROS2 contract CI verified; runtime services/actions and physical loops not implemented.

**Automated test source:** `onesa-ai-robot/onesa-ai-robot-backend/tests/test_edge.py`

**Visualization:** [Open diagram](/architecture?diagram=robot-current) · editable source `docs/diagrams/robot-current.mmd`

**Implementation source:** `onesa-ai-robot/ros2/README.md`

### engineering-ci — Development and automated code/security review

**Workflow:** engineering-ci

**Purpose:** Development and automated code/security review

**Trigger:** dev push or trusted/untrusted PR

**Actors:** Account holder, same-origin frontend, FastAPI, owned database records and configured provider

**Preconditions:** Correct environment and bounded validated inputs; enable external integrations only after their own health/isolation checks.

**Authentication and authorization:** Owner-scoped trusted deployment workflow; production credentials excluded from untrusted PR jobs; actual engineering/privacy/operations gates remain enforced.

**Normal sequence:** Select credential-free jobs → contracts/lint/unit/integration/browser/images → required summary

**Data interactions:** Source, test results and sanitized vulnerability/image manifests

**Failure paths:** Lint/test/contract/security finding, untrusted secret request

**Retry or recovery:** Fail candidate; correct source and rerun exact checks

**Logs and monitoring:** Correlated application errors and applicable audit/metrics; never emit credentials or document contents. Delivered alerts are separately unqualified.

**Security and privacy:** Synthetic staging only until verified processing approval; scope identities and private records; never replay physical commands.

**Implementation and hosted status:** Actual source CI exists; automated review is not independent human review.

**Automated test source:** `onesa-ai-platform/scripts/release/test_evidence.py`

**Visualization:** [Open diagram](/architecture?diagram=delivery-current) · editable source `docs/diagrams/delivery-current.mmd`

**Implementation source:** `onesa-ai-platform/.github/workflows/ci.yml`

### engineering-migration — Schema compatibility and isolated migrations

**Workflow:** engineering-migration

**Purpose:** Schema compatibility and isolated migrations

**Trigger:** Reviewed migration/initialization command

**Actors:** Account holder, same-origin frontend, FastAPI, owned database records and configured provider

**Preconditions:** Correct environment and bounded validated inputs; enable external integrations only after their own health/isolation checks.

**Authentication and authorization:** Owner-scoped trusted deployment workflow; production credentials excluded from untrusted PR jobs; actual engineering/privacy/operations gates remain enforced.

**Normal sequence:** Verify exact database identity and empty/compatible state → controlled transaction → head/role/TLS checks

**Data interactions:** Migration history and schema definitions

**Failure paths:** Identity mismatch, incompatible populated target, elevated runtime role

**Retry or recovery:** Refuse mutation/rollback; preserve real records

**Logs and monitoring:** Correlated application errors and applicable audit/metrics; never emit credentials or document contents. Delivered alerts are separately unqualified.

**Security and privacy:** Synthetic staging only until verified processing approval; scope identities and private records; never replay physical commands.

**Implementation and hosted status:** Staging and production Portal schemas verified; additive governance migration/import and exact production application acceptance remain separately qualified.

**Automated test source:** `onesa-ai-platform/scripts/release/test_evidence.py`

**Visualization:** [Open diagram](/architecture?diagram=delivery-current) · editable source `docs/diagrams/delivery-current.mmd`

**Implementation source:** `onesa-ai-platform/scripts/release/schema_compatibility.py`

### engineering-staging — Exact-source isolated hosted acceptance

**Workflow:** engineering-staging

**Purpose:** Exact-source isolated hosted acceptance

**Trigger:** Authorized staging dispatch

**Actors:** Account holder, same-origin frontend, FastAPI, owned database records and configured provider

**Preconditions:** Correct environment and bounded validated inputs; enable external integrations only after their own health/isolation checks.

**Authentication and authorization:** Owner-scoped trusted deployment workflow; production credentials excluded from untrusted PR jobs; actual engineering/privacy/operations gates remain enforced.

**Normal sequence:** Validate actor/source/target/credentials → one authoritative Preview/API trigger → synthetic integration acceptance → redacted receipt

**Data interactions:** Source/deployment identity and synthetic run-owned records

**Failure paths:** Wrong provider scope, missing credentials, auth/model/storage failure

**Retry or recovery:** Fail qualification; clean/revoke only this run synthetic authority

**Logs and monitoring:** Correlated application errors and applicable audit/metrics; never emit credentials or document contents. Delivered alerts are separately unqualified.

**Security and privacy:** Synthetic staging only until verified processing approval; scope identities and private records; never replay physical commands.

**Implementation and hosted status:** Portal/AI staging pass; Robot HTTP401 remains.

**Automated test source:** `onesa-ai-platform/scripts/test_staging_release.py`

**Visualization:** [Open diagram](/architecture?diagram=delivery-current) · editable source `docs/diagrams/delivery-current.mmd`

**Implementation source:** `onesa-ai-platform/.github/workflows/release-staging.yml`

### engineering-release — Qualification, owner authorization and production promotion

**Workflow:** engineering-release

**Purpose:** Qualification, owner authorization and production promotion

**Trigger:** Owner-authorized exact candidate

**Actors:** Account holder, same-origin frontend, FastAPI, owned database records and configured provider

**Preconditions:** Correct environment and bounded validated inputs; enable external integrations only after their own health/isolation checks.

**Authentication and authorization:** Owner-scoped trusted deployment workflow; production credentials excluded from untrusted PR jobs; actual engineering/privacy/operations gates remain enforced.

**Normal sequence:** Trusted CI/artifact/staging proof → operations/privacy/content evidence → existing owner decision → qualified main deployment

**Data interactions:** Exact commits, hashes, provider IDs and restricted evidence

**Failure paths:** Editable PASS JSON, stale/tampered proof, unqualified dependencies

**Retry or recovery:** Reject candidate; no redundant reviewer requirement or fake approval

**Logs and monitoring:** Correlated application errors and applicable audit/metrics; never emit credentials or document contents. Delivered alerts are separately unqualified.

**Security and privacy:** Synthetic staging only until verified processing approval; scope identities and private records; never replay physical commands.

**Implementation and hosted status:** Source controls implemented; overall production NO-GO.

**Automated test source:** `onesa-ai-platform/scripts/release/test_free_gate.py`

**Visualization:** [Open diagram](/architecture?diagram=delivery-current) · editable source `docs/diagrams/delivery-current.mmd`

**Implementation source:** `onesa-ai-platform/scripts/release/free_gate.py`

### engineering-docs — Classified publication and onboarding

**Workflow:** engineering-docs

**Purpose:** Classified publication and onboarding

**Trigger:** Reviewed docs change/publication

**Actors:** Account holder, same-origin frontend, FastAPI, owned database records and configured provider

**Preconditions:** Correct environment and bounded validated inputs; enable external integrations only after their own health/isolation checks.

**Authentication and authorization:** Owner-scoped trusted deployment workflow; production credentials excluded from untrusted PR jobs; actual engineering/privacy/operations gates remain enforced.

**Normal sequence:** Validate source/contracts/classification → render SVG/PNG/PDF → browser/security checks → protected/public separate deploy → hosted proof

**Data interactions:** Approved source references, searchable classified outputs and revision metadata

**Failure paths:** Broken links, private content in public output, Access denial/bypass

**Retry or recovery:** Reject publish; retain last qualified deployment; onboarding checkboxes are not gates

**Logs and monitoring:** Correlated application errors and applicable audit/metrics; never emit credentials or document contents. Delivered alerts are separately unqualified.

**Security and privacy:** Synthetic staging only until verified processing approval; scope identities and private records; never replay physical commands.

**Implementation and hosted status:** Protected staging published/verified; public Preview qualified; production update pending.

**Automated test source:** `onesa-ai-platform/scripts/docs/test_source_policy.py`

**Visualization:** [Open diagram](/architecture?diagram=docs-access-current) · editable source `docs/diagrams/docs-access-current.mmd`

**Implementation source:** `onesa-ai-platform/scripts/docs/generate.py`

### engineering-recovery — Backup, restore, rollback and incident response

**Workflow:** engineering-recovery

**Purpose:** Backup, restore, rollback and incident response

**Trigger:** Incident/recovery rehearsal

**Actors:** Account holder, same-origin frontend, FastAPI, owned database records and configured provider

**Preconditions:** Correct environment and bounded validated inputs; enable external integrations only after their own health/isolation checks.

**Authentication and authorization:** Owner-scoped trusted deployment workflow; production credentials excluded from untrusted PR jobs; actual engineering/privacy/operations gates remain enforced.

**Normal sequence:** Identify exact release/data scope → use existing isolated restore/lockdown → verify identity/integrity/revocation → explicit recovery/rollback

**Data interactions:** Synthetic recovery fixtures, release manifests and operational runbooks

**Failure paths:** Integrity/schema mismatch, missing encrypted backup, failed alert delivery

**Retry or recovery:** Preserve incident evidence; no destructive live restore; leave unverified gates blocked

**Logs and monitoring:** Correlated application errors and applicable audit/metrics; never emit credentials or document contents. Delivered alerts are separately unqualified.

**Security and privacy:** Synthetic staging only until verified processing approval; scope identities and private records; never replay physical commands.

**Implementation and hosted status:** Source/isolated tools exist; hosted production backup/restore/alerts unqualified.

**Automated test source:** `onesa-ai-platform/scripts/release/test_operational_checks.py`

**Visualization:** [Open diagram](/architecture?diagram=recovery-current) · editable source `docs/diagrams/recovery-current.mmd`

**Implementation source:** `onesa-ai-platform/scripts/release/restore_lockdown.py`

### engineering-decommission — Infrastructure and configuration cleanup

**Workflow:** engineering-decommission

**Purpose:** Infrastructure and configuration cleanup

**Trigger:** Verified redundancy finding

**Actors:** Account holder, same-origin frontend, FastAPI, owned database records and configured provider

**Preconditions:** Correct environment and bounded validated inputs; enable external integrations only after their own health/isolation checks.

**Authentication and authorization:** Owner-scoped trusted deployment workflow; production credentials excluded from untrusted PR jobs; actual engineering/privacy/operations gates remain enforced.

**Normal sequence:** Inventory consumers/data → classify removal impact → verify replacement → retain evidence → authorized bounded removal

**Data interactions:** Resource identifiers/links and cleanup manifest

**Failure paths:** Active dependency, shared database, missing replacement or deletion authority

**Retry or recovery:** Retain/investigate; no premature deletion of running/data-bearing resources

**Logs and monitoring:** Correlated application errors and applicable audit/metrics; never emit credentials or document contents. Delivered alerts are separately unqualified.

**Security and privacy:** Synthetic staging only until verified processing approval; scope identities and private records; never replay physical commands.

**Implementation and hosted status:** Retired staging worker/empty unused DB removed; production worker retained.

**Automated test source:** `onesa-ai-platform/scripts/test_configuration_inventory.py`

**Visualization:** [Open diagram](/architecture?diagram=infrastructure-current) · editable source `docs/diagrams/infrastructure-current.mmd`

**Implementation source:** `onesa-ai-platform/scripts/configuration_inventory.py`
