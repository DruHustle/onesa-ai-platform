# Onesa UG documentation hosting

The owner selected **docs.onesa.eu** for public documentation and confirmed Vercel
public-use eligibility. The existing Docusaurus application remains within
`onesa-ai-platform-frontend/apps/docs`; the three repositories stay independent.
This currently documents the AI platform. Portal and Robot guides are not implied
complete by hosting it.

Only the 15 sources in `docs/documentation-policy.json` and approved public assets
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
- `target=production`: requires `main`, publishes public docs and attaches
  `docs.onesa.eu` to the independent Vercel project. Application production release
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
The hosted backend 503 and internal identity acceptance still need resolution
before the internal service can be qualified.

## Acceptance

Verify home/guides, local search, read-only API schema, four public diagrams and
seven public manuals on desktop/mobile. Confirm `/database` and internal paths
are absent and static assistance clearly reports unavailability. Retest the
actual Vercel URL, then `https://docs.onesa.eu` after DNS/TLS verification. The
application production release remains NO-GO independently of public docs.
