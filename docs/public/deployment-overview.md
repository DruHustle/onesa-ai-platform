# Deployment, configuration and operations overview

## Independent release paths

Each product retains its own frontend/backend builds and repository. GitHub-hosted Actions validate the currently public repositories; local runners are reserved for private repositories after their provisioning and isolation are verified. Release gates distinguish a build, a controlled staging deployment and a public production promotion. There is no automatic application production approval from a documentation release.

Vercel frontends use the appropriate application subdirectory. This documentation site uses a separate `onesa-docs` project and the classified static build from the AI repository. Git-connected deployment is disabled in source configuration; the authorized workflow deploys the reviewed static output. The public URL is `https://docs.onesa.eu`. Private builds must never be uploaded to that project.

## Local development versus staging

Local development uses the repository's locked dependencies and documented application commands. Synthetic fixtures and mock inference are clearly labelled. Staging shares production code, dependency versions and runtime behavior, but uses separate data, credentials, origins, indexing and deployment protection. A temporary preview is not the persistent staging database or worker environment. Different provider capacity limits performance conclusions.

## Configuration boundaries

AI backend configuration uses `ONESA_DATABASE_URL`; Portal uses `DATABASE_URL`. These are distinct databases and secrets. Frontend server proxy configuration is private; do not put database or model credentials into `NEXT_PUBLIC_*`. Environment examples contain placeholders, not working credentials. Model endpoint, model identity, embeddings and private object storage require independently verified settings.

This site uses `ONESA_DOCS_SCOPE=public`, `ONESA_DOCS_STATIC_HOSTING=true`, `ONESA_DOCS_URL=https://docs.onesa.eu` and `ONESA_APPLICATION_URL=https://platform.onesa.eu`. Interactive API execution and documentation assistance are disabled on the static public host. Full operational key inventories and privileged commands belong to the authenticated engineering experience.

## Liveness and readiness

Liveness means the process answers. Core readiness verifies required schema, database connectivity and permissions. Inference readiness verifies the mandatory real model dependency. A missing database must fail honestly. Where implemented, independent non-AI routes remain usable when inference is unavailable. No unconditional healthy response may hide a failed release gate.

## Monitoring and recovery

Operational approval requires actual alert destinations, dependency checks, quota limits, recovery ownership and isolated restore tests. A configured backup option is not proof that a restore works. Database, private object files and Robot SQLite require their own recovery procedures. Retain the reviewed previous release and record deployment revision, artifact hashes and migration compatibility for rollback. Do not run uncontrolled load tests or restore experiments against production.

Public status descriptions do not expose private service IDs, hostnames, credentials, restricted schema details or incident records. Internal manuals describe implementation and procedures; deploying those requires the authenticated gateway.
