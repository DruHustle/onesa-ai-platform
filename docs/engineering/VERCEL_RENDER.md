# Vercel frontend and Render backend

Staging accepts the current Vercel Standard Protection API value
`prod_deployment_urls_and_all_previews`, as well as existing protected modes.
Missing or unknown protection still blocks Preview configuration/deployment.
See [Vercel Authentication](https://vercel.com/docs/deployment-protection/methods-to-protect-deployments/vercel-authentication).

Production remains unqualified. The existing isolated staging deployment and its
verified provider evidence are recorded in `AI_CONFIGURATION_INVENTORY.md`.
Use the private `onesa-ug/onesa-ai-platform` GitHub repository and `main`. The frontend and
backend remain separate release units. Grant the providers access only to the required
organization repositories. Deploy through `.github/workflows/deploy.yml`, dispatched from GitHub Actions.

For isolated AI staging, dispatch `repair-hosting.yml` on branch `staging` with
`staging_action=deploy-staging`. It requires successful exact-revision CI/hygiene,
uses the protected GitHub **Staging** environment, builds Vercel Preview with
staging-only `ONESA_API_URL` and `NEXT_PUBLIC_ONESA_DOCUMENTATION_URL`, verifies the
existing Neon schema/restricted role and deploys only the identified free Render
staging service. Migration and automation-bypass credentials remain private in that
environment. The workflow verifies real hosted security, restart persistence,
bounded idle staging-connection recovery and responsive/accessibility checks.

## Vercel

Create project `onesa-ai-platform` with Next.js, Node 24, root directory `onesa-ai-platform-frontend/apps/chat`,
install `npm ci` and build `npm run build`. Configuration is in that root's
`vercel.json`. For the AI frontend enable inclusion of source outside the project root
for its shared API client within the frontend directory. Production branch: `main`.
Deploy a protected preview first, using one stable HTTPS hostname for authentication;
do not send production credentials to arbitrary preview deployments.

Set server-only backend origin: `BACKEND_URL` for the portal, `ONESA_API_URL` for AI,
using the actual Render HTTPS URL. Cookies/CSRF/Origin pass through the frontend BFF;
do not use cross-site cookies or expose database/model credentials to JavaScript.
Portal additionally needs `PUBLIC_ORIGIN`, `SITE_URL` and matching server-only
`PROXY_SHARED_KEY`. Supply `NEXT_PUBLIC_MAX_UPLOAD_BYTES=3145728` at build time.
AI route duration is 150 seconds for bounded streamed generation; verify plan limits.

## Render

`render.yaml` configures Docker services with app-only build contexts, private
PostgreSQL, Frankfurt region, readiness checks and disabled native auto-deploys. Templates
use paid always-on resources: review actual pricing/capacity before applying. No
resources or charges are created by storing this file. Databases disable public IP
access by default; allow only an approved temporary operator address if external
migration access is needed, and remove it afterwards.

Create/provision database schema with a separate migration-owner identity; then supply
only a restricted application URL in Render's secret environment settings. Do not use
a managed database owner's connection string directly as the web application's role.
Render user-creation permissions must be checked; if SQL CREATE ROLE is unavailable,
use a provider-supported scoped user and equivalent grants. Application readiness is
the final privilege check. Owner credentials must not remain in API/worker environments.

Portal uses a Render API and background worker with a shared encrypted private S3
bucket and encryption key. Supply scoped bucket credentials privately; do not attach
separate ephemeral local storage to the two services. Configure SMTP and scanner as
approved integrations; without scanning, uploaded PDFs stay quarantined. Company
facts and legal/editorial gates remain unapproved until the owner verifies them.

AI uses PostgreSQL/pgvector and a restricted database URL with `postgresql+psycopg://`.
Apply Alembic migrations using owner credentials, enable vector, and grant CRUD while
keeping `alembic_version` read-only. Set actual `ONESA_PUBLIC_ORIGIN`, secure cookies
and generated metrics token. Production configuration refuses mock inference;
local Mac Ollama is not reachable from Render. Supply a qualified authenticated
remote Ollama/vLLM endpoint and model before claiming a live AI service. No model is
downloaded or trained by deployment.

## Provider limits and promotion

Vercel function payloads are limited to 4.5 MB, including request encoding; the
configured 3 MiB file limit leaves room for base64/multipart overhead. Larger uploads
or downloads require a separately implemented signed object-storage delivery path.
Streaming, login/MFA, Secure cookie/CSRF, ownership, private files, DB role restrictions,
worker queues, backups/restore and rollback must pass on the actual target before
production promotion. Provider deployment does not approve corporate claims/privacy
notices. Keep public data-collection gates closed until the owner completes them.

Sources: [Vercel monorepos](https://vercel.com/docs/monorepos),
[function limits](https://vercel.com/docs/functions/limitations),
[duration](https://vercel.com/docs/functions/configuring-functions/duration),
[Render Blueprint fields](https://render.com/docs/blueprint-spec),
[monorepo roots](https://render.com/docs/monorepo-support),
[pgvector](https://render.com/docs/postgresql-extensions).

## GitHub deployment setup

One-time provider setup is required: import this private GitHub repository into Vercel,
configure the frontend root above and its production environment, and create the
Render Blueprint services, private database and backend secrets described above.
Disable Vercel Git auto-deploys and retain Render `autoDeployTrigger: off` so GitHub
Actions owns releases. Initial provider provisioning may create an initial deploy;
keep it access-protected until target checks pass.

Store the following secrets in each repository's Actions secrets. The organization
currently uses GitHub Free; private repositories cannot consume organization secrets
or deployment environment secrets on that plan. These commands prompt privately; never put credential values in command
history or chat. Vercel IDs must belong to the configured project/team. Render API
access must belong to the service owner's workspace.

```sh
gh secret set VERCEL_TOKEN --repo onesa-ug/onesa-ai-platform
gh secret set VERCEL_ORG_ID --repo onesa-ug/onesa-ai-platform
gh secret set VERCEL_PROJECT_ID --repo onesa-ug/onesa-ai-platform
gh secret set RENDER_API_KEY --repo onesa-ug/onesa-ai-platform
gh secret set RENDER_BACKEND_SERVICE_ID --repo onesa-ug/onesa-ai-platform
gh workflow run deploy.yml --repo onesa-ug/onesa-ai-platform --ref main -f application=both
gh run list --repo onesa-ug/onesa-ai-platform --workflow deploy.yml
gh run watch RUN_ID --repo onesa-ug/onesa-ai-platform --exit-status
```

The workflow refuses a branch other than main or a commit without successful push CI
and publication-hygiene checks. Frontend and backend jobs remain independently selectable.
Vercel builds the checked-out commit with production provider settings; Render receives
that exact SHA and is polled until live, with commit verification. Render deploy failure
or timeout fails the workflow. Check service logs and health before retrying; roll back
using provider controls to a previously qualified release if needed. No provider tokens,
database URLs or application secrets belong in the repository.

## Final release qualification — 2026-10-09

Prepared configuration is not a hosted deployment. Production promotion additionally
requires the exact-commit `RELEASE_QUALIFICATION_JSON` Actions secret with all four
reviewed gates passing and a matching source fingerprint. The local audit decision
is NO-GO. Do not supply a passing attestation until target, operations and content
approvals actually exist. See restricted `docs/internal/release-audit/` evidence.

Render AI health checks now use `/core-ready`: DB/core failures are unhealthy, while
optional inference outage reports degraded without causing restart storms. `/ready`
still verifies inference. Node runtime images exclude build-only package managers;
run compiled Node migration/worker entry points, not `npm`, inside runtime containers.


## Domain configuration — 2026-10-10

Owner selected `platform.onesa.eu` for the AI chat frontend. The production example
now uses this exact `ONESA_PUBLIC_ORIGIN`; Vercel `ONESA_API_URL` remains the actual
Render API URL. Company and private administration use `onesa.eu` and
`portal.onesa.eu` in the independent portal repository. Future robot host is
`robot.onesa.eu`; the robot application is not implemented. Provider assignments,
DNS/TLS qualification and production delivery remain pending; populated `.env`,
models, indexes, cookies and API contracts were not changed. No push/deploy here.

### Read-only hosting diagnosis

Run `gh workflow run inspect-hosting.yml --ref main` in this repository to check
the existing Render services and Vercel project using the configured Actions
secrets. The workflow never changes provider settings, deploys code, creates
resources or prints environment values. Inspect its log for required configuration
presence, root/health-path matches and the provider's deployment commit. A successful
diagnostic job means the inspection ran; it does not establish healthy deployment.
Production deployment still requires a reviewed exact-commit qualification record.

`gh workflow run repair-hosting.yml --ref main` repairs the existing service layout
and absent nonsecret configuration, then reads it back. Repository and runtime
identity must match before any update. This does not deploy or migrate the database;
missing database/model credentials and qualification remain explicit blockers.


## Current AI staging deployment

The exact staging revision a25bfb02a46101aaa3afd74bfc51ce371b3d1673 passed CI and hosted deployment workflow 38105826742. Render uses Dockerfile CMD with its command override cleared; /health and /core-ready return 200. Hosted authentication, account isolation, CSRF and restart persistence passed 39 checks; protected Preview passed 15 desktop/tablet/mobile checks. This resolves the staging exit-127 startup fault. /ready remains an honest 503 because no approved model endpoint exists. Real semantic embeddings, worker delivery and public production acceptance remain unqualified. Subsequent releases must pass current-revision CI and the staging workflow again.

## Automated qualification migration

See [automated release qualification](AUTOMATED_QUALIFICATION.md) for immutable
Actions evidence, explicit owner reviews, build integrity and the guarded migration.
The legacy secret remains active until remote migration verification is complete.
