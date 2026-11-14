# Day 2 — Understand the software

Open the [interactive Day 2 workflow](/onboarding#day-2). Source: `docs/diagrams/day-two.mmd`; SVG/PNG/PDF exports are available from the diagram viewer. Reviewed 2026-10-13; distinguish implementation from hosted acceptance.

## Learning objectives

- Trace one endpoint from frontend to API schema and storage.
- Explain session CSRF roles and ownership.
- Prepare isolated development without production data.

## Practical checkpoints

- [ ] Choose an endpoint in the API explorer and identify its request/response model.
- [ ] Find the owner foreign key in a generated ERD.
- [ ] Run publication hygiene locally and use synthetic development fixtures.

## Detailed references

- [Local Development](/docs/deployment/LOCAL_DEVELOPMENT)
- [Authentication](/docs/api/AUTHENTICATION)
- [Schema](/docs/database/SCHEMA)
- [Portal Database](/docs/ecosystem/PORTAL_DATABASE)
- [Robot Database](/docs/ecosystem/ROBOT_DATABASE)

## Source and local commands

AI: `onesa-ai-platform-frontend/apps/chat`, `onesa-ai-platform-backend/app/main.py`, `app/auth.py`, `app/models.py`, and `migrations/versions`. Portal: `onesa-company-portal-frontend/src/app`, `onesa-company-portal-backend/src/app.ts`, `src/jobs/worker.ts`, and `migrations`. Robot: `onesa-ai-robot-frontend`, `onesa-ai-robot-backend/robot_api/main.py` and `robot_api/safety.py`. Cross-project APIs and SQL snapshots pin reviewed revisions; builds do not silently import sibling source.

From the chosen repository, first read `AGENTS.md` and its build guide. In AI, use `python3 scripts/repository_hygiene.py`, `npm --prefix onesa-ai-platform-frontend run typecheck` and `.venv/bin/python scripts/docs/generate.py`. Use the existing isolated `_test` PostgreSQL guide before running destructive integration fixtures. Never point test reset commands at staging or production.


## Shared interface contract

Read [Onesa Design System](../architecture/ONESA_DESIGN_SYSTEM.md) and the pinned consumer manifest before frontend changes. AI and Docs retain distinct product shells over shared semantic tokens. Browser/OS preference controls appearance without selectors, clock timers or stored overrides. Verify drafts, focus, streams, forced colors, reduced motion and affected routes in both modes; local verification does not prove deployed acceptance.
