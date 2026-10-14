# Start Here — Onesa Engineering

This is the New Engineer Onboarding Overview. Open the [interactive four-day learning path](/onboarding) and [Architecture & Workflows](/architecture). Learning checkboxes are private browser notes, never release qualification or access grants.

## How the Onesa system fits together

Portal, AI Platform and Robot are three independent repositories and deployments. Frontends use Vercel and their own same-origin proxies; APIs use Render. Portal uses PostgreSQL, private object storage and an Oracle staging worker with ClamAV. AI uses independent PostgreSQL/pgvector and configurable generation/embedding adapters, including Workers AI. Robot is software simulation; physical actuation is disabled. The [visual index](../ecosystem/VISUAL_WORKFLOWS.md) links editable sources and current evidence limits.

## Four days

1. [Day 1 — Understand Onesa](DAY_1.md).
2. [Day 2 — Understand the software](DAY_2.md).
3. [Day 3 — Understand delivery](DAY_3.md).
4. [Day 4 — Understand operations](DAY_4.md).

Then use [First Engineering Contribution](FIRST_CONTRIBUTION.md). Keep three permanent branches, with only the reviewed temporary security exception; do not reset another engineer's changes, process real candidate documents in staging or bypass production qualification.

## Documentation boundaries

Public guides are explicitly allowlisted. Engineering pages, schemas, diagrams and downloads use a separate build and server-side authorization. Restricted release evidence and corporate records are excluded from both sites. Current source repositories are public: hosted Access does not make committed source confidential. Credentials, live records and incident evidence belong in approved private stores, not source examples.


## Shared interface contract

Read [Onesa Design System](../architecture/ONESA_DESIGN_SYSTEM.md) and the pinned consumer manifest before frontend changes. AI and Docs retain distinct product shells over shared semantic tokens. Browser/OS preference controls appearance without selectors, clock timers or stored overrides. Verify drafts, focus, streams, forced colors, reduced motion and affected routes in both modes; local verification does not prove deployed acceptance.
