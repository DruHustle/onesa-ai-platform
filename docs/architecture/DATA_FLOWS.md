# Data flows

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
