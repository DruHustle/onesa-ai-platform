# Migrations

The current single migration head is `20261025_twins`, matching
`REQUIRED_SCHEMA_REVISION` in `app/database.py`. The ordered chain is:

| Revision | Scope |
| --- | --- |
| `58c65932c572` | Chat, authentication and rate buckets |
| `2b1d6757a609` | Documents and pgvector |
| `608f3f79f76e` | Agent history and travel |
| `20261010_identity` | Invitations, recovery, access grants and durable identity mail |
| `20261010_uploads` | Bounded uploads and chunks |
| `20261010_capacity` | Shared model-admission leases |
| `20261021_industrial` | Owned industrial investigation evidence |
| `20261025_twins` | Owned equipment, files/model revisions, sources, readings/events and notes |

The knowledge migration creates the vector extension if needed; its downgrade leaves
that extension for other consumers. The identity, upload and capacity migrations
deliberately reject automatic downgrade: use a reviewed forward recovery plan.
Industrial and Twin migrations also preserve evidence through forward recovery.
The Twin schema is additive. Default-off applications retain their previous compatible
readiness revisions; enabling Twins requires the new head and private persistent files.
Back up and restore those files together with PostgreSQL before hosted activation.

```sh
cd onesa-ai-platform-backend
# Lists local migration scripts; does not connect to a database.
../.venv/bin/python -m alembic heads
# Supply ONESA_DATABASE_URL privately for an explicitly approved target first.
../.venv/bin/python -m alembic current
../.venv/bin/python -m alembic upgrade head
../.venv/bin/python -m alembic check
```

Compose runs a one-shot migrate service before API startup. Readiness verifies the expected
revision constant in app/database.py; update it when adding migrations. Generate a new
revision with autogenerate, inspect it, and include required type imports (pgvector) and
extension changes explicitly. Never replace migrations with create_all in production.

Migration and metadata consistency tests use an isolated PostgreSQL database.
Destructive downgrade tests, where supported, require ONESA_TEST_DATABASE_URL whose
name ends `_test`; they do not override the forward-only migrations above.
Back up operational data before applying incompatible migrations. Never downgrade a live
primary just to test rollback; use a restored database and a version-compatible release.
