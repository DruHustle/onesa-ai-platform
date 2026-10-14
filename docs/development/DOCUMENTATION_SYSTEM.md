# Documentation system

Documentation version 0.3.0 implements Amendment 002.2, superseding overlapping 002 requirements.
The public portal defaults to localhost:3200; internal engineering to localhost:3201;
Onesa applications remain localhost:3100. These are configurable development origins.

## Sources, classification and builds

One Docusaurus/TypeScript framework under onesa-ai-platform-frontend/apps/docs shares UI components and Onesa design tokens.
The public source allowlist is docs/documentation-policy.json. Everything else is internal by
default. Existing architecture/design/operations Markdown remains authoritative; generated staging
copies rewrite repository references into portal routes without creating separately maintained text.
The two builds have separate Markdown inputs, static directories, indexes, retrieval files,
OpenAPI schemas, diagrams and manuals. Public database engineering pages are absent.

```bash
npm --prefix onesa-ai-platform-frontend/apps/docs ci
make docs-api
make docs-diagrams
make docs-pdf
make docs-public
make docs-internal
make docs-validate
```

SOURCE_DATE_EPOCH controls PDF generation dates for reproducible release inputs. Browser/PDF
metadata can contain renderer-specific identifiers; reproducibility means regenerating the same
classified source content, not claiming byte-identical PDFs across browser versions.

## Server-enforced internal identity

scripts/docs/gateway.py serves every internal path only after the existing Onesa API verifies
its session and engineering-user-ID allowlist. There is no independent password system. Default
engineering access is denied; a private environment setting ONESA_DOCUMENTATION_ENGINEERING_USER_IDS
contains approved existing user UUIDs. Logout, expiry, disabling a user or removing the ID revokes
access. The server guards HTML, JS/CSS, images, PDFs, indexes and manifests alike and sends private,
no-store headers. Missing identity service fails closed. Do not serve build-internal directly with
a generic static server or Docusaurus dev server. Internal development uses the protected gateway.

The optional compose.docs.yaml mounts only classification-scoped retrieval inputs into the API.
The API enforces engineering permissions again at retrieval time. The gateway fixes assistant
scope server-side, validates its own Origin and forwards the existing session-bound CSRF value.
Users cannot supply arbitrary source URLs or change retrieval scope. Answers use existing
knowledge embeddings and the shared ModelClient; vectors remain the lexical baseline.

## Developer experience

Global local search supports Command-K/Control-K, titles, full text, API methods, component names
and internal table metadata. No third-party telemetry is installed. Checklists store non-sensitive
progress only in localStorage and are not proof of execution. Feedback produces a local report;
no remote issue tracker is configured and no report is submitted automatically. Internal feedback
stays within approved engineering channels. Shared URLs/routes centralize application help links.

API reference mode is read-only by default. Optional ONESA_DOCS_API_URL accepts only an explicit
loopback development origin; intercepted requests cannot target a different origin. Existing
cookie, Origin, CSRF and CORS checks still apply. Production write execution is not enabled.
Operational metrics and private inference routes are excluded from generated schemas.

## Rendered media and manuals

Editable Mermaid sources reside in docs/diagrams. SVG/PNG and A4 manuals are generated to
separate docs/generated/public and docs/generated/internal artifact libraries and copied into
matching build staging directories. Internal manuals never enter the public static directory.
PDFs include classifications, covers, version/date/status, contents, headings, page headers/footers,
vector figures, source links and bookmarks. Actual schema-based API appendices and SQLAlchemy
metadata reflect current code. Screenshots capture synthetic accounts and redact credential fields.

## Validation and release boundaries

Run both builds with broken-link errors enabled. Verification compares current OpenAPI, ORM and
migration hashes, diagrams and artifact manifests; inspects PDFs; checks public allowlists and
negative internal exposure; tests gateway authorization, source isolation and browser navigation.
CI builds/validates locally and does not publish. Documentation dependencies have an independent
lock/audit; unresolved upstream advisories must be recorded, never hidden by downgrading safety
checks. Publication needs a configured approved workflow and a separate release review.

English documentation is delivered; existing English/German application catalogs remain intact.
NVIDIA, semantic embeddings, training, live providers and production qualification remain pending.

