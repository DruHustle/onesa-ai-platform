# Infrastructure and release architecture

## Authorized targets

Frontend, API, worker, database, private files and model endpoints have distinct configuration scopes. Vercel hosts frontend/static artifacts; Render APIs read only their own runtime settings. Neon application credentials differ from privileged direct migration credentials. Robot SQLite needs a persistent private disk/approved host. Model hosting does not arrive with a Render CPU service.

## Release sequence

Review source and existing working changes. Run source contracts, isolated migrations, classification/security checks, browser verification and reproducible production builds. Push to the authorized review/staging branch after checking triggers. Verify GitHub checks, source SHA, provider deployment ID, logs, liveness, core readiness, inference and actual user paths. Retain rollback paths. Do not deploy production solely because CI passed. Automated repairs are bounded to three attempts per repeated failure.

## Model and storage dependencies

Local Ollama remains loopback development inference. Hosted vLLM is a preferred proposed runtime but has no approved real endpoint. Embeddings require their own approved model/version/dimensions and actual service tests. Private file storage must survive service restarts; PostgreSQL does not store bucket data automatically. Never publish secret values or provider-specific private hostnames in public artifacts.

## Documentation deployment

The separate onesa-docs Vercel project receives only classified build-public via the manual workflow. Production builds use HTTPS public origins; preview is noindex. Private assets remain behind the engineering gateway. Existing domain assignment/TLS/DNS must be inspected rather than guessed. A documentation release does not promote any product backend or frontend.
