# Troubleshooting

Port occupied: change ONESA_CHAT_PORT and matching ONESA_PUBLIC_ORIGIN; leave unrelated
services running. Verification used 3100 because 3000 was occupied.

403 Origin/CSRF: use the exact configured browser origin (localhost and 127.0.0.1 differ),
ensure CSRF cookie/header are current after refresh, and use HTTPS with Secure cookies in
production. 401: sign in again; session may be expired/revoked/disabled. 429: wait for the
auth minute bucket and assess trusted ingress capacity configuration.

503 readiness: inspect `docker compose logs migrate api db`, migration head and model
health. Run Alembic upgrade via migrate, not destructive table creation. 409 conversation
busy: wait for current completion/deadline; expired leases recover on the next chat request.
Generation error: inspect private model health/configuration and token context; no silent mock fallback.

Upload 415/422/413: use UTF-8 .txt or unencrypted text PDF <=100 pages, <=5 MiB upload and
<=256k extracted characters. Scanned PDFs/OCR are not supported. Duplicate document: use
reindex, not duplicate import. Embedding incompatibility: dimension is fixed at 256 and
version must match; change dimension only with a schema migration/reindex.

Docker denied in sandbox: request appropriate local daemon access; never report container
execution without evidence. GPU unavailable: CPU/mock workflows remain usable, real inference
is pending. Test database absent: configure the explicit isolated `_test` database; skips are
not successful PostgreSQL verification. See status/handoff for actual results and limitations.
