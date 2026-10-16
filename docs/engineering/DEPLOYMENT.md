# Independent application deployment

## Oracle backend migration — owner authorized 2026-10-16

The owner now authorizes moving the existing staging and production APIs from Render
to the existing Oracle worker VM. This supersedes the backend-deployment pause for
this migration only. Keep qualification active; the Render billing hold itself remains.
Preserve the existing worker/scanner services, BaSyx, databases, credentials, accounts,
stored content, Robot history and physical-controller restrictions. Frontends stay on
Vercel; migrate only their server-side backend origin when the new target qualifies.

`compose.oracle-backend.yaml` defines independent staging/production API profiles.
Images must be ARM64, scanned, source-labelled and pinned by immutable image ID.
Each environment has separate networks, runtime files and (where used) storage volumes.
Ports bind only to loopback; no public API/container/database/SSH port is opened.
The existing PC-to-VM Tailscale SSH route remains an administrative connection.
Use an explicitly configured Cloudflare HTTPS tunnel for API ingress, retaining
application authentication/CSRF/ownership checks and existing Access/WAF protections.
No wildcard ingress or privileged crawler/session bypass is permitted.

Keep matching private runtime values in root-owned mode-600 files under
`/etc/onesa/backends/`; never copy them into Git or Actions. Preserve each environment's
original database, origin, key and inference/storage settings. Build from credential-free
Git archives off the VM and record exact backend tree, source commit, image ID,
archive digest and scan results in existing restricted evidence. The image map uses
`ORACLE_STAGING_IMAGE`, `ORACLE_PRODUCTION_IMAGE` and their corresponding `_COMMIT`
variables; both image values must be immutable `sha256:` IDs already loaded on the VM.

Run isolated config checks first, then deploy only the named staging service with
`docker compose --env-file <private-image-map> -f compose.oracle-backend.yaml
--profile staging up -d --no-build staging` (one command). Record healthy readiness,
private anonymous denial, authenticated workflows and measured host/container capacity.
An unavailable service or uncertain Robot journal lease stops activation; never repair
history through SQL or force an active lease. Reuse valid exact-source application
qualification and perform target-specific migration acceptance; local/config tests
alone are not hosted acceptance. Do not conceal a known application failure as PASS.

Only after the applicable staging/source/preservation gates pass, run the corresponding
explicit `--profile production ... production` command, then change the matching
frontend backend-origin binding and verify the deployed frontend revision and API.
Do not use `compose down`, restart workers, run migrations automatically, delete old
services, rotate credentials, provision paid capacity or change unrelated domains.
Keep the prior frontend/backend configuration and images for rollback. Render is
currently suspended: restoring its old URL is configuration rollback, not recovery of
service availability. On failure stop promotion and retain the actual partial state.

Staging has lower CPU shares/limits than production. Observe memory/OOM/error counters
and latency alongside the existing scanner and workers; a short idle sample does not
qualify peak load. Existing backups/monitoring remain active. Public documentation must
not publish the private runtime files, host inventory, source layouts or audit records.


## Render capacity hold — local maintenance, 2026-10-16

The owner confirms Render credits are exhausted and Render deployments remain paused.
Do not dispatch staging qualification that deploys to Render or request a Render recovery build,
resume a suspended service, change billing or provision paid capacity during this hold.
Continue non-deploying qualification and the authorized Oracle migration above. Preserve the
existing source-bound hosted results; they do not establish current API availability.
A restored Render budget is required before another Render build. Oracle migration
acceptance follows the source, staging, preservation and owner controls above.

The maintained deployment script now requires `suspended: not_suspended` and an
explicit empty `suspenders` list before creation and again when observing `live`.
Missing, malformed, contradictory or suspended service metadata blocks success;
a deployment's `live` status alone is insufficient. This check does not resume,
cancel or recreate a deployment. No availability failure is authentication evidence.
The staging producer also applies this check before reading runtime configuration
or requesting deployment. Offline regression: `python3 -m unittest discover -s
scripts/release -p test_render_availability.py` (one command).
These changes are prepared on development source; no new hosted release is claimed.
Rollback: revert only the reviewed maintenance commit, retaining existing receipts
and the owner-directed deployment pause.

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

The Cloudflare generation adapter uses the configured model's native
`/ai/run/<model>` endpoint and reads only string `choices[].delta.content`.
The compatible endpoint emitted numeric content deltas during a synthetic
context-recall investigation; converting those values to strings loses leading
zeroes. Native responses can also contain a duplicate `response` field, which is
ignored. Malformed choices still fail, reasoning is not exposed as answer text,
and no provider/model fallback or automatic inference retry is introduced.
See [Cloudflare's model interface](https://developers.cloudflare.com/ai/models/%40cf/qwen/qwen3-30b-a3b-fp8/).
Protocol regressions and one bounded real strict-parser diagnostic passed; only
the complete exact-source hosted workflows can qualify the application release.

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