## Local operation, relocation and CI

Current checkout: `/Users/andrewgotora/Software Development/GitHub/onesa-ug/onesa-ai-platform`. The user-authorized obsolete directory was removed after source/model preservation checks. Service managers derive the root from their own script locations. A moved editable Python environment needs `python -m pip install --no-deps --no-build-isolation -e onesa-ai-platform-backend`; Make uses module invocations to avoid stale CLI shebangs.

Use `make up-docs` to preserve the read-only retrieval mounts and private engineering access configuration; base `make up` alone omits the optional documentation integration. Start gateway services with `ONESA_DOCS_API_URL=http://localhost:3100 make docs-serve` only when local interactive execution is intended. Otherwise API exploration remains read-only. Gateway launch environment must match the build environment. Production URLs use centralized NEXT_PUBLIC_ONESA_DOCUMENTATION_URL, NEXT_PUBLIC_ONESA_ENGINEERING_DOCUMENTATION_URL, ONESA_APPLICATION_URL and ONESA_DOCS_URL; container frontend URLs are build arguments. No auth secrets are passed in links.

CI now builds both scopes, renders actual diagrams/manuals, checks schema/source drift and public exposure, and runs original application plus mock documentation browser checks. Its synthetic demonstration account is granted only through the explicit test configuration utility; no public role-grant endpoint exists. Separate `make docs-release-check` requires backport integrity/attack/compatibility tests and an all-severity npm audit; the original blocker is resolved with reviewed local backports. See [dependency security](../security/DOCUMENTATION_DEPENDENCIES.md). Remote CI has not been executed. There is no automatic publication workflow.

The gallery includes actual synthetic screenshots; the database library includes five actual schema relationship groups. The candidate model registry remains file-based, with no invented model/evaluation database tables. Fifteen concrete procedures live in [guided tutorials](../deployment/GUIDED_TUTORIALS.md). English documentation only; German application navigation remains supported.


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

## Historical interface identity (2026-10-10; superseded)

The current shared contract, product variants and system-preference appearance are maintained in [Onesa Design System](../architecture/ONESA_DESIGN_SYSTEM.md). Earlier clock schedules and disconnected navy/cyan skins below are historical evidence.

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

## Visual architecture and onboarding

The internal homepage and persistent navigation expose adjacent **Architecture & Workflows** and **Engineering Onboarding** entries. `docs/ecosystem/visual-navigation.json` supplies sixteen architecture sections, seventeen onboarding references and the four-day learning path; it is emitted only into the internal build. Learning notes remain in the browser and never count as qualification evidence.

Use the diagram catalog and editable `docs/diagrams/*.mmd` definitions. Every build supplies classification, actual source hash and revision metadata; the existing viewer supports keyboard/pointer pan, zoom, enlargement and SVG/PNG/PDF/Mermaid exports. Diagram status labels distinguish source implementation, verified staging, production limits and planned hardware/research.

After reviewing committed sibling changes, refresh cross-product references offline:

```sh
.venv/bin/python scripts/docs/sync_ecosystem.py --portal ../onesa-company-portal --robot ../onesa-ai-robot
.venv/bin/python scripts/docs/ecosystem.py --portal ../onesa-company-portal --robot ../onesa-ai-robot
make docs-assets docs-public docs-internal docs-validate
```

Review the updated pinned commits, contracts, SQL and hashes before committing. Portal OpenAPI comes from its Fastify exporter; Robot from its FastAPI exporter. Local and remote journal ERDs derive their actual DDL; AI schemas regenerate from metadata and migrations. The generator never exports live rows or credentials. `visual_policy.py` rejects missing references, undefined diagrams and wrong classification. CI renders all Mermaid, checks separate assets/schema drift and runs `visual-acceptance.mjs` for navigation, four-day checklists, diagram interaction, mobile layouts and automatic light/night accessibility. Its browser-intercepted fixture is local rendering evidence, never proof of hosted Access.

See the [source index](../ecosystem/VISUAL_WORKFLOWS.md), [onboarding overview](../onboarding/START_HERE.md) and [hosting controls](../engineering/DOCUMENTATION_HOSTING.md). Publishing engineering content still requires actual Access/MFA and direct-origin/preview/index/download qualification.
