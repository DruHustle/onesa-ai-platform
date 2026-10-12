# Infrastructure and release architecture

## Authorized targets

Frontend, API, worker, database, private files and model endpoints have distinct configuration scopes. Vercel hosts frontend/static artifacts; Render APIs read only their own runtime settings. Neon application credentials differ from privileged direct migration credentials. Robot SQLite needs a persistent private disk/approved host. Model hosting does not arrive with a Render CPU service.

## Release sequence

Review source and existing working changes. Run source contracts, isolated migrations, classification/security checks, browser verification and reproducible production builds. Push to the authorized review/staging branch after checking triggers. Verify GitHub checks, source SHA, provider deployment ID, logs, liveness, core readiness, inference and actual user paths. Retain rollback paths. Do not deploy production solely because CI passed. Automated repairs are bounded to three attempts per repeated failure.

## Model and storage dependencies

Local Ollama remains loopback development inference. Cloudflare Workers AI is the configured staging generation and embedding provider; native and prior hosted tests passed. vLLM remains an interchangeable future target without a qualified GPU host. Versioned Qwen3 embeddings use the implemented normalized 256-dimensional Matryoshka projection. Production model serving still needs separate scoped configuration and acceptance. Private file storage must survive service restarts; PostgreSQL does not store bucket data automatically. Never publish secret values or provider-specific private hostnames in public artifacts.

## Documentation deployment

The separate onesa-docs Vercel project receives only classified build-public via the manual workflow. Production builds use HTTPS public origins; preview is noindex. The engineering build is packaged separately for Cloudflare Pages with a fail-closed Access JWT verifier. Its Pages project currently has only a harmless staging placeholder. Origin and wildcard-preview applications, approved identities, MFA policies and both environment bindings have been verified; fifteen anonymous probes redirect to Access login. Owner-login and content acceptance remain pending before private upload. The retained local gateway independently verifies an AI engineering-allowlisted session. Existing domain assignment/TLS/DNS must be inspected rather than guessed. A documentation release does not promote any product backend or frontend.

## Environment and provider status — reviewed 2026-10-13

Portal staging has its own restricted PostgreSQL role, private bucket and healthy Oracle ARM64 executor/scanner. Its corrected staging database binding needs a new API deployment and hosted acceptance. The unused credential-free Render staging worker and an empty unreferenced Neon migrations-staging project were deleted after inventory; active/shared databases remain. The production Render worker still has a live deployment and is retained until a qualified Oracle production replacement exists.

AI staging now has a separate Neon project with a restricted role and schema/vector extension. Its existing region is US East 2; only synthetic staging data is permitted until privacy/transfer requirements are verified. Production uses its existing independent Neon target. The prior hosted AI test did not establish provider-level database isolation; fresh acceptance against the corrected staging target is required.

Robot uses its separate Turso journal only in staging. Remote tasks and an exclusive owner lease persist; process-local sessions/safety never become retained authority. A rolling-deployment handoff fix is source-verified but awaits hosted execution. The local SQLite production profile requires qualified persistent storage; an ephemeral Free Render filesystem is insufficient.

GitHub-hosted Actions run current checks. The retained isolated local runner is a dormant private-only option, not a prerequisite for PR validation. Private GitHub Free protections cannot be described as enforced. Owner authorization is accepted; technical and privacy gates remain mandatory. [Visual pipeline](/architecture?diagram=delivery-current).
