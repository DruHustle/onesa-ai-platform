# Changelog

## 2026-10-16 — Protected Oracle VM operations documentation

- Added the shared VM layout, exact API routes/loopback ports, environment isolation,
  worker/scanner boundaries, Tailscale administration and resource limits.
- Linked read-only troubleshooting, monitoring, backup and recovery procedures from
  maintained deployment references; private runtime values and evidence remain excluded.
- Documentation changes do not deploy, restart or qualify an application.

## 2026-10-16 — AI Platform production API moved to Oracle

- Moved the existing qualified backend to an immutable, scanned ARM64 image on
  the existing Oracle Free VM, behind a dedicated HTTPS tunnel and loopback bind.
- Republished the identical accepted frontend artifact with its server-side API
  origin changed. Existing authenticated access, protected reads, logout/revocation
  and anonymous denial pass through the production website.
- Preserved accounts, credentials, external data and existing worker/scanner services.
  No Render build, paid resource, schema migration or physical actuation occurred.
- Prior full application qualification is reused for unchanged source; new target
  checks establish access and readiness, not a new feature or inference release.
  Staging Preview acceptance remains independently recorded in restricted evidence.


The platform remains under development. These entries record verified hosting
and pre-launch releases; broader launch qualification remains separate.

Current qualification work defers Docs search-index loading until search is
opened and qualifies public Docs independently with exact production-context
artifacts. Docs authorization does not authorize the AI application or API.
Maintained product copy uses count-neutral wording; protected public Docs Preview
tests keep their credential within the verified deployment origin.
Public Docs archive verification uses the producer's path ordering and retains
the exact build and archive digest checks.
Prepared protected Docs custody uses a conditional owner handoff with staging
blocked and all deployment grants false until external live validation. Private
site bytes stay outside GitHub artifacts; full and public release gates remain
independent.
