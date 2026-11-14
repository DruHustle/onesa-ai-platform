# Data flows

> Current hosted status, reviewed 2026-10-13: [visual workflows and evidence limits](../ecosystem/VISUAL_WORKFLOWS.md). Workers AI staging generation/semantic embeddings and Oracle staging jobs/scanning are verified. Corrected database targets need new hosted acceptance; production, private documentation Access and physical hardware remain separately gated. Earlier dated milestone evidence below does not supersede this readback.

Onesa AI is European-based, general-purpose and applicable to European and international
markets. Shared services have no geographic routing or country/language whitelist.
African/regional use cases are optional specializations. See ADR 0003 and AI_SOVEREIGNTY.md.

Authentication: browser Origin → auth throttle → Argon2id verification → hashed opaque
session and CSRF representation → HttpOnly session/readable CSRF cookies. Mutations
require matching configured Origin and session-bound CSRF header. Refresh rotates under
a row lock; logout revokes and clears cookies. GET me returns safe user fields only.

Chat: authenticated request → ownership and row lock → lease/busy check → optional
owned-document retrieval → commit user/run → stream deltas → commit complete assistant
and source metadata → message_end. Failure/timeout/disconnect records failed/cancelled
run and clears lease; partial assistant text is not successful history. Expired leases
allow recovery after process death. No transaction is held throughout generation.

Knowledge: bounded multipart upload → UTF-8/PDF validation → extracted text/checksum →
chunk batches → selected embedding adapter → versioned vectors → transaction commit.
Search embeds the question, filters documents by user/version, then returns bounded
cosine-ranked excerpts. Reindex computes new embeddings before deleting the old index.
Document deletion cascades chunks; previously saved chat answers/sources remain history.

Agents: caller grants local tool names → explicit steps or bounded planner proposal →
allowlist/schema checks → 2-second tool calls inside a 10-second execution deadline →
owned run/step outcomes. Cancellation is cooperative between bounded calls; no external
side effects exist in the initial registry. Planner text cannot grant permissions.

Travel: preferences → shared-model or mock planner → typed consecutive-day validation →
structured JSONB trip. Revision generates outside the write lock, then compares the
expected version under a row lock. Missing/live providers return unavailable; no booking.

Training: reviewed/provenance-labelled examples → normalization/deduplication/PII screen
→ deterministic isolated splits/checksums → config dry-run → separately authorized CUDA
training → checkpoint/adapter/experiment → held-out evaluation → immutable candidate
registry. No automatic promotion and no ingestion of private user chats for training.

Amendment 001: dataset language/domain labels flow into manifests and candidate profile metadata;
base and candidate predictions can be paired on the same general/domain held-out cases. Reports
and config hashes accompany adapter hashes. No profile name initiates deployment/promotion.
Interface locale preference only selects UI copy; it never changes model routing or authorization.

Milestone 2: successful chat messages retain safe inference metadata and actual reported
input/output tokens, latency and first-text timing. Request-owned accounting prevents
concurrent requests sharing usage. Missing token counts stay null. Protected generation
metrics have bounded backend/outcome labels. Next.js compression is disabled so SSE
deltas reach clients during generation; browser disconnect propagates upstream.


Account controls: exact Origin/CSRF → shared authentication throttle for password
proofs → user/session locks and fresh revocation checks → profile/password/session
mutation. Password changes revoke every old token and issue a replacement cookie.
Account export takes a repeatable-read, owner-scoped bounded snapshot and excludes
credentials/vectors/internal telemetry. Account deletion rejects active runs and
cascades owned live data, including embeddings, in one transaction. No external
backup-retention processing is implied. A cancelled agent whose row disappears
returns a safe not-found result instead of an uninitialized outcome.


## Domain configuration — 2026-10-10

Owner selected `platform.onesa.eu` for the AI chat frontend. The production example
now uses this exact `ONESA_PUBLIC_ORIGIN`; Vercel `ONESA_API_URL` remains the actual
Render API URL. Company and private administration use `onesa.eu` and
`portal.onesa.eu` in the independent portal repository. Future robot host is
`robot.onesa.eu`; the robot application is not implemented. Provider assignments,
DNS/TLS qualification and production delivery remain pending; populated `.env`,
models, indexes, cookies and API contracts were not changed. No push/deploy here.


### 2026-10-10 release-candidate delta

Backend packaging now pins Python3.11.17 Alpine3.24 by manifest digest and build-only uv0.13.0 by digest. No pip/setuptools/wheel/uv is shipped in the web runtime; real retrieval, inference clients and Linux PDF seccomp remain. Additive SQL stores hold bounded upload chunks, invitation/reset hashes and persistent encrypted mail work plus shared admission leases. Identity worker command is `python -m app.identity_worker`; provisioning/real delivery need scoped approval. Browser5MiB documents use512KiB authenticated chunks through same-origin BFF; no public storage URL. Invitation policy is explicit configuration, not automatically enabled or existing-user eligibility. Core readiness/database and model readiness are separate; production real authenticated HTTPS inference remains unverified. Source/API/docs classification and existing local models/data are preserved. Release remains NO-GO; exact local evidence and unapplied provider delta are restricted under docs/internal/release-audit.

Staging infrastructure follow-up (owner direction 2026-10-10): reuse an existing
qualified AI-specific Render database if found; otherwise prepare separate staging
and production PostgreSQL proposals without provisioning or selecting a paid plan.
The diagnostic workflow now inventories AI-named database candidates and the actual
backend region without retrieving connection credentials. Hosted vLLM and semantic
embedding infrastructure remain blocked pending a costed, approved host; preserve
native Ollama and local data. Database/core readiness now requires an actual current
schema even in development; `/health` stays process liveness, while `/core-ready`
may remain available during an inference outage only with a healthy database.
