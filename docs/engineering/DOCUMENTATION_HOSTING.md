# Onesa UG documentation hosting

> Current readback — 2026-10-13: the existing `onesa-engineering-docs` Direct Upload project has protected origin and wildcard-preview Access applications requiring approved identities and TOTP/security-key MFA. Both Pages environments have verified audiences, approved identities and allowed-host bindings. Owner authentication now reaches the qualified staging build (`9b21e5debbd4a86aae95d7d3db429bf0e01ef703`, deployment `bd016bea`). Hosted acceptance passed all 16 architecture sections, four learning days, 292 diagram exports, search and pan/zoom/enlargement, 18 desktop/mobile automatic day/night layouts, and 15 anonymous origin/preview/page/index/download probes. No blocking automated accessibility findings were observed. All authenticated resources remain private/no-store/noindex, and anonymous probes redirect to Access. Public Preview workflow `38327330427` passed at the same revision. Production publication and the proposed custom internal hostname remain unverified; no DNS cutover occurred. Earlier installation and authentication failures below are historical, not current missing-resource findings.

[Visual diagrams and onboarding](../ecosystem/VISUAL_WORKFLOWS.md) are prepared in the classified builds. Public production still follows the existing `docs-hosting.yml` main-source qualification; private publication requires Access and source qualification first. [Cloudflare MFA policy reference](https://developers.cloudflare.com/cloudflare-one/access-controls/policies/mfa-requirements/).

The owner selected **docs.onesa.eu** for public documentation and confirmed Vercel
public-use eligibility. The existing Docusaurus application remains within
`onesa-ai-platform-frontend/apps/docs`; the three repositories stay independent.
The v0.3 reference covers the Company Portal, AI Platform and Robot simulator.
Implemented software, verified staging core, unavailable dependencies and proposed
hardware/model integrations have distinct labels; documentation hosting does not
qualify application production.

Only the explicitly approved sources in `docs/documentation-policy.json` and approved public assets
may be published. Internal engineering records remain private by default.

## Deploy from GitHub

The manual **Public documentation hosting** workflow uses Node 24 and Python 3.11,
locked dependencies, security tests, an all-severity dependency audit, fresh
synthetic screenshots from an isolated Docker/PostgreSQL mock fixture, classified
SVG/PNG diagrams/PDFs, source provenance validation and the public static build.
It uploads **build-public only**. No live database, model or user account is used.

- `target=build`: creates a reviewable public artifact without provider changes.
- `target=preview`: uploads the same static application to a temporary Vercel URL,
  with crawl-blocking headers. It does not attach production DNS.
- `target=production`: requires `main`, publishes public docs and verifies the existing
  `docs.onesa.eu` assignment on the independent Vercel project. Application production release
  guards are unchanged; this standalone documentation deployment does not promote
  the AI or Company Portal application.

Existing `VERCEL_TOKEN` and `VERCEL_ORG_ID` GitHub Actions secrets are reused only
inside the runner. `VERCEL_DOCS_PROJECT_ID` is optional: without it, the workflow
looks up the separately named `onesa-docs` project. Set `create_project=true` to
create that project if absent. It refuses to deploy into the AI frontend project
or another project's name. No paid plan, function, database, model service or
subscription is provisioned; no credentials enter the static site or reports.

Git deployment is handled by this GitHub workflow; do not attach an automatic
repository-root build that bypasses classification. Retain the existing
application `VERCEL_PROJECT_ID` unchanged. Provider changes, deployments and the
actual DNS target must be recorded from workflow/provider results, not invented.

## Squarespace DNS

After the production upload succeeds, use the **domain-readback** in the workflow
summary or the Vercel project's Domains screen:

| Type | Host | Value |
| --- | --- | --- |
| CNAME | `docs` | Exact recommended CNAME returned for `docs.onesa.eu` |
| TXT, if requested | Exact verification host returned by Vercel | Exact public verification value |

Do not guess a CNAME, alter nameservers or remove existing website/email records.
Verify the custom hostname and TLS after updating DNS. A working Vercel deployment
URL does not prove the custom hostname is attached correctly.

## Preview and staging versus production

A preview reviews one change. Staging is a stable test environment with isolated
configuration/data. Production and staging should share the code, dependency
versions, build process, runtime and routing. Domains, secrets, data and indexing
must be appropriately scoped. Different capacity limits performance conclusions.
The docs preview and production use the same public static build/routing; only
preview receives `X-Robots-Tag: noindex, nofollow`.

`ONESA_DOCS_STATIC_HOSTING=true` explicitly disables documentation assistance
because a static host has no authenticated gateway. Guides, local search,
read-only API reference and approved downloads remain usable. API execution
stays disabled. Mock screenshot capture does not qualify hosted inference or
application readiness.

## Internal engineering documentation

The owner selected `engineering.docs.onesa.eu` as the proposed private hostname
on 2026-10-12. It is not a verified live service.
Never upload `build-internal`, `.generated/internal`, private audit evidence,
repository history or application env to this static project. The supported
internal gateway verifies existing Onesa sessions and engineering-user allowlists
for **every** page, index, asset and PDF, and fails closed when identity is
unavailable. A hidden URL or client-side login page does not provide this boundary.
The existing server gateway passes identity/asset denial and permission tests. A
separately approved authenticated hosted target and session-origin acceptance are
still required; public Vercel must never receive internal output.

### Cloudflare Access setup — prepared 2026-10-12

Use a separate **onesa-engineering-docs** Pages project in the existing Cloudflare
account. The existing AI Worker and public `docs.onesa.eu` project remain separate.
Local packaging does not provision a project, enable Access or upload files.
Authenticated account readback now succeeds for the owner-selected account. The
existing Zero Trust organization is now **Onesa**, as requested by the owner on
2026-10-12. Its team domain remains `andrewgotora.cloudflareaccess.com`, with the
existing One-time PIN provider. API readback verifies the display-name change and
preserves all other organization settings, identity providers, applications and
policies. The private rename receipt is
`data/runtime/cloudflare-docs/organization-rename-receipt.json`. Pages and Access API
permissions were granted through browser OAuth;
credentials remain in native local CLI storage. No billing changes were made.

The Git-connected Pages creation request returned Cloudflare error **8000011** about
the account's Pages Git installation. No Pages project or docs Access application
has been created. Repair/connect the Cloudflare GitHub integration for the selected
`DruHustle/onesa-ai-platform` repository before retrying creation; do not silently
replace the requested Git-connected project with an irreversible Direct Upload choice.
The proposed source configuration disables automatic production and preview builds.

After the owner explicitly approved MFA enrollment, the organization update was
applied and verified on 2026-10-12: allowed authenticators **TOTP and security keys**,
MFA session **8h**, global MFA enforcement **off**. Before/after API readback confirms
the existing team and unrelated organization fields, identity provider and application
policies are preserved. The API initially rejected its own disabled, unconfigured
service-token inactivity object; omitting that invalid input preserved the original
disabled object exactly on readback. No credential revocation, identity removal,
recovery reset or unrelated application change was performed.

The private receipt is `data/runtime/cloudflare-docs/mfa-enrollment-receipt.json`.
The owner has now confirmed **successful authenticator verification**. Access user
metadata separately records successful owner sign-in at `2026-10-12T15:24:34Z`.
Device verification is owner-reported; it is not an API inspection of MFA devices or
a successful MFA login to a protected docs application. The enrollment page remains
`https://andrewgotora.cloudflareaccess.com/AddMfaDevice`; preserve existing
authenticators. Apply policies directly to the specific docs applications, then
verify both approved identities against their harmless placeholders. A new Git-connected
Pages attempt still returned **8000011**; no project or docs application exists, and
hosted anonymous, unauthorized-user and direct Pages/Preview bypass acceptance
remain **BLOCKED**, not passed. No internal content was uploaded.

Enrollment-help inspection found no configured App Launcher application or policy.
The required enrollment portal is now enabled with an application-specific Allow
policy containing only the two approved owner emails, the existing One-time PIN
provider and an eight-hour session. Readback verifies the exact policy and preserves
the organization, identity providers and unrelated applications. Its private receipt
is `data/runtime/cloudflare-docs/app-launcher-enrollment-receipt.json`. This portal
permits owner sign-in and authenticator enrollment; it does not grant access to docs
applications or enable their MFA enforcement. The owner has completed authenticator
verification through this portal. For another approved identity, sign in and open
**Account → MFA devices → Add an MFA device**, select **Authenticator application**,
scan the provider's QR code privately and verify using the current app-generated
six-digit code. Preserve existing authenticators. See [App Launcher setup](https://developers.cloudflare.com/cloudflare-one/access-controls/access-settings/app-launcher/)
and [enrollment instructions](https://developers.cloudflare.com/cloudflare-one/access-controls/access-settings/independent-mfa/#enroll-authenticators).

The owner supplied two exact authorized email identities. Their values and the
dashboard settings are in the ignored, owner-readable local file
`data/runtime/cloudflare-docs/setup.json`; personal identity values are not added to
public repository configuration. Apply those **Email** Include rules with action
**Allow**, an initial **8-hour** session, and no other Allow/Bypass rules. Multiple
Include rules are OR conditions; do not add account membership, Everyone, an email
domain or a login method as an additional Include rule that broadens the allowlist.
See [Access rule semantics](https://developers.cloudflare.com/cloudflare-one/access-controls/policies/).

1. In the existing account, open Zero Trust and select the **Free** plan if onboarding
   appears. The existing team is `andrewgotora`; `onesa-ug` was only a suggestion. The owner
   completes any billing verification. Cloudflare requires payment details even for
   this plan and says Free enrollment itself is not charged. See
   [Zero Trust onboarding](https://developers.cloudflare.com/cloudflare-one/setup/).
2. Connect the appropriate source repository through **Workers & Pages → Create
   application → Pages → Connect to Git**. The current `DruHustle/onesa-ai-platform`
   repository is public; the owner intends to make it private at official Onesa UG
   launch. Use only approved source there. Pages also supports private GitHub repos.
   The new build script must reach the selected branch before the Git build can use it;
   the local dev work has not been pushed or merged by this task.
3. Publish only the bootstrap with these actual build settings:

   | Setting | Value |
   | --- | --- |
   | Project | `onesa-engineering-docs` |
   | Production branch | `main` |
   | Framework preset | None |
   | Root directory | Repository root (empty field) |
   | Build command | `python3 scripts/docs/prepare_cloudflare.py --placeholder --output build/cloudflare-docs` |
   | Build output directory | `build/cloudflare-docs` |

   This command needs no application dependencies and emits only a harmless HTML
   placeholder, robots file and response headers. It cannot copy the internal build,
   even if one exists. The bootstrap can initially be public because it contains no
   engineering material. Internal builds require a fresh isolated output directory.
4. In Pages **Settings → General → Enable access policy**, create the preview policy.
   Manage its Access application and remove the wildcard from its public hostname to
   protect `onesa-engineering-docs.pages.dev`. Return to Pages and enable Access again
   to recreate preview protection. Verify separate application coverage for the exact
   hostname and `*.onesa-engineering-docs.pages.dev`, including commit and branch URLs.
   Apply the exact email allowlist to both; replace any generated membership-only policy.
   Follow [Cloudflare's Pages Access procedure](https://developers.cloudflare.com/pages/platform/known-issues/#enable-access-on-your-pagesdev-domain).
5. New organizations default to the Cloudflare identity provider with account-member
   restriction. Confirm that each allowed email has a usable login; the default does
   not establish that both addresses are Cloudflare account members. For email-code
   login, add One-time PIN under **Integrations → Identity providers** and select it as
   an application login method, while retaining the exact email policy. Email PIN alone
   does not satisfy the requested MFA. Enable **Access controls → Access settings →
   Allow multi-factor authentication (MFA)**, then enforce independent MFA in each docs
   application's **Authentication → MFA → Custom MFA settings**, with a security key or
   authenticator app and an initial 8-hour duration. Leave policy overrides inheriting
   this requirement. Cloudflare's IdP-based `Authentication method = mfa` selector does
   not list its own provider or PIN as supported; use
   [independent MFA](https://developers.cloudflare.com/cloudflare-one/access-controls/policies/mfa-requirements/).
6. Set Pages **Settings → Runtime → Fail open / closed → Fail closed**. The Free
   Functions quota must not cause authentication code to be skipped and static private
   assets to be served. See [Pages routing](https://developers.cloudflare.com/pages/functions/routing/#fail-open--closed).
7. Verify owner MFA enrollment and authentication before applying docs enforcement.
   Then verify anonymous denial and both approved logins against the harmless
   production and preview placeholders. Then configure the server-side values from
   `infra/cloudflare-docs/access.env.example` in **both Production and Preview**: actual
   team domain, the application AUDs, the exact two emails, and allowed hostnames.
   AUD values come from each application's configuration. These are separate from an
   AI Worker API credential. Missing bindings cause the internal Worker to deny access.

### Build the engineering artifact after Access verification

The actual framework is **Docusaurus 3.10.2**, with internal output at
`onesa-ai-platform-frontend/apps/docs/build-internal`. A raw Docusaurus output is
insufficient: package it with the Advanced Mode Worker and `_routes.json` so **every**
request validates the Access signature, issuer, audience, expiry and exact email
before calling `ASSETS`. This includes search indexes, JS/CSS, diagrams, schemas and
direct PDFs. The packaged directory is `build/cloudflare-docs`. See
[Advanced Mode](https://developers.cloudflare.com/pages/functions/advanced-mode/).

Use the supported Node 24/Python 3.11 environment and locked dependencies from
[BUILD_AND_TEST](BUILD_AND_TEST.md). Regenerate assets from reviewed source and set the
deployed origins before building:

```sh
make docs-assets
ONESA_DOCS_HOSTING=cloudflare-access \
  ONESA_DOCS_URL=https://onesa-engineering-docs.pages.dev \
  ONESA_PUBLIC_DOCUMENTATION_URL=https://docs.onesa.eu \
  ONESA_APPLICATION_URL=https://platform.onesa.eu \
  make docs-internal
make docs-validate docs-check
make docs-cloudflare-package
```

The final command requires a new output location; use `prepare_cloudflare.py --output`
with another private build location if the bootstrap already occupies it. Never reuse
or deploy a raw `build-internal` directory. Only upload the reviewed wrapped output
to the identified Pages project after the Access/fail-closed checks. The bootstrap
Git command stays placeholder-only; it does not automatically start publishing
engineering docs. If selecting Wrangler Direct Upload initially, do not assume it
can later become a Git-integrated project; select the project type deliberately.
No provider credentials are added to editable GitHub workflows by this preparation.

When using Wrangler with a Git-integrated project for the wrapped release, first
disable automatic production and preview builds after the bootstrap. Otherwise a
later Git push can replace the reviewed engineering artifact with the placeholder.
Cloudflare supports Wrangler deployment to an existing Git-integrated project after
[disabling automatic deployments](https://developers.cloudflare.com/pages/configuration/git-integration/#disable-automatic-deployments).

`ONESA_DOCS_HOSTING=cloudflare-access` disables the documentation assistant's form:
this Pages Worker serves authorized GET/HEAD requests and has no hosted inference
gateway. Guides, downloads, search and read-only API reference remain available.

### Optional custom hostname and hosted acceptance

Read-only DNS inspection on 2026-10-12 returned Cloudflare nameservers
`elijah.ns.cloudflare.com` and `tina.ns.cloudflare.com` for `onesa.eu`; no CNAME was
returned for `engineering.docs.onesa.eu`. Account/zone ownership and the full record
set still need readback in the existing account. No nameserver or DNS changes were made.

While only the harmless bootstrap is deployed, add `engineering.docs.onesa.eu` through
the Pages **Custom domains** flow, verify TLS, then create its own **Self-hosted and
private** Access application with the same email/MFA/session policy. Cloudflare lists
an already-protected hostname as a Pages custom-domain setup limitation, so attaching
it during the bootstrap avoids exposing internal material during certificate setup.
Inspect the actual custom-domain/DNS result; do not add a CNAME without registering
the domain in Pages. After its policy works, add this hostname and its AUD to both
runtime environments. See [custom domains](https://developers.cloudflare.com/pages/configuration/custom-domains/)
and [known issues](https://developers.cloudflare.com/pages/platform/known-issues/#custom-domains).

Keep the protected `pages.dev` hostname initially if custom-domain setup is pending.
For every configured hostname, test the homepage, a real guide, a real schema/search
index and a real PDF in a private browser: anonymous and unrelated authenticated
identities must receive Access login/denial, never engineering bytes; each approved
email must pass MFA and load the same artifacts. Test at least one actual commit URL
and branch alias and review wildcard coverage. Confirm Functions failure is closed
and missing runtime bindings deny access. Record real provider and browser evidence
before marking hosted engineering access qualified. Local security tests establish
the wrapper behavior only, not dashboard policy enforcement.

Local validation on 2026-10-12: four packaging regressions, ten signed-token/host/asset
Access tests and thirteen existing documentation dependency-security tests passed.
The dependency suite's file-watcher case required execution outside the filesystem
sandbox. TypeScript checking, an internal Docusaurus build with deployed origins,
the unavailable-assistant HTML check and repository publication hygiene passed.
The isolated build used existing generated source assets; it is validation output,
not a freshly regenerated, release-qualified artifact. No hosted Access enforcement
or authenticated browser acceptance is claimed.

## Acceptance

Verify home/guides, local search, read-only API schema, 19 public diagrams and
11 public manuals on desktop/mobile. Confirm `/database` and internal paths
are absent and static assistance clearly reports unavailability. Retest the
actual Vercel URL, then `https://docs.onesa.eu` after DNS/TLS verification. The
application production release remains NO-GO independently of public docs.

## Ecosystem source synchronization

The two sibling products remain independent repositories. Reviewed contract and
schema snapshots live in `docs/ecosystem`, pinned by source commit and file hashes
in `source-revisions.json` and `snapshot-hashes.json`. Public hosted documentation
CI checks out those exact Portal/Robot commits with persisted credentials disabled
and verifies the source fingerprints. It does not follow another product's mutable
main branch or query any live database. The public Portal spec includes only
`/api/v1/public/*`; full administrative contracts and complete SQL-derived schemas
remain in the engineering build. Robot's simulator contract is separately selectable.

On a major architecture change, export that product's actual contract, review the
schema/source changes, update its pin and fingerprints, regenerate snapshots and
run the classification, browser and schema-drift gates. Private deployments require
approved local cross-project source access; no cross-repository token is introduced
by this change. Existing public snapshots do not certify newer product revisions.

## Acceptance commands and artifact scope

Run `make docs-assets`, then public/internal builds and `make docs-validate`.
The ten requested ecosystem engineering manuals are additional to the 12 existing
engineering references. The approved public four product/system manuals supplement
the seven existing public guides. A4, bookmarks, pages, version and source hashes are
validated from real PDFs. Large Portal ERDs have five readable subject exports.
Use the standalone static gate with production origins:

```sh
ONESA_DOCS_STATIC_HOSTING=true ONESA_DOCS_URL=https://docs.onesa.eu \
  ONESA_APPLICATION_URL=https://platform.onesa.eu \
  npm --prefix onesa-ai-platform-frontend/apps/docs run build:public
make docs-static-acceptance
```

This gate uses a local static server and synthetic browser context; it checks all
public diagrams and PDF downloads, real product specs, private-path denial, search,
keyboard controls, internal links, robots/sitemap, 320/390/768/1024/1440px widths and
automated WCAG serious/critical violations. Manual accessibility acceptance and
hosted engineering identity checks remain separate. All existing application tests,
security gates, production guards and private-runner requirements are retained.

## Observed domain state — 2026-10-11

The public resolver returns CNAME `15e3ff75c7141bd0.vercel-dns-017.com`.
The actual custom domain passed HTTPS and returned 200 for the homepage, sitemap,
public diagram catalog and manuals catalog; `/robots.txt` returned 404. Private
schema requests returned 404. Thus the earlier NXDOMAIN/sitemap-resolution failure
is not currently reproducible. Its historical cause cannot be established from
current successful DNS alone. No DNS change is needed or authorized by this finding.
Publish only the qualified public artifact to correct the missing robots response,
then recheck actual domain, release metadata, links and artifact boundaries.

Deployment verification also checks the actual Vercel deployment ID, separate
project identity, READY status and `onesaSourceRevision` against the workflow SHA.
Production runs execute the public browser/asset acceptance against docs.onesa.eu.
The production workflow still requires main; a feature/audit branch cannot promote
production. Existing domain assignments are read only; missing assignments require
the owner's configuration action.

## Public repository and internal source distinction

All three repositories are currently public. On 2026-10-12 the owner confirmed that
the source repository will become private at official Onesa UG launch; this task
does not change repository visibility. Generic software
implementation references and migration definitions in Git are public source, even
when only the engineering build renders them. This work adds no live database
export, credential, customer document or restricted incident evidence. Private
engineering hosting protects generated pages/assets, not the public Git history.
An owner classification decision is required if implementation-reference source
itself must be private; use a separately protected source/publishing boundary.
Do not silently change repository visibility or publish confidential source.


## Build context and design contract

Set `ONESA_DOCS_ENVIRONMENT=staging` for an approved preview/Pages staging build and `production` only for the qualified production artifact. Values are validated as development, staging or production; absent local configuration defaults to DEVELOPMENT. The public hosting workflow selects its value from the trusted target input. Access audience and deployment context are separate from system appearance; no hostname/query parameter determines either. Browser/OS preference controls both classified builds without a manual selector or stored appearance override.

From the reviewed AI repository root, generate/validate assets first, then build the actual target:

```sh
ONESA_DOCS_ENVIRONMENT=staging ONESA_DOCS_HOSTING=cloudflare-access ONESA_DOCS_URL=https://staging.onesa-engineering-docs.pages.dev npm --prefix onesa-ai-platform-frontend/apps/docs run build:internal
ONESA_DOCS_ENVIRONMENT=production ONESA_DOCS_STATIC_HOSTING=true ONESA_DOCS_URL=https://docs.onesa.eu ONESA_APPLICATION_URL=https://platform.onesa.eu npm --prefix onesa-ai-platform-frontend/apps/docs run build:public
```

These commands build source; they do not upload or prove qualification. Preserve existing Access bindings, approved identity/MFA and all-path verifier when packaging internal output with `scripts/docs/prepare_cloudflare.py`. Its provenance must match the committed current source. Public upload remains the independent `docs-hosting.yml` target workflow; production requires qualified main. The observed protected reference is [Onesa Design System](https://staging.onesa-engineering-docs.pages.dev/docs/architecture/ONESA_DESIGN_SYSTEM); verify that exact candidate route after upload. The proposed engineering custom hostname is not assumed assigned.
