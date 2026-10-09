# ADR 0001: Platform baseline

Date: 2026-10-09. Status: adopted engineering baseline; future capabilities remain proposed.

## Context

The workspace is empty. The user selected a reusable self-hosted platform, a
Phase A/Phase B strategy, and a starter stack, with incremental continuation.
The attachment uses another repository name; the explicit destination is authoritative.

## Decision

Use this `onesa-ai-platform` monorepo. Start with a FastAPI modular API and mock
ModelClient, then Next.js Chat, PostgreSQL/SQLAlchemy/Alembic, and SSE. Real local
inference uses a separate private vLLM service with configurable Qwen weights.
Later RAG uses pgvector; training uses PyTorch/Transformers/PEFT/TRL and separate
artifacts. Do not create unused package skeletons, Kubernetes, Redis, or robotics.

M1 authentication will use Argon2id passwords and random opaque server-side
sessions. Store only session-token hashes. Cookies are HttpOnly, Secure in
production, SameSite=Lax; enforce same-origin checks and CSRF tokens on mutations,
including login/register defenses. Logout revokes the session; refresh rotates
credentials transactionally. Do not store credentials in localStorage.

## Consequences

Applications do not depend on model-specific behavior. CPU development stays light.
PostgreSQL integration requires an available local/container database; GPU verification
requires NVIDIA Linux hardware. Documentation/status determine the next work item.
Auth implementation must verify expiry, revocation, CSRF, throttling, and user isolation.

## Alternatives

External paid inference conflicts with local-first requirements. A service for each
module adds premature deployment complexity. JWT-only auth complicates immediate
revocation. SQLite can aid isolated tests but cannot substitute for PostgreSQL
migration/integration acceptance. No project software license is inferred from model licensing.
