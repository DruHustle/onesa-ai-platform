# Separate application builds and tests

`node --test scripts/docs/cloudflare-access.test.mjs` checks the protected Pages
worker with synthetic signed identities. Generated Mermaid sources must retain
their exact bytes and private headers while overriding Pages' karaoke MIME type
with UTF-8 plain text. Denied identities cannot reach assets; error responses and
unrelated asset types retain their provider MIME type. Hosted byte and MIME
verification remains mandatory for each new private Docs artifact.

Hosted UI receipts are created privately and exclusively before the unchanged
owner probe reads them. The credential-free receipt regression runs the actual
Python reader against Node-created files, including a permissive-writer negative
control, existing-file preservation and simultaneous independent writers. These
local checks do not qualify a hosted release.

`python3 -m unittest discover -s scripts/release -p test_oracle_docs_build.py`
and `python3 -m unittest discover -s scripts/docs -p test_build_evidence.py`
verify genuine build/local-check custody separately from owner hosted acceptance.
They reject run ID zero as an Actions run, source/context drift, failed or skipped
checks, changed bytes, expiry and attempts to grant authority from local results.
No provider or production credentials are used by these tests.

The owner frontend fixture injects a conflicting production default and verifies
explicit Preview selection before staging dispatch. A wrong provider target retains
the one-create intent and refuses acceptance. Actual pinned CLI protocol fixtures
also exercise the explicit staging argument with synthetic loopback-only services.
These controls use no provider credentials and do not establish hosted acceptance.

Installer fixtures also place disposable custody under the private home directory
when executed as root. The explicit writable-parent regression still requires the
production verifier to reject shared writable ancestors; no custody guard changes.

