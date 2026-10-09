# Operations runbook

From repository root with private .env: `make up`; inspect `docker compose ps` and
`docker compose logs migrate api db chat`. Restart app service with `docker compose restart api`
or chat; do not delete volumes. Configuration changes require `up -d` recreation, not restart.
Only the loopback web port is published; API health is reachable through the web proxy.

On 503: verify database health/schema head/model discovery. On SSE error: confirm private
model configuration and available context; no mock fallback. A cancelled/failed generation
retains the user turn without a completed partial assistant; an expired lease allows retry.
On stale agent run: inspecting an unfinished run older than 15 seconds classifies it failed.
No durable task queue exists.

Back up before migrations/upgrades and verify restore into a new database. Stop via `make down`
to preserve data. Select known-good code/image/model revisions for rollback; never use down -v
or schema downgrade as casual troubleshooting. Production runbook requires actual host/TLS/
secret/monitoring/resource review; the template was not externally deployed.
