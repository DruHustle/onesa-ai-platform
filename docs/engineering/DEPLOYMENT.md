# Independent application deployment

## Security releases and permanent branches

Keep dev, staging and main as the only permanent branches. Temporary Dependabot
security-fix PRs and reviewed security release candidates are allowed. Security updates
target the actual GitHub default branch (currently main); ordinary version-update settings
for dev do not change that behavior. Keep automatic security-fix generation, alerts,
scans and owner notifications; ordinary version PR creation remains limit 0.

Review fixes through credential-free hosted PR checks and normally integrate on dev,
then staging and main. For urgent remediation when dev contains unfinished work,
construct the candidate from exact current production plus the reviewed fix only.
Qualify it in existing isolated staging, bind tests/artifacts/approval to that source,
use owner-controlled production release, then reconcile into dev and staging. No new
permanent environment, blind auto-merge, deployment secrets in bot jobs or unsafe
pull-request triggers are permitted. Cleanup temporary branches only after confirmed
incorporation and review of evidence/artifact/rollback dependencies. A green bot check
is not authorization to ship unrelated dev work or skip operations/privacy gates.

The [CI/CD runbook](CI_CD.md) records the implemented staging/main guards and the
conditional urgent procedure. Direct qualification from a temporary branch when
staging contains unrelated unfinished work is not implemented. Preserve that work
and report the limitation; never reset staging or weaken exact-source checks.

## Reviewed staging path — 2026-10-12

After dev review and exact merged staging CI pass, use the registered owner bridge: `gh workflow run deploy.yml --ref staging -f target=staging -f fixture_mode=temporary`. Existing Staging-only credentials and approved synthetic scope/project fixture JSON are required. Temporary identities use random private credentials and two-hour grants; cleanup expires those exact grants and revokes their sessions. Provided credentials remain available with `fixture_mode=provided`. No production identities or migrations are changed.

Vercel Git owns the protected exact-source staging Preview; Actions verifies that Preview and manually deploys the backend. Actual inference, embedding, streaming, user isolation and storage acceptance remain mandatory. Mock/local UI tests do not qualify hosted model readiness or production. Public documentation Preview uses the independent `docs-hosting.yml` workflow and scoped external release described in the CI/CD runbook. Internal documentation uses the authenticated gateway or the existing all-path Cloudflare Access Pages project; actual approved engineering identity and MFA acceptance must qualify that separate protected release. Internal site artifacts are excluded from public hosting and public Actions uploads.

The existing hosted producer also requires real conversation context/history, persisted source citations, bounded uploads, model-planned permitted tools, Travel creation/revision/conflict and owner isolation, and active cancellation. Browser acceptance covers all seven protected routes at desktop/tablet/mobile in both system modes, with live draft/focus/session preservation and an actual active stream and Stop. Source/run/origin binding, real-model metadata and complete browser coverage are checked by the receipt reader; absent, partial or foreign evidence fails closed. Temporary credentials stay in private runner files and are revoked after probes. Travel live data and bookings, manual Safari and screen-reader review remain outside the demonstrated synthetic scope.

For a specifically authorized context-response investigation, the same
`release-staging.yml` dispatcher accepts `context_diagnostic=true`,
`deployed_commit=<full already-live staging SHA>` and `fixture_mode=temporary`.
This mode requires successful exact workflow-source CI, the owner, first attempt
and a disposable GitHub-hosted staging runner. It verifies the still-live Render
revision, unchanged backend/chat/client/lockfile source, protected Vercel Preview
and its actual running origin before creating the existing two temporary fixtures.
It makes at most two application inference requests (acknowledge, recall), retains
structural outcomes only, and uses the existing unconditional fixture revocation.
It does not deploy, rebind configuration, alter the model or create qualification
evidence. Its short-lived `staging-context-diagnostic` artifact cannot replace
`staging-verification`; ordinary full qualification remains unchanged. Reserve
requests in the current restricted authorization/attempt register before dispatch;
failure consumes the submitted requests and permits no automatic retry.

Public Docs keyboard acceptance waits for Docusaurus's actual hydration marker
before its single Enter/menu check. Missing hydration fails within ten seconds.
The isolated static-build regression holds JavaScript to reproduce visible SSR
markup without working React handlers; no repeated key presses are used to turn a
failed interaction into acceptance.

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