Run `python3 -m unittest discover -s scripts/ci -p test_browser_dependencies.py`
for the disposable GitHub-runner browser preparation boundary. The helper selects
`https://archive.ubuntu.com/ubuntu/` for noble, noble-updates and noble-backports,
and `https://security.ubuntu.com/ubuntu/` for a separate noble-security stanza.
Selection requires the exact `mirror+file:/etc/apt/apt-mirrors.txt` URI, canonical
Ubuntu Signed-By identity and reviewed public-key bytes, and bounded Deb822 fields. Unknown,
duplicate, mixed, malformed or authentication-relaxing input fails before writes;
legacy active mirror indirection also fails. Comments, continuations and line
endings follow the [Ubuntu Noble source format](https://manpages.ubuntu.com/manpages/noble/en/man5/sources.list.5.html),
with ambiguous inline comments refused. Only the affected URI and Signed-By path
values change; all other source bytes are preserved.
The unused mirror list is neither read nor modified, and disabled validated stanzas
remain disabled. Existing source/config custody, signed package verification,
timeouts, retries and fatal repository-update errors remain required.

The observed hosted image made the canonical keyring root-owned but mode `0777`.
The helper never changes its bytes or mode, and APT is not rebound to that writable
file. A single no-follow, nonblocking descriptor captures at most 3608 bytes after
validating regular-file metadata, one link, root ownership/group, mode `0644` or
the observed `0777`, and exact size 3607. The captured buffer must match SHA-256
`80a36b0a6de2f69f49d2df75ef473ccde121e9e190b9ea01d20a4f63778d5c31`.
Only those bytes can be copied to
`/etc/apt/onesa-ci-keyrings/ubuntu-noble-2023.11.28.1.gpg`. Its held directory
ancestry must be root-owned, non-writable by group/others and traversable by APT;
the new directory is `0755` and file `0644`. A completed, fsynced exclusive temporary
file is published without replacing any existing final name. Existing copies must
already match the same bytes and custody; conflicts refuse. All sources, existing
configuration and copy plans validate before any write. Repeated execution validates
both original and protected key even after the affected stanzas have been rebound.
The result reports Signed-By path changes separately from unchanged signer bytes,
suites and components. No runtime download or automatic key rotation is supported.

The reviewed pin and embedded public verification-key fixture come from Ubuntu's
[Noble ubuntu-keyring 2023.11.28.1 metadata](https://packages.ubuntu.com/noble/all/ubuntu-keyring/download)
and its [official package](https://archive.ubuntu.com/ubuntu/pool/main/u/ubuntu-keyring/ubuntu-keyring_2023.11.28.1_all.deb).
The 11124-byte package matches the HTTPS-published SHA-256
`36de43b15853ccae0028e9a767613770c704833f82586f28eb262f0311adb8a8`;
in-memory extraction of its canonical public-key member yields regular file,
UID/GID `0:0`, mode `0644`, size 3607 and the key digest above. This is provenance
from official HTTPS metadata and the checksum-bound package, not an independently
verified signed InRelease chain. Unknown key versions or bytes require a reviewed
pin update. The test fixture contains only this public verification key.

The preparation fixtures verify canonical archive/security routing, removal of
all active archive-list references, preserved unknown list bytes, idempotence,
single bounded key capture, unchanged originals, unsafe ancestry/metadata/digest
refusal, concurrent destination conflicts, interrupted-copy cleanup and validation
of every source before any write. When the native
`/usr/bin/apt-get` is already installed, one fixture uses `--print-uris` against
isolated temporary configuration/state/cache/log directories to cross-check the
actual APT parser without acquiring packages or changing host APT configuration.
The full `scripts/ci/test_*.py` suite remains a mandatory pipeline-security step.
This local evidence does not replace the exact-source hosted browser and TLS gates
or the unchanged first-attempt release policy.

Consumer response parsing rejects excessive JSON nesting as an incompatible
provider response, even when the body fits the byte limit. The regression verifies
one request, no automatic retry and no provider details in the public error; this
also protects the MCP bridge's shared response reader.

Docs and owner dependency regressions exercise the installed package entry points
for [minimatch globparts amplification](https://github.com/isaacs/minimatch/security/advisories/GHSA-g3hv-75wg-m249)
and [glob traversal after cancellation](https://github.com/isaacs/node-glob/security/advisories/GHSA-3g3m-2fjr-6pw4).
The affected modern consumers use exact upstream minimatch 11.0.1 and glob 14.0.2.
Only serve-handler 6.1.7 and @ts-morph/common 0.11.1 receive the reviewed callable
entry-point adapter; it delegates to the fixed upstream matcher without copying
the old implementation. `make docs-security-pack` regenerates the source/archive
provenance and identical owner-image copy. Preserve upstream license and hashes.

After locked Docs installation, `make docs-security-test` covers hostile patterns,
real static-file headers/rewrites/redirects and default-deny Swagger file allowlists.
For the isolated owner tools, run `npm ci --ignore-scripts --prefix
infra/oracle/vercel-tools` and `npm ci --ignore-scripts --prefix
infra/oracle/npm-runtime`, then `node --test
scripts/release/oracle_dependency_security.test.cjs`. It checks the real NFT,
TypeScript/config, npm workspace and packlist consumers and asserts that both
promise and streaming glob calls stop filesystem reads after cancellation.
Adversarial matching runs in a worker with memory/time bounds so a regression
fails the suite without exhausting the runner. CI retains low-severity audits,
the actual owner-image build and its separate offline provider protocol tests.
Local package tests cannot replace those image checks or hosted qualification.

Chat's exact eslint 10.12.0, @eslint/config-array 0.23.5 and TypeScript ESTree
8.71.1 consumers use scoped upstream minimatch 11.0.1 overrides. Run `node --test
scripts/test_lint_globs.cjs` after the locked Chat install, then
`make frontend-check`. Real ESLint fixtures must retain file discovery, dotfiles,
directory ignores, negation, unmatched-pattern errors and fatal parse diagnostics;
the TypeScript project service must retain its default-project allowlist. These
checks are required in CI without changing the existing audit policy or toolchain.

`test_ai_pre_request_resume.py` exercises the continuation command with a newer
owner decision arriving during CI preflight and a signed authorization revoked
during the operations check. Both must fail before reservation or provider calls,
retaining the original consumed context and unissued intent. Current signed-chain
and latest-decision reads occur under the same immediate SQLite write transaction
as the single-use claim; source changes do not commission this optional extension.

Consumer interoperability checks are in `tests/test_consumer.py` and
`tests/test_mcp_stdio.py`. They cover unchanged consumer business code with Onesa
and compatible provider transports, portable history/provenance, credential separation,
strict completion/failure boundaries, response/input limits, cancellation and MCP
discovery/explicit permissions. Route fixtures without PostgreSQL simulate admission
and identity; the separate database test verifies actual sessions, CSRF, shared budgets
and absence of stored conversations/messages. Run both with the existing backend
`pytest -q` command and the isolated `_test` database. A skipped database case is
not an authenticated integration PASS. No live provider or physical tool is used.

Release-unit fixtures pin a disposable commissioning registry and keep its keys,
policy and database inside their temporary directory. Root test execution uses a
private home-directory parent and never reads the host's production trust registry.
Fixtures that deliberately replace their policy explicitly update their synthetic
commissioning record. Production source, trust checks and release authority are unchanged.

Docs visual acceptance and its native-owner regression resolve Axe from Docs' own
locked dependency installation. Preview transport fixtures close their owned HTTP
servers even if browser launch or browser cleanup fails; an unavailable renderer
remains a failed check and must not leave the test process listening indefinitely.
Native public asset verification uses at most four concurrent GETs. Every manifest
entry still requires its exact status, size, digest and MIME before the full UI
matrix, within the existing observation deadline. Failure stops further reads and
settles in-flight reads before target cleanup. Run `node --test
scripts/docs/native-owner.test.mjs scripts/docs/native-full-preflight.test.mjs`
with the locked public build for the bounded-reader and complete TLS fixtures.

Travel planning retains one provider request, the existing output-size/token and
total generation-time budgets, strict JSON/schema/day validation, and the 503
boundary for invalid plans. Its prompt explicitly requests compact complete JSON
without Markdown. Fixed failure categories distinguish empty, oversized, invalid
JSON/schema, day-sequence, timeout and provider failures without retaining model
output, preferences or exception messages. Metrics and the bounded warning contain
only those categories. Run `pytest -q tests/test_travel_planning_failures.py
tests/test_agents_travel.py` from the backend with the disposable PostgreSQL test
target configured; a rejected revision must preserve the saved trip. The hosted
producer records the exact Travel create/revise/ownership step on failure. These
synthetic tests and a stateless engineering diagnostic are not hosted acceptance.

Owner preflight validates the matching frontend dependency and initializes private
operation/observation parents for a new exact-source artifact. Existing operation
directories and receipts remain reserved; initialization cannot retry a request.
Cold-directory, concurrent-initialization and alias/permission refusal tests run
with the release regression suite, without provider credentials.

Oracle CI selection keeps an existing push authoritative, including failed,
pending, skipped or cancelled evidence. Only an absent push permits the existing
owner-dispatched full workflow; both owner identities, a complete run listing,
first attempt and every mandatory job/security step remain required. Signed
references preserve the actual CI event. Synthetic mixed-event regressions must
reject a newer successful manual run presented over a failing push.

The documentation security suite exercises `qs` comma-array serialization with
hostile non-callable `toString` properties and ordinary parse/stringify compatibility.
Its lock uses upstream 6.16.1 for
[GHSA-6pq8-jhm2-2vcw](https://github.com/ljharb/qs/security/advisories/GHSA-6pq8-jhm2-2vcw),
retaining the low-threshold dependency audit. Dependabot PR204 / source
`bf6ab183548ad180c0f4d5c5e6b543780430c889` supplies the reviewed lockfile patch;
local checks and source promotion do not establish a live documentation release.

Browser, documentation and TLS browser jobs use Playwright's supported Ubuntu24.04
runner explicitly. The previous moving `ubuntu-latest` selected Ubuntu26.04 and
timed out installing TLS browser dependencies. All three engines, TLS checks,
the bounded installer and job deadlines remain mandatory.

The offline release suite includes `test_oracle_inventory.py`: completed temporary
monitoring clients and list/inspect races do not become preservation baselines.
Long-lived temporary workloads, unchanged-inventory command failures, incomplete
metadata and real independent runtime changes still fail closed. These fixtures
make only mocked Docker reads and do not establish hosted qualification.

`test_oracle_owned_probe.py` reproduces the self-client replacement deadlock and
checks the narrow owner-controlled exception. The Docker-written CID lives outside
all producer mounts; its immutable identity, exact image, operation label, command,
mounts and resource/security profile must agree. Missing, changed or forged clients
and any other automatic-removal workload fail closed. Cancellation tests retain
private inputs on uncertain exit, preserve the original failure and prohibit a
second stop/deployment request. SIGTERM enters existing fixture cleanup. Run this
with the full offline release suite; Linux root custody and genuine hosted
replacement/rollback evidence remain mandatory before release.

Hosted browser probes use the daemon's existing outbound bridge network in their
own network namespace. Host networking exposes Chromium to unrelated host interface
changes and can cancel a request with `net::ERR_NETWORK_CHANGED`. Preflight and
execution reject a missing, foreign, host or internal-only bridge; they never fall
back to host networking. Application deadlines, TLS, workflow assertions, fixture
cleanup and source-bound release authority remain mandatory. See Docker's
[network isolation reference](https://docs.docker.com/engine/network/drivers/host/).
An engineering diagnostic is separate from full hosted qualification and cannot
issue a release record.

Container health uses the Alpine base image's existing BusyBox `wget`, with proxies
disabled and response bodies discarded. It retains the production readiness and
staging liveness routes, intervals, retries and network deadlines. After building an
image, run `python3 scripts/healthcheck_smoke.py <image>`: an isolated network-free
container tests the actual image command against a synthetic loopback server,
including a custom port, HTTP 503/404, hostile proxy settings, refusal and timeout.
These client checks are separate from application/database release qualification.

Owner-run static artifact checks treat Next.js catch-all chunk names such as
`[...path]` as literal filenames, encode them for HTTP, and reject traversal
segments, encoded paths, controls, query strings and fragments. Regressions verify
that every accepted asset is read and hashed; changed or oversized bodies still fail.

The owner qualification image includes the versioned icon manifest used by the
mandatory hosted UI checks. Its exact source hash is part of the commissioned
probe inventory. Missing or changed image resources fail the credential-free
preflight; image startup, a passing API suite or a partial UI result cannot replace
the full hosted qualification. Keep the existing metadata and icon assertions.

Oracle staging container probes use database-free `/health`. The image default
retains `/core-ready` for existing production dependency monitoring. The middleware
regression in `tests/test_foundation.py` installs a failing connection hook on a
configured PostgreSQL engine, includes a session cookie and verifies repeated
liveness requests acquire no connection. `/core-ready` still attempts real database
readiness and fails on the unavailable engine; `/ready` retains model readiness.
Deployment qualification must continue to check schema, restricted runtime identity,
authentication and affected workflows. Container health establishes process liveness;
hosted application acceptance and measured compute savings require separate evidence.

CI and hosted artifact-build workflows pin Node 24.22.1 explicitly; a cached
`24` major selector can otherwise select an older vulnerable patch. Runtime images
and provider-managed runtimes require their own source-bound verification.

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

The public static acceptance validator resolves both Playwright and Axe from the
locked Docs installation. Importing `scripts/docs/acceptance.mjs` needs no Chat
dependency installation. Screenshot capture and full documentation generation
retain their separately documented application prerequisites; this dependency
separation does not establish a passing browser suite or hosted publication.

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

The Industrial database suite includes a fresh status read while another transaction
holds the record's writer lock. The read must return the committed snapshot promptly;
stale-recovery mutations still acquire and recheck their own lock. This synthetic
regression uses no model requests and does not replace hosted model acceptance.

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

## Classified operational source checks

`make docs-public` uses public-only generation and must not read private source
bundles. `make docs-internal` uses the internal scope; real protected publication
requires the configured restricted bundle and complete per-document provenance.
Run `python -m unittest discover -s scripts/docs -p test_protected_sources.py`
and `node --test scripts/docs/secure_internal_output.test.mjs` for the content,
path/hash/permissions, public isolation and packaging boundaries. The normal Docs
suite retains navigation, search, diagrams, PDF/source-link and private route checks.
A reference-only CI build does not qualify a protected edition with full runbooks.
Keep all local model/database targets synthetic while generating documentation.

## Conversation history and provider transport

The conversation instruction identifies supplied messages as the current history
and asks the model to copy recalled values verbatim. It is request context, never
a stored user message. `tests/test_chat_integration.py` checks bounded history,
ownership and persistence, including two-turn native Cloudflare request bodies
for streaming and non-streaming responses. These protocol cases use synthetic
provider responses; real model recall still requires hosted qualification.

## Node TLS trust regression

`node --test scripts/test_ui_navigation.cjs` reproduces a delayed response from a
previous page during navigation. Only newly observed GET responses can qualify the
current interface; current 401/503, interrupted bodies and missing responses still
fail. Request observation is removed after success and failure. This does not relax
the existing browser content, account, required-response or deadline checks.

Use Node 24.22.1 or a later reviewed security patch in the 24 series. Run
`node --test scripts/test_tls_trust.mjs` from the repository root. The test uses
a known public CA certificate and newly generated synthetic localhost certificates
in isolated child processes. It proves native fetch/HTTPS trust, rejection of
untrusted certificates and hostname mismatches, idempotence and fail-closed startup.
Temporary test keys are removed; it sends no application/provider requests.

The startup policy excludes only the SHA-256 fingerprint of the affected
emSign ECC Root CA - G3 from the effective application default store. It retains
other default/extra authorities and never disables certificate verification.
Node changes are thread-local. The Next frontend completes its Node-only
instrumentation hook before handling requests. The Python model API keeps its
independent versioned certificate bundle.
See the [advisory](https://github.com/advisories/GHSA-6q48-6c7w-9gw2) and
[Node TLS API](https://nodejs.org/api/tls.html#tlssetdefaultcacertificatescerts).
Source tests are separate from source-bound staging and production acceptance.
After the Chat build, run `node scripts/check_tls_bundle.mjs
onesa-ai-platform-frontend/apps/chat` from the repository root. The guard requires
the trust policy in each server gateway's actual file trace and rejects browser
bundle inclusion. Owner-built Vercel artifacts require the same command with their
`.vercel/output` directory as the third argument before publication; a successful
Next build or instrumentation source alone does not prove serverless packaging.

## Explicit Docs validation scope

`make docs-public` generates and validates only public provenance with
`python scripts/docs/validate.py --scope public --staged`. It requires no generated
internal tree or private bundle. `validate.py` without `--scope` retains full public
and internal validation. All allowlist, asset and private-exposure checks remain.
Static public and Cloudflare Access artifacts omit assistant navigation and use an
architecture action. Only an explicitly configured authenticated gateway enables
`ONESA_DOCS_ASSISTANT_ENABLED=true`; direct unsupported assistant routes explain the
limitation and link to guides. The CI gateway fixture opts in explicitly.

Synthetic screenshot capture can use `ONESA_CAPTURE_URL` and a separate `ONESA_CAPTURE_FIXTURE_NAME` (lowercase letters, digits and hyphens). `ONESA_CAPTURE_NEW_FIXTURE=1` creates a fresh disposable account for that named fixture. Keep its ignored private state and use only an explicitly isolated mock stack; the default `demo` fixture remains compatible with the configured Docs gateway checks.

For a public-only checkout, after the same locked prerequisites and browser installation, run `make DOCS_SCOPE=public docs-assets docs-public`. Asset rendering and staged validation read only public generated material. The default scope remains `all`; `make docs-assets docs-public docs-internal docs-validate` still requires both classified trees and the approved private source bundle for actual protected publication.


The owner-run protocol fixture additionally asserts the real pinned Vercel CLI's
outgoing `ONESA_API_URL` deployment value. Its loopback-only dummy credentials do
not authorize provider operations. `test_oracle_ai_probe_boundary.py` verifies
source-scoped early failure diagnostics, credential redaction and preservation of
original failures. All existing qualification checks and one-use contexts remain
mandatory; the protected deployment guide records current hosted outcomes.

The offline protocol suite also verifies outgoing authentication headers and the
pinned CLI's read-only user request with synthetic OAuth state. No provider credentials
or external network access are used. `test_oracle_cli_auth.py` covers expiry,
owner identity, concurrent custody changes and redacted early runner failures.

Pinned Alpine image builds retry upstream package fetching at most three times.
Each attempt keeps HTTPS, package signatures and the original package constraints;
exhaustion fails the build. The dependency auditor uses a bounded 60-second socket
timeout and retains the same vulnerability checks and failure status.

The offline Oracle release tests cover the legacy API/frontend policy and a new,
explicitly commissioned policy with fixed foundation, Twins and Cybersecurity
scopes. Each scope still permits only one qualification context for an exact
source. Mode changes, path aliases, expanded attempt limits, foreign repositories,
changed CI, revoked dependencies and context reuse are rejected. Temporary test
keys and a disposable signed ledger are not external release authority.

Qualification derives required feature journeys from the actual runtime flags.
If both optional features are enabled, both journeys must pass across the same
controlled replacement; a missing or skipped check fails qualification. A failure
after one journey passes retains a failed receipt and fixture cleanup evidence.
The new feature API profiles verify the retained frontend's original accepted
record and served build hashes, then require rendered production journeys without
another frontend deployment. Restore checks use the exact hosted schema, including
Twins on a database whose Cybersecurity migration is already present.
Combined activation also verifies the current coordinated database-and-file backup
before authorization and refreshes it after the actual production runtime changes.
Cybersecurity with Twins disabled keeps its independent database backup path.
These tests do not commission the new policy, activate features, migrate a hosted
database or establish hosted acceptance. Consult the protected canonical procedure
and evidence index for actual installation, qualification and deployment outcomes.

Upload regression tests exercise request-scoped expiry cleanup against disposable
PostgreSQL: another account's expired chunks and active rows survive, an owner's
expired fragments are removed, and the global limit still counts active leases.
The owner probe retains metadata-only preservation baselines and changed-table
diagnostics; every pre-existing row remains subject to the same strict comparison.

Travel accepts bare JSON or one whole-response JSON fence, followed by the same
strict itinerary schema and consecutive-day validation. It never extracts JSON
from prose, repairs an incomplete response, retries inference or substitutes a mock.
Protocol tests cover malformed framing, multiple objects, private reasoning markup,
schema drift and preservation of the saved trip after a failed revision. This
bounded framing support does not establish the cause of any historical hosted failure.

## Credential-free Docs build handoff

`.venv/bin/python -m unittest discover -s scripts/release -p test_oracle_docs_build.py`
checks real-run identity requirements and disposable ZIP failure controls for the
external Docs build reader. It refuses run ID zero as an Actions ID, missing/skipped
mandatory checks, provider execution, changed source/custody, expired records,
modified/private archives, unsafe ZIP members and mismatched rendered contexts.
The fixtures never issue qualification, authorization or provider requests. Build-only
workflow artifacts carry staging and production contexts separately; actual owner-run
provenance and hosted acceptance remain independent requirements.

The protected Docs adapter uses its own reviewed installation, source and runtime
closure, private artifact custody and one-use owner ledger. Its new conditional
metadata export/import/inspection commands retain the existing genuine Actions
handoff; that handoff grants no publication authority. Run
`python -m unittest discover -s scripts/release -p 'test_oracle_docs_internal_*.py'`
for source, Access, build, provider, conditional and durable journal refusals.
`node --test scripts/docs/internal-native.test.mjs scripts/release/oracle_cloudflare_transport_guard.test.cjs`
checks private byte/header readback, anonymous denial and atomic single dispatch.
The actual pinned Linux client protocol is mandatory in CI and uses synthetic
responses with its network disabled. The private full-renderer regression requires
an approved, isolated staging-context build outside Actions and runs
`ONESA_INTERNAL_DOCS_TEST_BUILD=/absolute/private/fixture ONESA_INTERNAL_DOCS_TEST_ENVIRONMENT=staging node --test scripts/docs/internal-acceptance.test.mjs`.
These tests do not commission a verifier, qualify a hosted deployment or publish
documentation. Actual outcomes remain in the protected canonical evidence index.

The release suite exercises the actual installed Docs module layout in a separate
`python -I` process with no inherited import path or provider credentials. It
reproduces the former missing-sibling import failure and verifies that both the
root verifier and sibling runner parsers load before any operation starts. This
startup regression is local evidence; fresh commissioning and hosted qualification
remain required for a changed runner.
