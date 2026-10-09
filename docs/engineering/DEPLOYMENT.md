# Independent application deployment

Use separate versioned images from the frontend/backend Dockerfiles. Each build context
is independent. Keep a common origin through TLS ingress; the Next.js server forwards
API traffic using private `ONESA_API_URL`. Backend PostgreSQL/pgvector, inference and
metrics endpoints remain private. Inject secrets at runtime from a secret manager.

Reference production/staging templates: `compose.production.yaml`, `compose.staging.yaml`,
`infra/deployment/*.env.example`, and the detailed
[production guide](../deployment/PRODUCTION_DEPLOYMENT.md). These are templates, not a
claim of qualified target-host deployment. Mock inference remains the default unless
an explicitly configured and qualified inference service is supplied.

Validate without printing secrets: `docker compose --env-file .env.production -f
compose.yaml -f compose.production.yaml config --quiet` (one command). Supply an
approved hostname, least-privilege application database role, separate migration-owner
credentials, secure cookies, model access settings and private metrics token. Apply
reviewed migrations once before rolling out the API; frontend can roll out independently
when contracts remain backward compatible. Readiness endpoints: backend `/ready`,
frontend `/ready`. Exercise login, CSRF, streaming and ownership isolation after rollout.

Before promotion: successful exact-revision CI, reviewed ownership/privacy decisions,
target-host TLS/load/retention/alerts, approved model licenses and restore verification.
Keep prior images and backward-compatible database migrations for rollback. Never use
`docker compose down -v` as a rollback. Robot integration does not belong in this core.

`release-images.yml` manually selects frontend/backend, checks successful CI and exports
an image candidate; it does not upload to a registry or deploy. A separately approved
production environment/release process must approve promotion after these checks, including `publication-hygiene`.
No production deployment, publication, GPU work or training is authorized here.
