# Initial setup engineering history

This preserved engineering record is not a post-launch release changelog. Current release state lives in the root CHANGELOG.md. Appearance schedules in historical entries are superseded by the 2026-10-14 system-preference design decision.

## 2026-10-31 — Select canonical signed Ubuntu sources for browser CI

The first main check of `da83084feaa936ce73348fc0280498a5bdef8a19`
([run 41180154809](https://github.com/DruHustle/onesa-ai-platform/actions/runs/41180154809))
failed in TLS browser preparation: the existing helper rejected an unexpected
runner mirror-list URI before Playwright or TLS acceptance ran. The offending
URI was not logged, so this change adds no inferred mirror hostname. That failed
first attempt remains preserved and does not qualify a release.

The initial correction explicitly selected the canonical HTTPS Ubuntu archive
or security endpoint from a fully validated Ubuntu 24.04/noble Deb822 stanza.
It required the exact existing archive-list reference and the canonical Ubuntu
keyring with valid custody. Types, suites, components, architectures and activation
remain bounded; duplicate, mixed, malformed, inline-comment, unknown and authentication-
relaxing fields fail before any write. That first correction changed only URI bytes.
Unused mirror-list bytes remain untouched, while signatures, suites, timeouts,
retries and all release gates remain in place.

Preparation-level fixtures cover both acquisition endpoints, preserved comments
and line endings, keyring custody, idempotence and refusal without partial writes.
An installed native APT parser cross-check prints the expected acquisition URIs
using isolated temporary configuration/state/cache/log paths, without network
acquisition or host APT writes. A new source candidate must pass the full native
first-attempt checks; this prepared fix does not turn the failed main run into a pass.

The first dev push of the correction at `8cc4458f04fad7470a48132d8e68de4afbd756ce`
([run 41181491988](https://github.com/DruHustle/onesa-ai-platform/actions/runs/41181491988))
then refused the canonical keyring's custody before writing sources or installing
browsers. A diagnostic-only follow-up reports the fixed keyring role, file type,
UID/GID, mode, size, existing bound and failing-condition codes from the already
held stat snapshot. It reports no key contents, raw source URI, environment or
path. That diagnostic change preserved every custody condition and refusal. This
failed candidate is not qualified.

The diagnostic source `bf66c140ff466d8965e343a1da040b2cb521e393`
([push run 41182017947](https://github.com/DruHustle/onesa-ai-platform/actions/runs/41182017947))
confirmed the canonical key was regular, UID/GID `0:0`, mode `0777`, size 3607 on
runner image `20261025.353.1`; only group/other writability failed the existing
custody predicate. Its failure remains preserved. The prepared repair captures the
original public key once through a bounded no-follow/nonblocking descriptor and
requires the reviewed Noble package's exact 3607-byte SHA-256 pin. It copies the
same captured bytes into a fixed protected `/etc/apt/onesa-ci-keyrings` location,
then rebinds only validated affected Signed-By paths. The original key and mirror
file bytes/modes remain untouched. URI and Signed-By path substitutions now change;
signer bytes, suites, components and all authentication/release gates remain intact.

The copy has root-owned, APT-traversable protected ancestry and mode `0644`.
Complete, fsynced temporary bytes are published without clobbering an existing or
concurrent destination. Unknown bytes, aliases, unsupported metadata, unsafe parents
and conflicting copies refuse; no runtime download or automatic rotation occurs.
Every source/configuration/copy plan validates before writes, and repeated runs
revalidate the original pin and protected copy. The real public-key fixture and
checksum-bound official HTTPS provenance are recorded in
[Build and test](../engineering/BUILD_AND_TEST.md); no independently verified
InRelease-chain provenance is claimed. Local regressions cover bounded capture,
FIFO refusal, original preservation, interrupted writes, destination races,
idempotence and the isolated native APT parser. Fresh first-attempt native CI is
still required; this prepared repair does not qualify any earlier failed source.

## 2026-10-31 — Bound provider failures and repair dependency security gates

The bounded consumer response reader now converts JSON decoder recursion failure
into the existing redacted incompatibility error. The regression reproduces a
small, deeply nested provider response and verifies no retry or provider-detail
disclosure. The shared reader also serves the read-only MCP bridge.

Retain the recovered pypdf 6.21.4 pin and both hash-locked dependency sets, plus
the compatible Docs follow-redirects 1.16.2 and joi 17.13.9 security updates.
Replace the remaining affected matchers with upstream minimatch 11.0.1 and glob
14.0.2 in the affected Docs and isolated owner-tool dependency paths. Vercel stays
at 65.2.0 and its official npm source stays at 12.2.1. Audit thresholds remain
unchanged; the runtime Python, Chat, Docs, Vercel-tool and separate npm-runtime locks
pass their local vulnerability audits.

Chat's three modern lint consumers also use exact-version scoped minimatch
11.0.1 overrides: eslint 10.12.0, @eslint/config-array 0.23.5 and
@typescript-eslint/typescript-estree 8.71.1. Their toolchain versions and all
unrelated optional-platform lock entries remain unchanged. Real ESLint fixtures
retain file/ignore/negation selection and fatal diagnostics; the TypeScript
project service still refuses files outside its explicit default-project pattern.
The Chat lock additionally passes a low-threshold local audit with no findings.

The two legacy callable consumers, serve-handler 6.1.7 and @ts-morph/common
0.11.1, use a narrow local entry-point adapter to the unchanged fixed upstream
matcher. It contains no old matcher code. Exact consumer overrides, upstream
integrity/license, source/archive provenance and the identical owner-image archive
are recorded. Installed-artifact regressions cover bounded hostile patterns,
post-cancellation filesystem work, static Docs serving, Swagger file allowlists,
TypeScript config, NFT asset tracing, npm workspace patterns and exclusion of
private files from packages. The owner compatibility suite is a required CI step.

The previously prepared pre-request continuation helper now rereads its signed
intent/authorization/qualification chain and latest owner decision inside the
SQLite write transaction immediately before claiming the one allowed attempt.
A superseding decision or revocation during CI/operations preflight cannot leave
a continuation reservation or issue a provider request. It never renews the
original context or authorization; interrupted attempts still require inspection.

These prepared source changes do not establish a live application, documentation
or owner-tool release. Hosted CI, immutable image/protocol checks and the existing
owner qualification path remain required; accepted production component versions
remain recorded separately in the root changelog.

## 2026-10-28 — Isolate release-unit commissioning fixtures

Docs visual acceptance and its native-owner regression now resolve the existing
Docs-owned Axe dependency. Preview transport browser fixtures also close their
owned servers on launch or cleanup failure, retaining the original failed result.

The product requirements also distinguish consumer application/provider portability
from MCP tool and context interoperability. The current internal and product adapters
remain accurately identified; shared-contract, configuration-switch and authorization
acceptance criteria are recorded without claiming the feature is implemented.

Release-unit tests use their own temporary commissioning registry, including root
test execution, without reading the host's production trust registry. The profile
ledger fixture explicitly updates its synthetic commissioning after its deliberate
policy replacement. Production verifier and release requirements are unchanged.

## 2026-10-28 — Declare Docs-owned accessibility validation dependencies

The public static acceptance validator previously imported Axe from the Chat
installation and could not be imported after a clean Docs-only install. Declare
the existing reviewed Axe version in Docs and resolve it there alongside
Playwright. Keep accessibility assertions, classified asset checks and independent
release gates unchanged. Local import verification is separate from the complete
browser acceptance suite and an authorized hosted publication.

## 2026-10-27 — Bound retries for failed upstream build fetches

Repeated native checks failed before testing during Alpine CDN TLS fetching or a
PyPI audit handshake. Retry signed HTTPS package operations at most three times
and allow the auditor a bounded 60-second socket timeout. Exhausted downloads and
vulnerability findings still fail. No deployment or acceptance is implied.

## 2026-10-27 — Check owner CLI authentication before qualification

Verify the pinned vendor CLI's actual read-only owner authentication before consuming
a qualification context. Refuse stale or concurrently replaced custody and retain
redacted failures that occur before the hosted producer starts. Extend the offline
real-client tests to assert authorization headers and user readback using synthetic
OAuth state. Existing signatures, source binding and deployment attempt limits remain
required; these changes do not establish a successful hosted release.

## 2026-10-13 — Protected Portal privacy-governance engineering reference

Refresh committed Portal API/schema snapshots from the reviewed governance source and Robot snapshots from qualified main. Add seven internal workflows covering review, retention, deletion requests, processors, transfers, privacy publication and the planned Vercel commercial transition. Include the protected governance reference in architecture navigation while preserving every required topic and the public/internal boundary. Public builds exclude governance documents and mutation contracts; private policy content is never part of documentation source.

## 2026-10-13 — Record isolated production Cloudflare serving configuration

The existing production Render service now has its own account-scoped Workers AI token and verified synthetic generation/embedding connectivity. Record renewal dates and the distinction between saved configuration and an accepted live release. The unused unauthenticated demo's public route is disabled reversibly; no application deployment or DNS cutover is implied.

## 2026-10-13 — Preserve redirect denial in the Cloudflare verifier runtime

The deployed verifier denied the approved owner because workerd rejected the signing-key fetch's `redirect: error` option. Use manual redirect handling and refuse every non-success response, retaining bounded fetches, trusted issuer, signature/audience/identity/host checks and MFA policies. Verify malicious signing-key redirects cannot expose assets; local workerd evidence remains separate from hosted acceptance.

## 2026-10-13 — Verify the ecosystem onboarding homepage

Update the authenticated documentation browser assertion to the new three-product homepage heading. Keep login, private asset denial, revocation, database/API and assistant checks enforced.

## 2026-10-13 — Align visual generators with required formatter checks

Format the changed documentation generator and validator using the repository's pinned Ruff rules. Preserve generated content, classification and access checks; run the complete required Python checks before pushing the correction.

## 2026-10-13 — Visual architecture and engineering onboarding

Make Architecture & Workflows and Engineering Onboarding adjacent persistent sections. Add source-controlled ecosystem, provider, delivery, quarantine/retry, AI, identity, data, operations/recovery, maturity and four-day learning diagrams. Reuse the existing accessible viewer and add individual PDF exports, source/build metadata and a browser-local learning checklist. Keep detailed navigation and workflows in the internal output, validate references and schema/source drift in CI, and refresh obsolete staging labels without asserting production or Access acceptance.

## 2026-10-13 — Reconcile database isolation and remove obsolete deployment entries

Pin staging probes to the verified *-staging Neon project and reject the production endpoint. Privately initialize/rebind only the empty synthetic target with the existing staging role contract, preserving production and model credentials. Replace the historical paid Render database declaration with an existing Free API reference and preserve keys instead of generating replacements. Correct approved reply-to examples; all supported provider adapters remain available.

## 2026-10-12 — Approved company contact and legal links

Display the owner-approved legal name, email and telephone across the independent chat application, with locale-aware links to the central company legal and privacy pages. Use a committed snapshot derived from the maintained Portal record; no sibling runtime or private record is required by this build. Preserve automatic styling, authentication and unverified privacy-processing gates.

## 2026-10-12 — Registered private-Free staging entry point

Allow the existing manual, owner-only staging bridge on private repositories so the repository-secret fallback is usable before new workflows reach main. Keep production guards, exact-source qualification, named staging secrets and protected Preview checks; test rejection of untrusted actors/events, main refs and production targets.

## 2026-10-12 — Cloudflare release profile compatibility

Accept the implemented Cloudflare inference/semantic embedding selectors in staging preflight. Preserve rejection of mock, lexical, missing and non-staging profiles; actual hosted generation and retrieval remain required. Document the supported account endpoints and versioned 256-dimensional adapter.

## 2026-10-12 — verified staging secret scope

- Select the verified public `Staging` environment through the non-secret `STAGING_SECRET_SCOPE` variable while keeping repository-level `STAGING_*` secrets as the private-Free fallback.
- Share one deployment sequence between mutually exclusive owner-only jobs; preserve source qualification, target checks and production separation.
- Test both scope selections, private fallback and untrusted actor rejection; diagnostics disclose only availability booleans.

## 2026-10-12 — Verify configured staging secret injection

Add trusted owner-only environment and repository availability modes to the existing
hosting inspector. Test required names as booleans, without checking out code, calling
providers or displaying values. Preserve the Staging entries and independently verify
usable injection and actual repository entitlement. Private-Free repository fallback
remains documented; secret names alone never prove authentication or data isolation.
Exercise real diagnostic code with synthetic sentinel values and assert they are never
logged. Oracle configuration remains independent of GitHub secret entry.


## 2026-10-12 — Qualify free-cloud adapters and automatic day/night styling

Add explicit authenticated Cloudflare generation and semantic embedding adapters,
with bounded responses, reviewed model profiles and versioned normalized 256-dimensional
Matryoshka vectors. Keep mock, Ollama and vLLM providers interchangeable; local adapter
tests do not prove hosted inference. Add server-side Access verification to every
internal documentation route and asset, with fail-closed packaging and origin checks.
Chat and documentation follow visitor-local 07:00/19:00 transitions without a theme
selector or stored manual override. Preserve CSP, strict accessibility assertions and
public/internal output separation. Repository-level staging secrets support private
GitHub Free; existing environment secrets must be reconciled privately before deployment.
Ignore regenerable Wrangler cache; preserve private provider and approval evidence.

## 2026-10-12 — Rename Zero Trust organization to Onesa

Apply the owner's requested organization display name and verify the existing login
domain, MFA configuration, identity provider, applications and policies on readback.
Cloudflare's partial update cleared an omitted MFA field; restore the approved
TOTP/security-key enrollment configuration and verify that every unrelated
organization field matches the snapshot. Eight-hour MFA sessions and global
enforcement off are retained. Record owner-confirmed authenticator verification
separately from API-observed sign-in and pending protected-docs MFA/bypass acceptance.
The Pages Git installation error still blocks the documentation project.

## 2026-10-12 — Enable owner MFA enrollment portal

Diagnose the missing App Launcher configuration and enable the required enrollment
portal with a policy limited to the two confirmed owner email addresses. Reuse the
existing email-PIN provider and eight-hour session, preserving organization settings
and unrelated applications. Owner MFA enrollment/authentication still requires actual
browser verification; engineering app enforcement and hosted bypass tests remain
pending the Pages Git connection and successful owner verification.

## 2026-10-12 — Verify approved Cloudflare MFA enrollment capability

Apply the owner's explicit approval for TOTP/security-key enrollment with eight-hour
sessions and global enforcement off. Provider readback preserves all unrelated
organization settings, identity providers and existing application policies. Record
the successful configuration separately from personal enrollment/authentication and
hosted docs acceptance, which remain unverified. The Pages Git installation still
rejects project creation with8000011; no internal upload or application enforcement
was performed. Existing recovery/admin methods are preserved; docs enforcement waits
for the owner's successful enrollment and authentication.

## 2026-10-12 — Prepare separate Cloudflare engineering documentation

Add a dependency-free harmless bootstrap target for `onesa-engineering-docs` and
retain the Access-wrapped internal packaging path with all requests protected. Reject
stale revisions, overlapping output paths and symlink artifacts; run packaging tests
in documentation checks. The Cloudflare build mode marks hosted assistance unavailable
because this gateway serves only authorized documents. Record exact Pages build
settings, separate main/preview/custom-host policies, independent MFA and Free Functions
fail-closed requirements. The owner's two allowed identities stay in ignored local
setup, and repository visibility stays public until the announced launch. Local
preparation does not activate Zero Trust, create/deploy a project or qualify hosted access.

## 2026-10-12 — Separate save-only production startup operator

The legacy main repair cannot run in the staging-only environment. Add an explicit owner-dispatched production startup operation on current dev after full exact-source CI/hygiene. It verifies the existing free Frankfurt production service and disabled auto-deploy, preserves reviewed Dockerfile/script startup, and clears an unrecognized override only. Readback requires unchanged functional configuration, environment and deployment identity. No deployment, database change, model target, credential transfer or production approval is implied.

## 2026-10-12 — Approved AI browser favicon

Add the existing owner-supplied Onesa64×64 ICO through the Next.js file-based metadata convention, so the AI app emits an actual branded icon link and serves its own asset. Copy the approved Portal icon byte-for-byte (SHA256 `7d236707ace84a0117de7dd6fcb97e4664b96f859b9e1bdc3325e7fe3b097e89`); no unrelated logo or image transformation is introduced.

## 2026-10-12 — Remove appearance switching

Remove Auto/Light/Dark controls, preference logic, timers and custom palette switching at the owner’s request. Retain the fixed light surfaces and navy/cyan brand elements, with responsive and authenticated acceptance checks. Public and protected documentation use the fixed light default with the framework switch disabled. Remove only assets and tests belonging to the retired feature.


## 2026-10-12 — Explicit hosted trust roots and failed deployment receipts

Use the existing operating-system CA bundle explicitly so certificate/hostname verification does not depend on bundled libpq’s build-time certificate path. Keep channel binding required and reject absent trust stores. Database authentication, TLS, channel-binding and privilege failures return fixed codes only. After a verified backend deployment, retain actual hosted FAIL/BLOCKED receipts even if temporary fixture creation fails.


## 2026-10-12 — Hosted fixture TLS and safe operation phases

Use libpq system trust roots with verify-full and required channel binding on fresh hosted runners; saved query options cannot downgrade those controls. Return fixed database/identity phases on failure, retaining role/schema guards and private credentials.


## 2026-10-12 — Consistent appearance and authenticated staging qualification

- Chat and public/protected documentation implement persisted Auto/Light/Dark with visitor-local 07:00/19:00 transitions. Bootstrap runs before rendering; Chat retains CSP nonces and documentation synchronizes Docusaurus color context.
- Fixed dark-theme form/card/message contrast and expanded every Chat page plus every public documentation sitemap route in both modes at desktop/mobile widths. All 124 documentation route/mode/width checks pass with zero axe findings, alongside 19 diagrams, 11 public PDFs, 3,056 internal-link checks, search and protected-path exclusions. The mobile search wrapper no longer covers appearance; inline links are distinguishable and theme color changes apply immediately.
- Stage fixture schema is validated before deployment. Owner-dispatched temporary synthetic users receive two-hour access grants; private credentials stay in a 0600 runner file and are revoked/removed after verification. No production identities or migrations are changed.
- Production documentation links default to the actual public docs domain; engineering links stay hidden until their protected target is configured.
- Reuse the exact protected native Git staging Preview; do not create a second frontend deployment. Authentication diagnostics expose fixed phase/reason codes only. Real inference/embeddings/streaming remain mandatory and cannot be replaced by mock QA.
- Local backend: 156 pass, four external serving tests skip. Chat: 24 Chromium/WebKit browser cases pass (four external serving cases skip); 61 release guard tests pass. Native documentation security regressions and both classified builds pass after manifest regeneration. Updated official immutable Node 24-compatible Actions; corrected docs deployment shell assignment to preserve failed-read errors. Actual hosted model readiness and production owner review remain release gates.

## 2026-10-12 — Fail incomplete hosted staging acceptance

Retain uploaded staging receipts but fail the workflow when hosted acceptance is FAIL,
BLOCKED, incomplete, or falsely claims PASS with failed checks. A successful provider
build/deploy is still recorded separately. Production qualification gates are unchanged.

## 2026-10-12 — Safe hosted preflight diagnostics

Report a fixed failure code for provider access, target identity, database binding,
model configuration and Preview protection without printing values, URLs, provider
responses or arbitrary exception text. Retain every existing validation/release gate;
add regression coverage rejecting private exception text from diagnostics.

## 2026-10-12 — Explicit staging secret forwarding

Declare and forward only the staging secret names used by the reusable qualification
workflow. GitHub otherwise resolves environment-only secrets to empty strings. Retain
Staging environment precedence, preflight value/isolation checks and production gates;
add contract coverage for missing mappings and prevent production credential forwarding.

## 2026-10-12 — Initial qualified staging entry point

Allow an explicitly selected staging dispatch through registered deploy.yml, reusing
release-staging.yml and its Staging environment without inherited production secrets.
Retain exact-source owner/branch/event, provider/database isolation and hosted model
acceptance gates. Production requires its explicit target and existing authorization.
This permits initial staging qualification before new workflow files reach main.

## 2026-10-12 — Production provider credential boundary

Correct legacy public production workflow bindings to use production provider secret
names, preserving staging-only credentials in staging workflows and all existing
qualification/approval gates. Private production jobs remain disabled; no provider
values or deployments changed. Add a regression forbidding staging tokens in production.

## 2026-10-12 — Public documentation search description

Add the missing homepage description to public documentation so generated HTML
provides a useful search snippet and social description. Preserve public-source
selection, internal access controls and documentation deployment gates.

## 2026-10-12 — Save reviewed production defaults without deployment

Add an explicit owner-only operation on dev to save missing nonsecret settings to
the identified AI production service, after exact-source CI and hygiene pass. Preserve
existing values, reject staging/foreign targets, active deployments and linked groups,
disable redirects, and verify readback and unchanged deployment identity. Do not copy
database/API credentials, create resources or promote production. Preserve the reviewed
Ollama and semantic embedding profiles pending actual hosted endpoints. Set the approved
reply address to info@onesa.eu and keep email disabled until delivery is qualified.
Add regression coverage to CI for these configuration and credential boundaries.

## 2026-10-11 — Staging environment and branch configuration

Scope staging credentials to the GitHub Staging environment, preserve each product’s Vercel project for staging previews, and standardize remote branches on dev/staging/main with restricted recovery archives. Keep production qualification and explicit owner approval enforced.



## 2026-10-11 — Automated review and CI/CD optimization

Add read-only Reviewdog, checksum-locked workflow/secret analyzers, negative pipeline
tests, conservative PR paths, dependency caches, PR cancellation and required CI summary.
Preserve full release-source checks and independently tested runtime evidence; remove
Portal duplicate image builds. Add opt-in isolated staging and automatic technical
qualification, retaining manual exact-digest owner authorization and external production
credential custody. Legal/operational evidence never receives fabricated PASS.
Dependabot version schedules are prepared; automatic security-update PRs were enabled
and verified as requested. No other remote settings, pushes or live deployments. See the CI/CD pipeline report.

## 2026-10-11 — Private-Free release safeguards

Credential-free hosted PR CI; immutable Actions pins; exact-commit qualification and owner authorization with external production handoff; separate staging credentials; legacy JSON fallback removed; private credential-bearing production workflows excluded. Remote settings and deployments unchanged. See the private-Free safeguard report for owner migration and enforcement limits.

## 2026-10-11 — Preserve qualified staging with owner runner policy

- Merge all current staging corrections and owner-approved runner routing by ordinary
  merges. Preserve bounded chat history, exhausted mail leases, public PDF links,
  crawler policies, Preview protection and staging operator regression coverage.
- Keep all software, browser, docs, startup and full image-security checks in the
  private reusable gate; public jobs use hosted execution and verify live visibility.
- Keep obsolete implementation and session handoff files removed. No local runner
  activation, production promotion, billing or physical control.

## 2026-10-11 — Public repository hosted Actions

- Record the owner-selected temporary public visibility and standard GitHub-hosted
  runner policy. Local runners remain private-only; retain security and release gates.
- Clarify that earlier private-plan protection failures are historical and do not
  establish current public-repository enforcement. No billing or protection settings changed.

## 2026-10-11 — Final identity-mail lease crash recovery

Expired final-attempt mail leases become failed during maintenance, preserving
active final leases and recording no fabricated provider acceptance. Regression
tests use real isolated PostgreSQL and prove that a sixth send is not attempted.
Reconcile provider receipts before manually retrying an ambiguously completed job.

Public PDF source references now target `https://docs.onesa.eu` rather than a local
development server. Artifact validation inspects every public manual's actual PDF
link annotations and requires its declared source references to use the public site.

## 2026-10-11 — Vercel Standard Protection compatibility

The staging deployment guard recognizes the documented
prod_deployment_urls_and_all_previews protection mode alongside existing protected
modes. Missing/unknown protection still fails before configuration writes. Regression
checks retain repository/root/main identity, Preview-only scope and conflict refusal.
Production protection is never disabled.

## 2026-10-11 — Separate documentation crawler policies

Public documentation now emits robots.txt with the public sitemap. Internal builds
emit a separate disallow policy and retain authentication on every asset, including
robots.txt. Browser verification checks both emitted files and their HTTP boundaries.
Preview noindex headers and the public-production release guard remain in place.

## 2026-10-11 — Bounded chat context reads

Chat selects the last 30 messages directly in PostgreSQL, retaining chronological
model context and message sequences without materializing an unbounded history.
An isolated integration regression verifies the SQL bound, exact context ordering
and preservation of all stored conversation messages.


## 2026-10-10 — Frontend provider credential boundary

- Strip Vercel bypass headers and forward only Onesa session/CSRF cookies to the API;
  provider authentication cookies and other frontend cookies stay at the frontend.
- Added a real proxy regression with an isolated synthetic fetch transport. All
  eight CI checks and hosted authentication/CSRF, recovery and responsive acceptance
  passed for `43affff` in workflow `38088509721`.

## 2026-10-10 — Transaction-pooled runtime timeout

- Apply the five-second query limit inside each transaction, preserving bounded
  pooling and TLS without relying on a session startup option rejected by poolers.
- Read-only staging probes now use the actual application engine and report its
  timeout; regression coverage checks new transactions after commit and rollback.

## 2026-10-10 — Staging optional provider settings

- Preserve initialized staging data on retries; omit absent optional Render settings,
  retain unrelated settings and bound transient provider retries.
- Unconfigured model/embedding URLs default to empty instead of invented service hosts;
  Compose continues supplying its explicit internal service URLs. Hosted inference stays blocked.

## 2026-10-10 — Render startup regression

- Made Dockerfile CMD authoritative in AI configuration and added final-image startup,
  PORT, liveness, dependency failure and SIGTERM verification to CI.
- Added safe provider command classifications and staging revision readback.
- Local backend integration: 147 passed, four platform-dependent skips; hosted repair
  remains unverified. No push/deployment or inference-readiness claim.

## 2026-10-10 — Local semantic retrieval qualification

- Added optional private pinned Qwen3-Embedding-0.6B serving, 256/1024 normalized outputs,
  bearer/body/token/queue bounds, offline loading, weight verification and safe errors.
- Added fixed synthetic EN/DE evaluation and raw rankings; 256 passed declared thresholds
  with 45/48 top-1 versus 47/48 at 1024. Retained failures and dimension tradeoff.
- Explicit 256 requests and query-only instructions; HTTPS/key validation for production
  HTTP embedding services. Real pgvector isolation/reindex-failure/native grounded-chat
  acceptance passed; original live documents/configuration preserved. No deployment.


## 2026-10-10 — Account controls and typed feature workflows

- Added profile/password/session settings; password-confirmed bounded owner-scoped JSON
  export and atomic live account deletion, including document embeddings. External
  backups remain outside self-service deletion; oversized exports fail rather than truncate.
- Added extracted-document preview/reindex UI and strict runtime response models for
  knowledge, agents, trips and model discovery; feature pages use generated types.
- Serialized login/account locks, rechecked revoked tokens, fixed missing cancelled-run
  outcomes; verified cross-user isolation, derived-data deletion and malformed output denial.
- 112 PostgreSQL/backend passes, one Linux skip; frontend lint/types/build, 12 supported
  browser cases and public/internal docs builds passed. Conservative API review and
  production release gates remain unresolved. No new publication/deployment occurred.


## 2026-10-09 — Preserved frontend/backend split

- Moved the existing Next.js/docs apps, FastAPI/migrations and training/evaluation into
  separately buildable frontend/backend directories within the original Git history.
- Added runtime same-origin streaming BFF, generated typed API client, independent
  pinned Docker contexts, unbuffered Caddy routing, resource limits and env templates.
- Bounded PDF parsing and async readiness dependency probes; added availability metrics,
  private scrape/alert templates, backup integrity/retention and restart/rollback tools.
- Updated Make, CI, manual image packaging, classified documentation paths and runbooks.
  Verified database content preservation, existing regressions and real model stop/retry.
- Kept schema, OpenAPI, private credentials, native model/data and sibling projects intact.
  Local migration is verified; external production acceptance remains explicitly pending.

## 2026-10-09 — Documentation dependency blocker resolved

- Backported depth/AST guards for braces and bounded numeric formatting for sprintf-js into explicit private local forks; retained upstream licenses, reviewable diffs and source/archive integrity records.
- Added twelve mandatory security/consumer compatibility tests covering hostile nesting/precision, direct ASTs/cycles, real file watching, micromatch, argparse and Markdown rendering; clean install and npm audit now show zero findings.
- Enforced all-severity audit and installed backport integrity in CI/release gates. Qualified docs with repo-local official SHA-verified Node 24 and mutually supported React 18 peers; existing application React and data contracts are unchanged.
- Extended live Swagger testing to actual Try it out/Execute and response rendering, rebuilt isolated portals and regenerated classified artifacts. No remote publishing or model download occurred.


## 2026-10-09 — Amendment 002.2 documentation ecosystem

- Added independent public/internal Docusaurus builds, existing-identity gateway and retrieval-time engineering authorization; explicit public source/asset allowlists and negative exposure checks.
- Integrated desktop/mobile Documentation, conditional Engineering links and contextual help without changing existing application contracts or migrations.
- Added scoped search, interactive architecture/database/API exploration, local authenticated playground, seven public/twelve internal manuals, twenty-eight SVG/PNG diagrams, seven actual synthetic screenshot views and fifteen guided procedures.
- Added existing-model documentation assistance, validated integration/streaming examples, deployment checklists, local feedback, classified media/download libraries, release metadata and CI build/security/browser checks.
- Verified 84 PostgreSQL tests, 61 CPU tests, frontend/docs types/builds, four original mock and one real browser regression plus live documentation authorization/navigation/assistant checks. Recorded initial failures and unresolved upstream documentation audit findings; publication remains blocked.
- Preserved source/private configuration/installed model and database volumes during the user-directed repository move; deleted the explicitly authorized old directory and restarted managed local services at the new path.


## 2026-10-09 — Milestone 2: native Apple Silicon real inference

- Installed checksum-verified native Ollama and the explicitly requested Qwen3 4B Q4_K_M;
  loopback only, context 8192, private repo-local runtime/model storage.
- Added shared Ollama/vLLM streaming, request-owned usage/timing and safe model metadata;
  preserved public alias, authentication, schema, conversations and all applications.
- Fixed observed web SSE compression buffering; verified real browser/API cancellation,
  context/history, sources, model tools/travel and managed-daemon failure/recovery.
- Stored 13-case evaluation (12 strict passes, exact-format arithmetic failure), one
  native tool-schema probe and measured concurrency 1/2 benchmark reports with limits.
- Verified 62 PostgreSQL tests, 41 CPU tests, frontend lint/type/build, main Docker startup,
  four original mock browser tests and one explicit real-model browser test.
- Updated setup/contracts/architecture/status/handoff. Apple Silicon M2 is complete;
  M3 semantic embeddings are next. NVIDIA, alternative models, training and production
  qualification remain unverified. See MILESTONE_2_REPORT.md.

## 2026-10-09 — Amendment 001: European and international alignment

- Applied European-based general-purpose positioning, retained optional African/regional
  adaptation, and recorded ADR 0003 without changing the milestone order.
- Updated product/architecture/model/training/privacy/deployment documentation and added
  market/use-case/innovation/sovereignty/customization references with explicit evidence limits.
- Removed the training language enum; added extensible language/domain labels and logical
  candidate-profile/licensing/provenance/evaluation metadata with report/config hashes.
- Added unchanged-base paired regression reporting and English/German navigation/sign-in
  catalogs, configuration and persisted preference; other workspace copy remains English.
- Preserved existing public APIs, database schema, model alias and application implementation.
- Verified 47 PostgreSQL tests, 27 CPU tests, frontend lint/type/build, Docker startup,
  4 Chromium tests and unchanged OpenAPI. Evidence is recorded in SESSION_HANDOFF.md. Rechecked M2.3 hardware: NVIDIA/CUDA execution is pending.

## 2026-10-09 — Complete local platform and continuation handoff

- Delivered authenticated PostgreSQL-backed chat, migrations, session/CSRF protection,
  per-user isolation, SSE generation leases/cancellation and responsive Next.js UI.
- Added configurable vLLM adapter, pinned model/GPU images, diagnostics and LoRA override.
- Added TXT/PDF knowledge ingestion, versioned pgvector search and saved chat sources;
  lexical baseline and real embedding adapter remain clearly distinguished.
- Added bounded registered tools with explicit grants, shared-model planning and run
  history; structured saved/revisable travel with explicit provider availability.
- Added provenance-aware dataset preparation, split verification, training dry-run,
  gated local LoRA/QLoRA runner, evaluation and immutable candidate registry.
- Added safe logs/body bounds/protected metrics, non-root containers, TLS and restricted
  production database templates, backup/restore/load scripts and full CI configuration.
- Reconciled API/OpenAPI/schema/ERD/design/deployment/security/training/operations docs
  with actual implementation; retained engineering attachment as reference material.
- Verified 44 real-PostgreSQL tests, host lint/type/build, 3 real Chromium flows,
  Node 24.21.0 container startup, backup restoration and zero dependency audit findings.
- Started local platform on port 3100 with private generated secrets, preserving the
  earlier verification database. M2 NVIDIA hardware acceptance is the next incomplete
  task; real-model/provider/training/production qualification remains explicit.


## 2026-10-09 — Milestone 0 foundation

- Initialized the empty project without renaming the user's repository.
- Installed the supplied continuation prompt in AGENTS.md and a dedicated document.
- Preserved engineering input as reference and captured screenshots in architecture,
  PRD, roadmap, design decisions, API contracts and proposed PostgreSQL schema/ERD.
- Implemented FastAPI configuration/application factory, server-generated request
  UUIDs, health and bounded readiness with sanitized errors.
- Added a model-client protocol and labelled deterministic cancellable mock stream.
- Added dependency pins/lock, Make commands, Ruff, mypy, Pytest and CI configuration.
- Generated OpenAPI and documented local operation and verification limitations.
- Verified install/editable build, dependency checks, lint/format/type checks and
  11 passing tests. Fixed timeout-test lint and OpenAPI output-directory handling.
- Recorded current milestone M1 with PostgreSQL models/migrations as the first task.

## Organization preparation — 2026-10-09

Prepared `onesa-ug/onesa-ai-platform` as an independent private GitHub repository.
Renamed local `master` to `main` as requested; preserved baseline commit `1ea8d54`,
the baseline branch, all staged renames and unstaged work. Created the empty online
repository and configured `origin`; no code was pushed or committed in this session.
The parent `onesa-ug` workspace remains without a `.git` directory. Portal and robot
have separate Git roots; robotics remains outside the platform application boundary.

Added CONTRIBUTING/SECURITY/GITHUB_SETUP, application environment examples, separate
build/deployment guides and an offline publication-hygiene CI gate. Existing CI now
runs on every push/PR with read-only contents permission; manual candidate packaging
also requires hygiene. New ignores cover private/generated/runtime content, but do
not untrack existing files. Publication is blocked by 119 generated document paths
already in history/index, including 92 internal paths; owner classification and an
explicit remediation decision are required. No credential-pattern matches were found
in publishable worktree/index/reachable history, including decoded PDF text; this is
not a proof that confidential prose or unsupported credential formats are absent.

Current local checks: frontend lint/types/production build passed in an isolated
copy with local Node 24; backend wheel build, Ruff/format, strict mypy (20 source
files), and pytest passed (65 passed, 30 database-dependent skipped). Root scripts
and operations Ruff/format passed. Remote CI, Docker images, browser and live database
integration were not re-run. Work remains on M3.2; no unrelated milestone was advanced.
See `docs/engineering/BUILD_AND_TEST.md`, `DEPLOYMENT.md`, and `GITHUB_SETUP.md`.

## Source publication and Vercel/Render target — 2026-10-09

The owner authorized pushes to main, removal of workspace readiness-report artifacts,
and Vercel frontends with Render backends. History was explicitly deprioritized.
Prepared fresh source-only main while retaining original Git metadata/staged work
and patch backups locally. Generated manuals, credentials, uploads, records and
model artifacts remain local and excluded from publication. This supersedes the
prior tracked-history blocker for the new publication history only.

Database integration: 94 passed, one optional skipped; frontend cloud changes are
under verification. Added Render app-only build context/database/health configuration
and Vercel build configuration with 150-second API duration and a 3 MiB upload budget.
Mock is explicitly labelled until a qualified remote inference endpoint is configured;
native Mac Ollama is not exposed to the Internet. Provider authentication, final
origins, target-host checks and organizational privacy decisions remain incomplete.
No production readiness or actual remote deployment is claimed from local checks.

## GitHub release verification — 2026-10-09

Source-only main is now published to the private Onesa UG repository. Added manual
GitHub Actions deployments with exact-commit CI/hygiene gates, pinned Vercel CLI and
Render live-status/commit verification. Native provider auto-deploys are disabled in
the deployment standard. Provider projects/secrets and actual target acceptance are
still required; no cloud deployment or production qualification is claimed.

Resolved first remote CI failures by generating synthetic screenshots in clean docs
builds, waiting for documentation gateways to listen, updating operations cryptography
and its lockfile dependencies, and skipping cleanup when staging was never created.
Patched operations encryption regression passed; its dependency audit has zero findings.
M3.2 semantic retrieval qualification remains pending. Original Git metadata backup
is temporary and will be removed at the owner’s request after remote source verification.

GitHub plan compatibility: deployment workflows consume repository-level Actions
secrets without paid deployment-environment features.
AI documentation browser builds now generate diagrams/manuals before testing actual
assets; the standalone documentation and TLS/operations jobs passed remotely.

## Publication follow-up — 2026-10-09

Fixed the documentation search race after session revocation: access-denied HTML is
never parsed as JSON, pending fetches are canceled on unmount and unavailability is
shown without unhandled promise errors. Added denied-response/malformed-index regression
coverage. Removed the obsolete original-history backup and Ruff caches after source
commits were verified on GitHub, as requested. The owner chose to leave provider
Actions secrets empty, so actual Vercel/Render deployment remains pending configuration.
Portal full GitHub verification passed; its deployment workflow safely failed for
missing provider configuration. No cloud deployment or production qualification claimed.


## Final cross-project audit — 2026-10-09

This section supersedes earlier current-state readiness claims. Existing FastAPI / Next.js AI apps preserved; main baseline 6e98c6d4cb07, local uncommitted candidate only. No new push/deployment/publication. Local 105 backend tests passed, one Linux-only skipped and separately checked in Linux; 12 supported browser passes plus one real native model acceptance; frontend lint/type/production build passed. Firefox startup, conservative contract compatibility review, complete ASVS/a11y and hosted operations/legal acceptance remain incomplete. Production release is **NO-GO**, distinct from local passing checks.

Added exact-origin controls, nonce CSP, independent provider examples, standard generated clients/compatibility gate, strict release fingerprint/approval tooling, synthetic restore and current container scanning. Production mock/local inference endpoints now fail closed; bounded SSE runtime parser and non-forcing streaming scroll; core readiness separates model degradation; Python OS HIGH findings still block release. M3.2 semantic embedding remains incomplete.

Restricted release reports and evidence are ignored under docs/internal/release-audit. Read RELEASE_DECISION, RELEASE_BLOCKERS and VERCEL_RENDER_RUNBOOK before promotion. `python3 scripts/release/qualify.py decision` returns NO-GO. Actual provider credentials/origins/storage/inference/monitoring and human legal/content approvals remain required.

Current REST ownership verification: repository is private under DruHustle (User); onesa-ug remote redirects. Intended organization ownership is unverified and release-blocking. No ownership/remote/visibility changed.


## Domain configuration — 2026-10-10

Owner selected `platform.onesa.eu` for the AI chat frontend. The production example
now uses this exact `ONESA_PUBLIC_ORIGIN`; Vercel `ONESA_API_URL` remains the actual
Render API URL. Company and private administration use `onesa.eu` and
`portal.onesa.eu` in the independent portal repository. Future robot host is
`robot.onesa.eu`; the robot application is not implemented. Provider assignments,
DNS/TLS qualification and production delivery remain pending; populated `.env`,
models, indexes, cookies and API contracts were not changed. No push/deploy here.


## Private environment files — 2026-10-10

Created root `.env.local` and `.env.prod`, both ignored by Git and mode 0600.
Local variables preserve the existing `.env` values and add documented defaults.
Production settings use `platform.onesa.eu`, Secure cookies and a separately
generated metrics token; provider DB/inference credentials remain placeholders.
Lexical retrieval remains the production baseline pending hosted embedding
qualification. Files parse with the supported Node runtime. Select the files
explicitly; existing startup defaults and running services were not changed.
No API contracts, models, indexes, architecture or deployment changed.

### 2026-10-10 — deployment review

- Expanded offline secret gates for Resend and Neon; repository/history scans pass.
- Added explicit missing Vercel secret diagnostics without exposing values.
- Verified backend/frontend/browser checks and regenerated stale ignored documentation.
- Hosted API 503s and release/security/compatibility gates remain unresolved.


## Remediation and release closure — 2026-10-10 v1.1

This dated continuation supersedes earlier current-result statements, preserving their historical evidence. Targeted upload/security/contract/UI/operational changes are implemented locally; current application builds and synthetic checks are recorded in the restricted release-closure ledger. No remote mutation, commit, push, email, DNS or public-release approval occurred. Company Portal and AI Platform remain independently **NO-GO** for hosted503s, credential containment, operations/legal and remaining security/manual acceptance. Do not represent the older deployed revision as this dirty candidate.

Portal preserves10MiB private-file capability through bounded transport; fresh MFA/private provenance controls remain intact and two intentional compatibility changes await client/version approval. AI preserves5MiB ingestion and existing real local models; adds explicit invitation gating, one-use recovery/outbox worker, shared DB admission quotas and honest bootstrap errors. AI runtime uses pinned Python3.11.17 Alpine and build-only pinned uv; native Linux PDF restrictions remain enforced. Compatibility18→0 is a proved schema refinement, not baseline reset. Private STAGING_OPERATIONS_DELTA.md and SECURITY_ACCEPTANCE.md specify hosted/manual/policy gaps. Exact refreshed results/source hashes are in RELEASE_CLOSURE.md/EVIDENCE_INDEX.json, not old milestone totals.

Next executable bounded task: qualify native AMD64 PDF denial and prepared candidate staging after owner-approved target/access, then diagnose503 from actual Vercel/Render logs; separately implement the reviewed password-blocklist/session-assurance policy. M5 live travel, training, paid access, hosted inference/capacity and human multilingual quality are still unqualified; no speculative provider integration introduced. Preserve original ordered milestone requirements and all prior dirty work. Robot unchanged.

## GitHub review and deployment follow-up — 2026-10-10

The owner has now authorized reviewing, committing and pushing to `main`, and
monitoring deployments. Production qualification remains mandatory; this permission
does not establish staging, operations or content/legal acceptance. Company record
files awaiting publication approval remain local and are excluded from Git and
documentation artifacts. The manual `Inspect hosting configuration` workflow uses
existing provider secrets for read-only service, configuration and deployment
checks; it emits only required-variable presence and allowlisted status fields.
Paired releases now wait for the backend (and portal worker) before promoting the
frontend. Remote CI and provider results will be recorded after the push; they are
not implied by the earlier local test results.

CI follow-up: clean GitHub runners exposed root-owned Trivy report permissions;
image scans now use an exported image archive and the runner UID, retaining all
vulnerability/secret checks. The platform development dependency declaration now
includes pinned pip-audit, with the lock regenerated from source. Hosting readback
found missing provider configuration and failed native Render deployments. The
manual repair workflow only updates existing matched-repository Docker layout,
health paths, disables native auto-deploy and adds absent approved public origins
or portal S3 aliases. It never deploys, migrates data, copies/rotates credentials,
changes plans, creates resources or marks qualification gates as passed.

Browser CI repairs: portal blob download anchors are attached to the document and
object URLs are retained until WebKit starts downloading; the exact 10 MiB private
CV upload/download and SHA-256 check passed native Linux WebKit. Documentation
test grants accept only the old fixed or new randomized synthetic example.com
fixtures. Render AI configuration now rejects implicit development/test defaults
and suppresses input values in configuration validation errors. Fresh platform
backend checks passed (146 passed, 4 conditional skips); remote full checks remain
in progress. No production qualification record was fabricated.

Staging infrastructure follow-up (owner direction 2026-10-10): reuse an existing
qualified AI-specific Render database if found; otherwise prepare separate staging
and production PostgreSQL proposals without provisioning or selecting a paid plan.
The diagnostic workflow now inventories AI-named database candidates and the actual
backend region without retrieving connection credentials. Hosted vLLM and semantic
embedding infrastructure remain blocked pending a costed, approved host; preserve
native Ollama and local data. Database/core readiness now requires an actual current
schema even in development; `/health` stays process liveness, while `/core-ready`
may remain available during an inference outage only with a healthy database.


## Dedicated hosted AI preparation — 2026-10-10

The owner requires a dedicated AI Render PostgreSQL database and separately approved
European GPU/vLLM host, with staging first and no unapproved paid provisioning.
Read-only inventory found the backend in Frankfurt and no AI-named database
candidate; ownership/schema verification of differently named resources is not
implied. HOSTED_AI_PROPOSAL.md prepares isolated PostgreSQL 16/vector-256 proposals,
scoped roles/TLS/pooling/restoration and one costed Paris L4 GPU/CPU-embedding plan.
Separate staging/production JSON proposals are not applied Blueprints or live URLs.
HOSTED_AI_CONFIGURATION.md inventories all 47 actual Settings names and process
scopes without secret values. Expanded diagnostics report only presence booleans.

Alembic now reads ONESA_DATABASE_URL directly instead of requiring complete hosted
application/model settings. Full application validation remains strict. Fresh
Ruff/format/mypy passed; 147 backend tests passed, four conditional skips and one
upstream TestClient deprecation warning. A new isolated PostgreSQL regression proves
migration independence while invalid production inference configuration is refused.
GitHub verification for the preceding readiness revision completed successfully
across all eight jobs. The proposed migration/docs revision still needs fresh CI.
Hosted model, semantic embedding Linux lock/capacity, actual dedicated database,
original-file archive requirements, real delivery worker, credential rotation and
staging/operations/legal qualification remain open. Production remains NO-GO.


Expanded hosting readback: the authorized same-owner Render inventory returned zero
PostgreSQL resources without page truncation, and zero of all 47 AI application
settings were explicitly nonempty. Optional defaults do not qualify hosted services.
The proposal and full names-only matrix now record these actual observations. The
new diagnostic required Ruff formatting on the clean CI runner; formatting repaired
and the full repository make check is rerun before push. No runtime gate weakened.


## Owner free-only staging direction — 2026-10-10

The owner rejected paid database/GPU budgets and will establish staging. Added
staging.env.example with real application variable names, blank credential/endpoint
fields and isolated origins; existing populated env files remain untouched.
FREE_STAGING_SETUP.md documents ongoing free Neon/Render/Netlify/Resend/conditional
Zoho options, exact product setup/migration commands, limitations and owner steps.
Paid proposals/Blueprints are historical and explicitly not to be applied. No paid
resource, account subscription, DNS cutover, live migration or model switch occurred.
Vercel Hobby commercial restrictions, expiring Render free database, missing free
workers, EU model/privacy/capacity and restored backup limits remain material.
Free inference candidates are unconfigured, not a deployed real-model endpoint.
Production remains NO-GO; preserve independent products and all original data.


## Public documentation hosting — 2026-10-10

The owner selected docs.onesa.eu and confirmed Vercel public-use eligibility.
Prepared separate GitHub-built preview/production hosting for the allowlisted
Docusaurus public site. Only build-public is uploaded; internal engineering stays
behind its authenticated gateway. Static mode honestly disables documentation
assistance. Fresh isolated mock screenshots resolve clean-build missing images;
existing generated local files and the application on port 3100 are preserved.
The clean build rendered four public diagrams and seven public manuals, passed
source classification, 13 dependency-security tests, zero npm vulnerabilities,
TypeScript, and desktop/mobile static acceptance. See
../engineering/DOCUMENTATION_HOSTING.md for deployment and actual DNS readback.
Hosting/domain verification is not yet completed at this recorded source state.
No API/model/data configuration, application production guard or paid plan changed.
Application release remains NO-GO; internal authentication qualification is pending.


## Documentation favicon correction — 2026-10-10

Added the owner-approved Onesa orbit ICO as an independent docs static asset and
configured Docusaurus to emit its favicon link. The publication workflow now
checks the emitted index and exact bundled icon before upload. No API contracts,
internal source policy or application release guards changed. Hosted verification
will be recorded after the deployment completes; company branding is already
fixed in source but its production deployment remains independently gated.

## Public docs Git deployment safeguard (2026-10-10)

Added `git.deploymentEnabled: false` in the docs app `vercel.json`. The public
documentation hosting workflow copies this configuration into its isolated Vercel
deployment directory. Automatic Git deployments are disabled; the existing checked
GitHub Actions prebuilt deployment remains available. This does not prevent an
authorized administrator from connecting Git. JSON validation and diff checks passed;
no provider settings, deployment or release approval were changed.

## AI Render startup command correction (2026-10-10)

The reported exit 127 treats the quoted Uvicorn command as one executable.
Replaced nested `sh -c` overrides with `sh /app/start.sh` in both Render
blueprints and the hosting repair helper. The image includes this startup script
and uses it as CMD; it expands PORT (default 8000) and execs python -m uvicorn
with existing concurrency, logging and graceful-shutdown settings. Seven hosting
regressions, shell syntax, default/custom-port argv and diff checks passed.
The local Docker image builds successfully. Hosted settings and deployment have
not been changed; production remains gated.

## Shared Onesa interface identity (2026-10-10)

Public/internal documentation and the AI application now use the company homepage
navy (#081b32), cyan (#53dbe8), blue (#2366d1), neutral surfaces and Arial typography.
Docs retain light/dark reading modes and use a navy public hero; application layout,
security states, retrieval and API contracts are unchanged. Portal lint, platform
lint/typecheck, docs typecheck and the public docs build passed. Local locked
platform dependencies were restored after a missing axe test dependency was found.
These are local source changes, not a hosted release or legal/operations approval.

Final theme acceptance: desktop (1440px) and mobile (390px) browser checks
passed for docs and the platform signed-out interface, including horizontal
overflow and keyboard reachability of the docs skip link. The signed-out backend
remains honestly unavailable in the isolated preview; no authentication bypass
was used. The docs skip-link and hero spacing overflow were corrected. Robot
static preview checks passed at the same widths. Authenticated application styling
was updated in source but not verified against a live signed-in session.

Pre-push review: Docker health check now reads PORT consistently with startup.
Eight provider/startup regression tests and the rebuilt image pass. History hygiene
scans report zero findings in all three repositories. The generated Next.js route
declaration was restored to its production form; generated framework agent guidance
is included. Provider production readiness remains independent of a source push.

## 2026-10-10 — AI configuration inventory

Added AI-only, read-only provider inventory for actual backend origin, provider identity, linked environment groups, overrides, worker inventory, Vercel domain assignment and redacted configuration validity. No provider configuration or resource provisioning is performed by this workflow. Disclosure and scope tests pass locally.

Prepared complete source-backed AI configuration matrix, verified origin/proxy values, temporary free Render PostgreSQL staging proposal and standalone loopback-only vLLM host proposal. Corrected production example to retain semantic embedding candidate; no private environment files or other projects modified. Local isolated PostgreSQL147passed4skipped; hosted API503 remains open.

## 2026-10-10 — Instruction documentation cleanup

Removed completed GitHub setup instructions and duplicate status/session-handoff
logs. Consolidated contribution, security, repository governance and agent policies
in one root AGENTS.md per independent repository. Preserved unfinished work in
existing roadmap/release documentation, updated links and documentation tooling.

## 2026-10-10 — Owner-created AI staging database

Recorded the owner-reported isolated Neon resource `onesa-ai-platform-backend-db-staging`, superseding the Render staging database creation request. Updated staging template and private ignored staging profile without copying the disclosed owner password. Preserved local/production/Portal configuration. Hosted ownership/schema/TLS/roles and migrations remain unverified until fresh private credentials are available.

### Isolated AI staging configuration

Added a scope-checked staging diagnostic and Preview-only configuration/deployment path.
CI and publication hygiene must pass on the current staging SHA before deployment.
Recorded actual PostgreSQL 18.6, empty staging schema and privileged-role blocker;
client TLS is checked separately from the Neon pooler internal connection.
Production branch and provider settings remain unchanged.

Prepared staging-only controlled migrations, restricted runtime-role provisioning,
exact-origin configuration and real hosted security/persistence/restart tests.
Bound the existing GitHub Staging environment and restricted its deployment branch.
Corrected Vercel tracing separately from Docker standalone packaging.
Hosted results remain unverified until the new revision passes CI and deployment.

### 2026-10-11 — Identity worker lifecycle

Graceful termination stops new claims and disposes connections; bounded one-shot
execution supports a separately qualified scheduler without changing durable mail
leases, retries or provider idempotency. Hosted delivery remains unqualified.


## 2026-10-10 — GitHub Free governance plan

- Selected private GitHub Free operation with voluntary feature-branch PRs, verified
  CI, manual authorization and least practical write access. No paid upgrade or
  visibility workaround is proposed; main enforcement remains blocked.

## 2026-10-10 — Branch protection and governance audit

- Verified private personal ownership, admin access, actual PR CI/security check names
  and deployment/environment evidence across all three repositories.
- Attempted repository rulesets and classic fallback; GitHub rejected both with HTTP
  403 requiring Pro eligibility. Main readback remains unprotected, NOT ENFORCED.
- Prepared exact payloads, solo-developer PR/recovery policy, templates and API-backed
  reports. Local `deploy.yml` display names now use `deploy-qualification`, `deploy-frontend` and `deploy-backend`; the manual documentation hosting job now displays `docs-hosting`. Job IDs, dependency expressions and deployment behavior are preserved. This removes collisions with required CI checks. These edits are not yet published; merge them through a reviewed PR and verify the resulting names before activating the payload.
- Existing local work is preserved. No push, merge, deployment, billing, visibility,
  credential or external provider change was performed.

## 2026-10-11 — Reviewed governance integration

Consolidated policy references and templates, preserved later audited runtime fixes, and reconciled deployment notes with actual staging evidence. Prepared protection settings remain reference only under GitHub Free. Original local work and private environment files are preserved. Public production qualification is unchanged.

## 2026-10-11 — Automated qualification (local implementation)

Added versioned exact-candidate Actions evidence, tested runtime digests, encrypted
reviewed Vercel prebuilt artifacts, owner approval/revocation records, staged/provider
receipts and fail-closed promotion/hosted checks. Legacy qualification is retained
behind an explicit verified migration switch. No production release or legal approval
was issued; target acceptance adapters/configuration and remote validation remain open.

## Documentation ecosystem reference 0.3.0 — 2026-10-11

Extended the existing Docusaurus portal across Company Portal, AI Platform and
Robot, with source-pinned Fastify/FastAPI explorers, current generated AI schema,
16 ecosystem diagram groups, readable private ERDs and ten additional engineering
manuals. Fixed architecture view selection, dated table-count/schema prose, Swagger
accessible labels/nested controls and low-contrast badges. Added static interaction,
link, classification, PDF and accessibility gates to hosted/private CI and docs hosting.
The public static build remains independent of application release approval. Hosted
internal access and actual model/hardware functionality are not claimed complete.

## 2026-10-11 — Remote CI integration review

Removed pip caching from the publication hygiene job because it installs no packages; GitHub runner cleanup otherwise fails when the cache directory is absent.
Preserved the newly merged ecosystem documentation, pinned its additional checkout actions, and scoped scanner exceptions to three verified source checksums.

Generated development-lockfile hashes for all 81 already-pinned packages. A clean dependency calculation validates hashes instead of relying on an existing local environment; no package versions changed.

## 2026-10-13 — Hosted protected visual documentation acceptance

Verified the qualified staging revision through actual owner Cloudflare Access MFA, then published the classified internal output to the existing protected Pages staging project. Confirmed 16 architecture sections, 17 onboarding chapters, four learning days, 73 diagrams with 292 rendered/editable exports, responsive automatic day/night views, search and accessible interactions. All 15 anonymous origin and Preview resource probes redirected to Access; authenticated responses remain private/no-store/noindex. Public Preview qualification passed independently at the same source. Production publication and custom internal DNS are not inferred from staging acceptance.

## 2026-10-13 — Reject retired approvals and reconcile architecture evidence

Retire the compatibility qualification command’s acceptance of locally editable gate JSON, even when its source hash matches. Actual release authority remains the existing trusted qualification/promotion workflows. Add forged and malformed approval regressions. Update canonical architecture/workflow references with actual isolated Portal/AI staging and protected engineering publication evidence; preserve Robot’s HTTP401 and production operational limitations.


## 2026-10-27 — Explicit owner deployment routing (unreleased)

Manual prebuilt Previews have no Git source, so commit metadata alone does not
supply the staging branch's server-only API origin. The owner frontend runner now
verifies only the two named existing routing variables, binds their identities and
canonical origins to the source-specific configuration, and passes that one
nonsecret origin explicitly to the deployment. Real pinned-CLI protocol tests
assert the outgoing binding for staging and production. Project variables,
authentication, optional-feature defaults and independent services are preserved.
Early hosted-probe failures now retain bounded source/operation/error-code diagnostics
without credentials or exception messages; a failure record never qualifies a release.
Source checks do not establish hosted qualification or production acceptance.
