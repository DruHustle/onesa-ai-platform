# Infrastructure and release architecture

> Purpose: explain implemented trust boundaries and qualification. Audience: engineers and reviewers. Classification: internal engineering design. Owner: Onesa repository maintainers. Verified: 2026-10-13 against source and cited staging evidence; production acceptance remains incomplete. Applicable revisions are identified below and in generated provenance.

## Current Oracle layout — 2026-10-16

The API hosting migration supersedes the dated Render/worker-only layout below.
The existing Oracle ARM64 VM now runs separate Portal, AI and Robot staging/production
APIs, two Portal workers and one private shared scanner. Two environment-specific
outbound Cloudflare tunnels reach loopback-only APIs. Vercel frontends, external
PostgreSQL/Turso data, private Portal objects and configured AI providers remain
separate. Owner PC administration uses Tailscale and pinned ordinary OpenSSH.

Use [Oracle VM architecture and troubleshooting](../engineering/ORACLE_VM_OPERATIONS.md)
for the service/port map, resource limits, protected file layout, read-only commands,
failure diagnosis, monitoring, backups and recovery boundaries. The
[interactive infrastructure layout](/architecture?diagram=infrastructure-current)
shows the migrated host. Hosting acceptance does not imply every later source release
or ongoing dependency health; current incidents remain in restricted evidence.

The following sections preserve their 2026-10-13 review context; Render references
are historical and are not deployment instructions for the migrated Oracle APIs.

## Authorized targets

Frontend, API, worker, database, private files and model endpoints have distinct configuration scopes. Vercel hosts frontend/static artifacts; Render APIs read only their own runtime settings. Neon application credentials differ from privileged direct migration credentials. Robot SQLite needs a persistent private disk/approved host. Model hosting does not arrive with a Render CPU service.

## Release sequence

Review source and existing working changes. Run source contracts, isolated migrations, classification/security checks, browser verification and reproducible production builds. Push to the authorized review/staging branch after checking triggers. Verify GitHub checks, source SHA, provider deployment ID, logs, liveness, core readiness, inference and actual user paths. Retain rollback paths. Do not deploy production solely because CI passed. Automated repairs are bounded to three attempts per repeated failure.

## Model and storage dependencies

Local Ollama remains loopback development inference. Cloudflare Workers AI is the configured staging generation and embedding provider; native and prior hosted tests passed. vLLM remains an interchangeable future target without a qualified GPU host. Versioned Qwen3 embeddings use the implemented normalized 256-dimensional Matryoshka projection. Production model serving still needs separate scoped configuration and acceptance. Private file storage must survive service restarts; PostgreSQL does not store bucket data automatically. Never publish secret values or provider-specific private hostnames in public artifacts.

## Documentation deployment

The separate onesa-docs Vercel project receives only classified build-public via the manual workflow. Production builds use HTTPS public origins; preview is noindex. The engineering build is packaged separately for Cloudflare Pages with a fail-closed Access JWT verifier. Its Pages staging project now serves the classified engineering build at revision `8c576371`; owner-login/MFA, content and fifteen anonymous origin/preview resource probes passed. Origin and wildcard-preview applications, approved identities, MFA policies and both environment bindings remain verified. Production publication is not inferred. The retained local gateway independently verifies an AI engineering-allowlisted session. Existing domain assignment/TLS/DNS must be inspected rather than guessed. A documentation release does not promote any product backend or frontend.

## Environment and provider status — reviewed 2026-10-13

Portal staging has its own restricted PostgreSQL role, private bucket and healthy Oracle ARM64 executor/scanner. Its corrected staging database/bucket binding passed hosted deployment and acceptance at `5062f7f` (workflow 38328994648), and its Oracle executor runs the same source. The unused credential-free Render staging worker and an empty unreferenced Neon migrations-staging project were deleted after inventory; active/shared databases remain. The production Render worker still has a live deployment and is retained until a qualified Oracle production replacement exists.

AI staging now has a separate Neon project with a restricted role and schema/vector extension. Its existing region is US East 2; only synthetic staging data is permitted until privacy/transfer requirements are verified. Production uses its existing independent Neon target. Fresh hosted acceptance at `8c576371` (workflow 38331890487) passed against that isolated target; historical acceptance before the binding correction is not used as isolation proof.

Robot uses its separate Turso journal only in staging. Remote tasks and an exclusive owner lease persist; process-local sessions/safety never become retained authority. The rolling-deployment handoff ordering fix and redacted diagnostics passed CI. Hosted login currently returns HTTP401 for the configured test credential, before journal changes; operator credential reconciliation is required. The local SQLite production profile requires qualified persistent storage; an ephemeral Free Render filesystem is insufficient.

GitHub-hosted Actions run current checks. The retained isolated local runner is a dormant private-only option, not a prerequisite for PR validation. Private GitHub Free protections cannot be described as enforced. Owner authorization is accepted; technical and privacy gates remain mandatory. [Visual pipeline](/architecture?diagram=delivery-current).


## Private administration boundary

The existing owner PC-to-Oracle Tailscale tunnel carries ordinary pinned OpenSSH administration. Tailnet policy, approved endpoints and OS authentication remain separate from application authorization. No public forwarding, subnet/exit routing or Tailscale SSH is implied; reverify current settings from protected operations evidence. See [Private PC-to-Oracle administration](../operations/TAILSCALE_ADMINISTRATION.md). Private node identifiers and addresses stay out of public artifacts.
