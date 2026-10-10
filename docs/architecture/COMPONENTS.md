# Components

Onesa AI is European-based, general-purpose and applicable to European and international
markets. Shared services have no geographic routing or country/language whitelist.
African/regional use cases are optional specializations. See ADR 0003 and AI_SOVEREIGNTY.md.

| Code | Responsibility |
| --- | --- |
| app/config.py | Validated environment; production requires HTTPS/Secure cookies/database/metrics credential |
| app/database.py, models.py | PostgreSQL engine, sessions, schema and required migration revision |
| app/auth.py | Argon2id, opaque session cookies, CSRF, rotation/revocation, throttling |
| app/conversations.py | Owned/paginated CRUD, row locks, busy-state protection |
| app/chat.py | Public model alias, user persistence, lease, SSE, completion/failure cleanup |
| app/inference.py | Shared mock/Ollama/vLLM streaming, health and request-owned usage |
| app/knowledge.py | Size/type checks, text/PDF extraction, chunking, embeddings, pgvector/search/reindex |
| app/agent_runtime.py, agents.py | Planner/registry interfaces, permitted bounded tools and owned execution history |
| app/travel.py | Typed itinerary planner, saved trips, optimistic revisions, unavailable-provider reporting |
| app/limits.py, observability.py | Total body limit, safe logs, request IDs, protected metrics |
| onesa-ai-platform-frontend/apps/chat/src | Chat/Knowledge/Agents/Travel pages in one Next.js deployment |
| training/ | Dataset, config, evaluation, guarded training and immutable candidate registry |
| scripts/ | Bootstrap, OpenAPI, tests, hardware/serving checks, backups/restores and load probe |

GPU model execution, semantic embedding service, real travel providers, distributed job
queues, object-storage adapters and robotics integrations are not implemented deployments.

onesa-ai-platform-frontend/apps/chat/src/lib/i18n.tsx supplies English/German navigation/sign-in catalogs and a persisted
non-sensitive preference; server layout reads a validated preference/ONESA_UI_LOCALE. Other
workspace text remains English. training/pipeline.py accepts extensible language/domain metadata;
registry.py adds logical profiles/provenance/evaluation evidence; evaluate.py adds optional paired
base regression reporting. These are additive extensions with stable API/database contracts.

## Repository and release boundaries

The `onesa-ai-platform` Git root contains the independently buildable frontend and
backend. `onesa-company-portal` and `onesa-ai-robot` have separate Git roots/history;
none requires a workspace-level repository or sibling source at build time. The
organization remotes are private and initially empty. Primary branch is `main`.
Governance and publication gates are documented in the root `AGENTS.md`; generated
internal/public manuals remain a tracked-history review blocker. Candidate packaging
is manual per application and is separate from approved deployment.
