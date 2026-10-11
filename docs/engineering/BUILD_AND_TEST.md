# Separate application builds and tests

Use Node 24 and Python 3.11. The existing Makefiles describe supported dependency installs.

## Frontend (repository root)

```sh
npm --prefix onesa-ai-platform-frontend run ci
npm --prefix onesa-ai-platform-frontend run lint
npm --prefix onesa-ai-platform-frontend run typecheck
npm --prefix onesa-ai-platform-frontend run build
docker build -t onesa-chat:local onesa-ai-platform-frontend
```

`ONESA_API_URL=http://127.0.0.1:8000 npm --prefix onesa-ai-platform-frontend run dev`
starts the frontend on 3100. Set this server-only API origin at runtime. The Docker
context includes the chat app and typed client; it excludes the documentation app.
Public/internal docs have separate generation/access controls in the parent Makefile;
use `npm --prefix onesa-ai-platform-frontend run docs:ci` and `make docs-assets
 docs-public docs-internal docs-validate` as one command without a line break.
Regenerate ignored public/internal manuals in CI; do not commit them.

## Backend (backend directory)

```sh
make install
make check
make test
docker build -t onesa-api:local .
```

Alternatively from the repository root: `make install check`. For development use
`make run` in the backend directory. Backend has an independent Dockerfile, Python
package, migrations and runtime example. Training/evaluation are separate optional
workloads; no model download or training is part of an application build.

Tests without `ONESA_TEST_DATABASE_URL` skip real database cases. Full integration
needs an isolated PostgreSQL/pgvector database named with `_test`; tests truncate its
users. Use the existing integration guide before running `make integration`. Browser
checks use an isolated mock stack, not the active application or a real inference service.
See `docs/deployment/LOCAL_DEVELOPMENT.md` and `ACCEPTANCE_STAGING.md` for complete gates.

Existing CI jobs: `backend`, `frontend`, `browser`, `documentation`, `containers`,
`tls-acceptance`. Add `publication-hygiene` to required checks. CI runs on all pushes and pull requests so required jobs can report consistently. No remote
CI success is implied by local build/test results.

## Identity worker lifecycle

Run `python -m app.identity_worker` from the backend environment with the same
scoped database and mail settings as the API. SIGTERM/SIGINT stops new claims,
lets the current bounded delivery attempt complete, and closes its connection pool.
`--once` claims at most one eligible job; `--max-jobs 20` bounds one scheduled run
and exits immediately when no work is currently eligible. Retries remain durable
and require a subsequent invocation. Provider acceptance does not prove delivery.
These modes prepare a scheduler integration; no hosted worker or delivery is
qualified merely by enabling the command. Keep scheduler secrets server-side.


After building the backend production image, run
`python3 scripts/startup_smoke.py onesa-api:local`. This exercises Dockerfile CMD,
installed Uvicorn/factory, provider PORT, liveness, missing dependency 503, SIGTERM,
and distinct production configuration failure using isolated containers. CI runs it
against the final backend security candidate image; it does not qualify inference.
