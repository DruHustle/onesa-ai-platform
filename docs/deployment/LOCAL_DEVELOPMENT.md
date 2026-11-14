# Local development

Full platform: Docker/Compose, `python3 scripts/bootstrap_env.py`, then `make up`.
Bootstrap writes a new mode-0600 .env with random URL-safe database/model/metrics secrets
and refuses to overwrite existing configuration. Change both web port and public Origin
when using a different local port. `make down` preserves the PostgreSQL volume; never
use down -v as a routine restart. Database/API/inference have no public ports by default.

Host checks use Python 3.11 and a pinned virtual environment:

```sh
make install
make check
npm --prefix onesa-ai-platform-frontend/apps/chat ci
make frontend-check
make openapi
```

Host frontend checks passed with installed Node 20.20.1; use Node 24 LTS for new environments
and the pinned Node container for deployment. Python 3.12/3.13 are declared but unverified.
`make run` runs the API on loopback; full business APIs additionally need an
exported ONESA_DATABASE_URL pointing to migrated PostgreSQL. It does not automatically
load `.env`. `npm --prefix onesa-ai-platform-frontend/apps/chat run dev` proxies to local API unless ONESA_API_URL changes.

## Isolated integration database

```sh
docker run -d --name onesa-platform-test-db \
  -e POSTGRES_USER=onesa -e POSTGRES_PASSWORD=onesa-test-only \
  -e POSTGRES_DB=onesa_test -p 127.0.0.1:55432:5432 pgvector/pgvector:pg16
make integration
```

These credentials are for the isolated disposable test database only. Override
ONESA_TEST_DATABASE_URL for CI/another dedicated `_test` database. Integration tests
truncate data and run downgrade/upgrade; never point them at operational data.
If no test URL is supplied to ordinary `make check`, 21 PostgreSQL tests are skipped;
`make integration` sets the isolated developer default. No SQLite substitution is claimed.

Browser tests require a running migrated stack and Chromium:

```sh
cd onesa-ai-platform-frontend/apps/chat
npx playwright install chromium
ONESA_BROWSER_URL=http://localhost:3101 npm run test:e2e -- tests/chat.spec.ts
```

The original chat.spec.ts suite expects mock on an isolated stack (3101 above).
For this real stack use ONESA_REAL_INFERENCE=1 ONESA_BROWSER_URL=http://localhost:3100
and `npm run test:e2e -- tests/real.spec.ts`. Keep native Ollama running; see
[setup](../models/OLLAMA_SETUP.md). Change browser URL with the configured port. Screenshots/backups/load output live in
ignored `data/`. Ordinary checks download no model weights and require no NVIDIA hardware.
Dependency updates: edit pins, pip-compile runtime lock, regenerate dev pins without editable
paths, npm install with exact versions, run checks/audits and update OpenAPI/docs/handoff.

ONESA_UI_LOCALE selects the default installed interface catalog (en or de). The language selector
can override it with a non-sensitive preference cookie. German currently covers navigation/sign-in;
workspace and API text remains English. This is independent of model-language evaluation.
