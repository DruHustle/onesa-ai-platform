# Independent application deployment

> Current private-Free release policy: [safeguards and external owner authorization](../development/PRIVATE_FREE_SAFEGUARDS.md). Legacy JSON approval is retired; native protection requirements below apply only to a verified supported configuration.

Use separate versioned images from the frontend/backend Dockerfiles. Each build context
is independent. Keep a common origin through TLS ingress; the Next.js server forwards
API traffic using private `ONESA_API_URL`. Backend PostgreSQL/pgvector, inference and
metrics endpoints remain private. Inject secrets at runtime from a secret manager.

Reference production/staging templates: `compose.production.yaml`, `compose.staging.yaml`,
`infra/deployment/*.env.example`, and the detailed
[production guide](../deployment/PRODUCTION_DEPLOYMENT.md). These are templates, not a
claim of qualified target-host deployment. Development/staging may use a labelled mock; production refuses mock and development
inference endpoints and requires an authenticated HTTPS model service.

Validate without printing secrets: `docker compose --env-file .env.production -f
compose.yaml -f compose.production.yaml config --quiet` (one command). Supply an
approved hostname, least-privilege application database role, separate migration-owner
credentials, secure cookies, model access settings and private metrics token. Apply
reviewed migrations once before rolling out the API; frontend can roll out independently
when contracts remain backward compatible. Readiness endpoints: backend core `/core-ready`, model `/ready`,
frontend `/ready`. Exercise login, CSRF, streaming and ownership isolation after rollout.

Before promotion: successful exact-revision CI, reviewed ownership/privacy decisions,
target-host TLS/load/retention/alerts, approved model licenses and restore verification.
Keep prior images and backward-compatible database migrations for rollback. Never use
`docker compose down -v` as a rollback. Robot integration does not belong in this core.

`release-images.yml` manually selects frontend/backend, checks successful CI and exports
an image candidate; it does not upload to a registry or deploy. A separately approved
production environment/release process must approve promotion after these checks, including `publication-hygiene`.
For the authorized Vercel/Render target, use the GitHub deployment workflow and
[provider setup guide](VERCEL_RENDER.md). GPU work and training require their own scope.


### 2026-10-10 release-candidate delta

Backend packaging now pins Python3.11.17 Alpine3.24 by manifest digest and build-only uv0.13.0 by digest. No pip/setuptools/wheel/uv is shipped in the web runtime; real retrieval, inference clients and Linux PDF seccomp remain. Additive SQL stores hold bounded upload chunks, invitation/reset hashes and persistent encrypted mail work plus shared admission leases. Identity worker command is `python -m app.identity_worker`; provisioning/real delivery need scoped approval. Browser5MiB documents use512KiB authenticated chunks through same-origin BFF; no public storage URL. Invitation policy is explicit configuration, not automatically enabled or existing-user eligibility. Core readiness/database and model readiness are separate; production real authenticated HTTPS inference remains unverified. Source/API/docs classification and existing local models/data are preserved. Release remains NO-GO; exact local evidence and unapplied provider delta are restricted under docs/internal/release-audit.


## Staging-first hosted AI direction — 2026-10-10

Before applying a Blueprint, review [HOSTED_AI_PROPOSAL](HOSTED_AI_PROPOSAL.md)
and [HOSTED_AI_CONFIGURATION](HOSTED_AI_CONFIGURATION.md). Historical root
render.yaml names an alternative database; do not create that and the proposed
staging/production databases together. Reuse a verified isolated AI resource first.
No paid plan, endpoint, staging service creation or production promotion is approved
by a checked-in example. Credential values belong only in scoped provider secrets.


Owner free-only direction supersedes paid provisioning examples. Follow
[FREE_STAGING_SETUP](FREE_STAGING_SETUP.md) and staging.env.example; no paid
Blueprint/application or production release is approved by an example.
