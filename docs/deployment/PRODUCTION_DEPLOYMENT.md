# Production deployment — template, not an executed release

Configure an owned domain/DNS, reviewed secrets, GPU/embedding endpoints and deployment
resources first. `.env` must be private and excluded from source control. Set ONESA_DOMAIN,
a 32+ character metrics credential, and Secure cookie/HTTPS settings. Apply migrations
with the owner role, then provision a separate CRUD application role using
scripts/database/create_app_role.sql and a privately supplied password. Set
ONESA_APP_DATABASE_URL to that restricted role. Production readiness rejects a superuser
application connection; development owner credentials are not a production default. The production
API refuses missing HTTPS/cookie/database/metrics configuration.

```sh
docker compose -f compose.yaml -f compose.production.yaml config --quiet
# After operator deployment review on the intended server:
docker compose -f compose.yaml -f compose.production.yaml up --build -d
```

Caddy terminates same-origin TLS and proxies the web service. Database/API are private;
web has no direct host port in the production override. App containers use non-root users,
read-only filesystems/tmpfs, dropped capabilities and no-new-privileges. Caddy volumes hold
certificate state. Keep metrics on the internal network with a bearer credential.
No real DNS/certificate/TLS/public deployment was performed in this session.

Before a release: restore backups in a new database; review migration compatibility;
measure authenticated/model load, memory and failure recovery on target resources;
capacity-tune ingress auth throttling; isolate hostile PDF parsing; establish retention,
monitoring/alerts, independent security review and CSP; verify real inference/embeddings.
The local health probe is not production load qualification.

Roll back using a known code/image/model revision and compatible restored database;
never assume a destructive schema downgrade preserves user data. No domains or accounts
are invented and no external services are deployed automatically.

European deployment: choose application, database/volume, backups, inference, embeddings and
future provider locations/ownership according to the actual residency requirements. Existing
configuration does not enforce geography. Record private network and transfer/egress paths,
provider access/subprocessors and key custody. Review organizational GDPR responsibilities and
EU AI Act applicability separately from software controls; see AI_SOVEREIGNTY.md and
security/PRIVACY_AND_DATA_PROTECTION.md. No funding or certification claim is implied.

## Reproducible split deployment and rollback

Build contexts are the application directories, each with its own Dockerfile.
The frontend image uses runtime `ONESA_API_URL`; public documentation links are
build arguments. Root Compose preserves `onesa-platform`/`postgres-data` and port
3100. Caddy routes `/api/v1/*`, `/health`, `/ready` directly to API with immediate
flushing; all other requests go to chat. No response encoding is enabled at this
proxy. Both direct ingress and the alternative BFF are locally regression-tested.
The BFF deadline defaults to 135 seconds, above the backend's maximum generation
deadline. Tune `ONESA_PROXY_TIMEOUT_SECONDS` and upstream ingress deadlines together.

Separate environment examples are in `infra/deployment`. Actual TLS staging should
use separate secrets/namespace/storage with production controls; the HTTP loopback
`compose.staging.yaml` tests container hardening, routing and restart but does not
qualify TLS, Secure cookies, target hardware or staging alert delivery. Run its two
origins sequentially with matching ONESA_PUBLIC_ORIGIN, never weaken Origin checks.

```sh
ONESA_MODEL_BACKEND=mock ONESA_PUBLIC_ORIGIN=http://localhost:3120 \
  docker compose -p onesa-platform-split -f compose.yaml -f compose.staging.yaml up --build --wait
ONESA_BROWSER_URL=http://localhost:3120 npm --prefix onesa-ai-platform-frontend/apps/chat run test:e2e -- tests/chat.spec.ts
# Recreate API with origin 3121 to exercise the BFF, then:
ONESA_MODEL_BACKEND=mock ONESA_PUBLIC_ORIGIN=http://localhost:3121 \
  docker compose -p onesa-platform-split -f compose.yaml -f compose.staging.yaml up --wait
.venv/bin/python scripts/verify_restart.py
```

CI now packages frontend/backend separately and validates container startup and
contracts. The manual release-image workflow produces a selected reviewable image
artifact, without registry publication or production deployment. Configure a reviewed
deployment workflow with protected environments, approved immutable digests and
recorded readiness gates before any production release. No remote workflow was run.

Rollback baseline: `baseline/platform-split-20261009`, commit `1ea8d54`.
Pre-split local images are tagged `onesa-platform-api:pre-split-20261009` and
`onesa-platform-chat:pre-split-20261009`. In a separate baseline checkout create a
private `.env` from the preserved operator configuration and point a local Compose
override at those images with `pull_policy: never`. Use `--no-build` so the baseline
images are not replaced. Keep project name `onesa-platform` and its existing volume;
stop migrated application services first for a deliberate rollback. Explicitly keep
the original docs-source mounts or rebuild the baseline portals/gateways in the chosen
checkout. Native inference paths must continue pointing at the preserved root data.
Do not delete/reset the migrated working tree or replace .env while reviewing the split.
This migration needs no schema downgrade. For data recovery, restore the private dump
into a new `_restore` database, verify fingerprints, and approve promotion separately.
The isolated backup restore and service restart were rehearsed; baseline-image rollback and forward recovery were subsequently tested on the isolated
split stack with the same authenticated session and persisted conversation. Use
`infra/deployment/rollback.yaml` and `scripts/verify_restart.py --rollback` to repeat.
Main-service rollback was deliberately not performed.

## Acceptance 005 result and promotion boundary

The newer `ACCEPTANCE_STAGING.md` documents an actually running isolated local TLS environment,
including Secure cookies, restricted DB roles, local Prometheus/Alertmanager delivery,
encrypted scheduled backups, measured load, real native inference and image rollback.
Its PASS results supersede the earlier template-only limitations for those local checks.
They do not verify this production host, its public certificate, its network or NVIDIA hardware.
Read `development/PRODUCTION_ACCEPTANCE_REPORT.md` and
`security/LEGAL_PRIVACY_DECISIONS.md` before considering a release.

The manual candidate-image workflow now requires successful checks for the exact source
revision before independently packaging either application. It records source/image identity;
it does not publish a registry image or deploy. Remote CI execution has not occurred in this
local session. A production owner must approve all deployment/security/operations/legal gates,
select immutable image/model revisions, confirm compatible schema, complete target-host smoke
and restore tests and explicitly authorize promotion. Maintain the previous images and verified
snapshot for rollback. No public promotion command was executed during acceptance 005.
