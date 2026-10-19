# Separate application builds and tests

> Current pipeline: [automated review, staging qualification and owner activation](../development/CI_CD_PIPELINE_REPORT.md). Prepared local changes are not live deployments; branch/PR optimization and automatic technical evidence supersede older manual-only details.

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

`apps/chat/tests/startup.spec.ts` uses synthetic browser network fixtures for initial
rendering, the eight-second session-check deadline and cancellation, connection retry
without a page reload, optional document loading and deferred Markdown rendering. It
runs with the ordinary `test:e2e` CI suite. For a targeted local check, build first with
`npm --prefix onesa-ai-platform-frontend run build`, start the resulting frontend on
an isolated loopback port, then run
`ONESA_BROWSER_URL=http://127.0.0.1:<port> npm --prefix onesa-ai-platform-frontend/apps/chat run test:e2e -- tests/startup.spec.ts`.
These fixture checks qualify prepared source behavior; they do not measure hosted
startup latency or establish a production deployment. See
[Performance checks](../testing/PERFORMANCE_TESTS.md) for the startup boundaries.

The Chat image install uses a BuildKit npm download cache, locked integrity checks,
and explicit bounded fetch retries/timeouts. It omits installation-time audit/funding
requests; the separate mandatory CI npm audit and final-image vulnerability/secret gates
remain required. A failed install remains a failed build; no whole-job retry is implied.

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
`tls-acceptance`. Add `publication-hygiene` to required checks. CI runs relevant main/staging PR checks and full release-source push checks, with fail-closed summaries. No remote
CI success is implied by local build/test results.

## API contracts

From the repository root, install the separate locked contract tools before generating
or checking contracts. The Chat dependency installation does not install these tools.

```sh
npm ci --ignore-scripts --prefix scripts/contract-tools
make openapi api-client contract-check
```

Use the local backend environment; generation never requires a production API or
database credential.

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

## Reproducible external-review index

From the AI repository, run `python3 scripts/release/review_package.py --workspace .. --output docs/internal/release-audit/external-review/<new-review-id>`. Optionally supply the approved `--public-build` and protected `--internal-build` directories. The collector reads independent repository identities, source routes, API operations and workflow hashes; it never contacts providers, reads environment values or authorizes release. The resulting mode-600 manifest and SHA256SUMS preserve source/build classifications, dirty-source limits and unmatched route-test status. Give the external reviewer this restricted index together with the existing deployment/security/recovery evidence, exact Actions run links and read-only reproduction commands. `READY_FOR_INDEPENDENT_REVIEW` describes package availability; the reviewer verdict remains pending.

The compatibility `qualify.py decision` command rejects all retired editable approval JSON. Actual release decisions use the existing trusted qualification and owner-controlled promotion workflows.

## Travel authentication and draft protection

`apps/chat/tests/travel-drafts.spec.ts` requires a loopback frontend and intercepts
API transport with synthetic fixtures. It verifies authentication before inviting work,
trip/app/history navigation, pending-save locking, failed saves, same-account session
renewal, different-account isolation and late optional Docs membership responses. It
performs no model inference and must not run against hosted data. Use the existing
Playwright command with this filename and the required browser projects.

The draft registry is mounted in the application layout; it keeps editable values in
component memory. History state stores only a position. Refresh/exit protection uses
the browser's supported beforeunload prompt; explicit discard and completed saves
clear the guard. Authentication returns to the original task; an expired submission
is not replayed. Real synthetic backend/staging qualification remains a separate gate.

## Usability probes and unsaved work

The hosted timing probe restores each input's original value after proving it is
editable, including when its observation callback fails. It must not leave a
synthetic Travel draft and then accidentally test the discard guard as a navigation
benchmark. `scripts/usability-draft.cjs` owns that cleanup; it does not bypass dialogs,
authentication, draft protection or timing limits. The local Travel regression checks
both clean-baseline navigation and continued protection of a genuine unsaved edit.
Only fixed step/matcher labels enter failure diagnostics; never log input values,
credentials or raw assertion messages. Passing local controls does not authorize a
hosted retry or establish production performance.
