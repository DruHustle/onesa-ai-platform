# Fifteen guided development and operations procedures

Version 0.2.0 · internal engineering · 2026-10-09. These steps use existing software. Screenshots are actual synthetic application views; NVIDIA procedures are preparation, not target-host verification. Use [troubleshooting](../public/troubleshooting.md) for application errors and [recovery](../operations/RECOVERY.md) for operational failures.

## 1. Install local development prerequisites

Install Docker/Compose, Python 3.11 and Node 24. In a fresh checkout run `make install`, `npm --prefix onesa-ai-platform-frontend/apps/chat ci` and `npm --prefix onesa-ai-platform-frontend/apps/docs ci`. Do not replace existing private configuration. Run `python3 scripts/bootstrap_env.py` only when .env does not exist. Expected: pinned dependencies install and bootstrap creates mode-0600 configuration. See [local development](LOCAL_DEVELOPMENT.md).

## 2. Start the application

Set matching ONESA_CHAT_PORT and ONESA_PUBLIC_ORIGIN in private .env; this checkout uses 3100. Run `make up-docs`, then `docker compose ps`. Expected: migration exits successfully, API is healthy and the application sign-in loads. Use `make down` to preserve volumes. Never use `down -v` for routine shutdown.

## 3. Create a development account

Open the application, choose Create an account, enter synthetic display name/email and a strong development password. Submit. Expected: the authenticated Chat view replaces the sign-in form. Existing cookies establish identity; no token is placed in a URL. [Authentication](../api/AUTHENTICATION.md).

![Synthetic registration interface](/generated/screenshots/registration.png)

## 4. Start the first conversation

Choose New conversation, enter a short prompt and send it. Inspect the backend badge before interpreting the result. Expected: response deltas arrive and a completed assistant message is saved. Select the conversation again to verify history. Stop during generation to check cancellation; incomplete assistant output is not saved.

![Actual Chat and history](/generated/screenshots/chat.png)

## 5. Connect installed Ollama

For this already qualified checkout run `.venv/bin/python scripts/local/ollama_service.py status` and, if stopped, `start`. Run `curl http://127.0.0.1:11434/api/version`. Configure the existing backend connection described in [Ollama setup](../models/OLLAMA_SETUP.md) and restart with `make up-docs`. Expected: native server is loopback-only and authenticated model discovery reports Ollama. No additional weights are downloaded by these steps.

## 6. Select and inspect the inference model

Review private ONESA_MODEL_BACKEND, ONESA_MODEL_NAME and ONESA_MODEL_CONTEXT_LENGTH configuration. This installation uses the qualified Qwen3 4B tag and 8192 context. Apply configuration through `make up-docs` and inspect the Chat inference badge and authenticated GET /api/v1/models. Expected: configured identifier/backend appear. There is no multi-model selection screen; configuration selects the model. Unknown usage is null, not invented. [Serving architecture](../models/LOCAL_INFERENCE.md).

## 7. Use Knowledge retrieval

Open Knowledge, upload a synthetic TXT or PDF within the 5 MiB limit, and search a phrase it contains. Expected: an owned document appears with attributed matching excerpts. Optionally attach its ID to Chat through the supported request contract. Current vectors are a labelled lexical baseline. [Schema](../database/SCHEMA.md).

![Knowledge upload and search](/generated/screenshots/knowledge.png)

## 8. Configure agent permissions

Open Agents; enter `Count the words in: hello local model`. Explicitly grant the text-statistics tool and run. Expected: bounded execution reaches completed and shows its tool result. Repeat without a grant: requested execution must fail safely. Model output cannot grant tools. Real planning may fail validation; a failure is not a successful run. [Agent design](../design/AGENT_DESIGN.md).

![Agent grant and execution](/generated/screenshots/agents.png)

## 9. Create an itinerary

Open Travel, enter Berlin and two days, and create a plan. Expected: a typed itinerary is saved with revision 1; subsequent revisions retain ownership. Generated suggestions have no verified live availability, prices or booking authority.

![Saved travel itinerary](/generated/screenshots/travel.png)

## 10. Make an API request

Follow [validated Python/TypeScript/cURL examples](../public/examples.md). Login establishes session and CSRF cookies. Use the same development Origin, retain cookies and supply X-CSRF-Token for mutations. GET /api/v1/models should return model metadata for an authenticated caller. Expected: valid response or the documented authentication error; never bypass authorization. The [API explorer](/api-explorer) is read-only unless an explicit loopback execution environment is configured.

## 11. Deploy the local containers

Run `docker compose -f compose.yaml -f compose.docs.yaml up --build -d`. Inspect readiness with `docker compose ps`. Expected: private database/API services and one published loopback application port. Use the protected Python gateways for internal documentation; never serve its build as unrestricted static files. [Documentation security](../development/DOCUMENTATION_SYSTEM.md).

## 12. Prepare NVIDIA/vLLM

On the intended approved Linux host, inspect `nvidia-smi` and run `.venv/bin/python scripts/diagnostics/check_gpu.py`. Follow [vLLM deployment](../models/VLLM_DEPLOYMENT.md) for driver/toolkit compatibility, immutable model revision, private endpoint and Compose GPU profile. Expected before qualification: configuration and hardware inventory only. Successful startup, memory measurements and inference require that host. These Mac checks do not establish NVIDIA compatibility; starting the GPU profile may download weights and is a separate authorized operation.

## 13. Run migrations

Normal startup runs the existing migrate service before API readiness. On a configured development database, `docker compose run --rm migrate alembic current` shows the revision and `docker compose run --rm migrate alembic upgrade head` applies pending revisions. Expected: current equals the repository head. Verify backups and review changes before operational upgrades; do not test downgrades on operational data. [Migration architecture](../database/MIGRATIONS.md).

## 14. Run the tests

Run `make check` for lint, format, types and CPU tests. Start the dedicated onesa-platform-test-db and run `make integration`; the configured database name must end in _test. Run `make frontend-check`, `make docs-check` and `make docs-browser`. Original Chat browser tests require an isolated mock stack; real.spec.ts requires ONESA_REAL_INFERENCE=1. Expected: exact passed/skipped results are recorded; a skipped integration is not a verified database check. [Test strategy](../testing/TEST_STRATEGY.md).

## 15. Back up and restore

Run `scripts/database/backup.sh data/backups/backup-YYYY-MM-DD.dump` with a fresh filename, then `scripts/database/restore.sh data/backups/backup-YYYY-MM-DD.dump onesa_new_restore`. Expected: private custom-format dump, a new isolated database and a matching migration head/content review. The restore script refuses existing database names and never overwrites the primary. Do not promote without a reviewed operational procedure. [Full backup guide](../database/BACKUP_RESTORE.md).

[Interactive checklists](/checklists) store progress locally and do not certify infrastructure validation.
