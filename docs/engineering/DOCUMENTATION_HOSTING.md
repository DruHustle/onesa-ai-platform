# Onesa UG documentation hosting

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

`engineering.onesa.eu` is a proposed separate hostname, not a live service.
Never upload `build-internal`, `.generated/internal`, private audit evidence,
repository history or application env to this static project. The supported
internal gateway verifies existing Onesa sessions and engineering-user allowlists
for **every** page, index, asset and PDF, and fails closed when identity is
unavailable. A hidden URL or client-side login page does not provide this boundary.
The existing server gateway passes identity/asset denial and permission tests. A
separately approved authenticated hosted target and session-origin acceptance are
still required; public Vercel must never receive internal output.

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

All three repositories are currently public by owner choice. Generic software
implementation references and migration definitions in Git are public source, even
when only the engineering build renders them. This work adds no live database
export, credential, customer document or restricted incident evidence. Private
engineering hosting protects generated pages/assets, not the public Git history.
An owner classification decision is required if implementation-reference source
itself must be private; use a separately protected source/publishing boundary.
Do not silently change repository visibility or publish confidential source.
