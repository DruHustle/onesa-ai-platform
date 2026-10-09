# Test strategy

`make check` runs application Ruff/format/strict mypy, script/training lint/format and Pytest.
Ordinary no-database runs separate skipped PostgreSQL tests from CPU successes. `make integration`
uses the dedicated developer `_test` database; the fixture applies real migrations, truncates
owned scratch data, and verifies downgrade/upgrade/metadata consistency.

Backend coverage: configuration/fail-closed serving, liveness/readiness, correlation/error
sanitization, auth/hash/cookies/CSRF/rotation/expiry/throttling, ownership, CRUD/pagination,
ordering/constraints/cascades, mock/vLLM contract errors, lease concurrency/recovery,
actual network-disconnect cancellation, ingestion/pgvector/reindex/source persistence,
tool permissions/deadlines/cancellation/history, invalid model proposals/plans, trip revisions,
body bounds/metrics, dataset validation/tampering/approval and immutable artifact metadata.

`make frontend-check` lints/types/builds Next.js. Playwright uses the real Compose stack for
three desktop/feature/mobile flows. CPU CI includes PostgreSQL, frontend build, OpenAPI,
audits and browser tests; configured remote workflows have not been run here.

No ordinary check downloads weights or starts training. GPU/local-model, semantic embedding,
provider and public production tests are recorded separately as pending, not mocked success.
