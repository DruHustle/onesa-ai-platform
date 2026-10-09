# Migrations

Alembic revisions: `58c65932c572` chat/auth/rate buckets; `2b1d6757a609` documents/pgvector;
`608f3f79f76e` agent history/trips. Knowledge migration creates the vector extension if
needed; downgrade removes tables/indexes and leaves the extension for other consumers.

```sh
cd onesa-ai-platform-backend
ONESA_DATABASE_URL=postgresql+psycopg://... ../../.venv/bin/alembic upgrade head
ONESA_DATABASE_URL=postgresql+psycopg://... ../../.venv/bin/alembic check
```

Compose runs a one-shot migrate service before API startup. Readiness verifies the expected
revision constant in app/database.py; update it when adding migrations. Generate a new
revision with autogenerate, inspect it, and include required type imports (pgvector) and
extension changes explicitly. Never replace migrations with create_all in production.

Upgrade/downgrade/metadata consistency tests pass on the isolated PostgreSQL database.
Destructive downgrade tests require ONESA_TEST_DATABASE_URL whose name ends `_test`.
Back up operational data before applying incompatible migrations. Never downgrade a live
primary just to test rollback; use a restored database and a version-compatible release.
