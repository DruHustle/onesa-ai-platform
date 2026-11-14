# Integration tests

Use ONESA_TEST_DATABASE_URL for a dedicated database ending `_test`. Tests truncate users/
rate buckets with cascades and downgrade all schema tables; the suffix guard prevents
accidental ordinary primary use. `make integration` supplies the explicitly isolated local
container default documented in LOCAL_DEVELOPMENT.md. No SQLite fallback is used.

The suite runs real PostgreSQL/pgvector migrations, relationships/constraints/ownership,
API auth/content/RAG/agents/trips and actual HTTP disconnect cleanup via a temporary Uvicorn
socket. Browser tests hit the real Next.js→API→database→mock path through Compose.

CI includes a PostgreSQL/pgvector service and separate container/browser job. Local migration
round-trip, full backend and three browser flows pass. Remote CI execution is not claimed.
Use snapshot copies/test namespaces for destructive migration and restore checks.
