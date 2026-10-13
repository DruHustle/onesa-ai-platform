# Day 3 — Understand delivery

Open the [interactive Day 3 workflow](/onboarding#day-3). Source: `docs/diagrams/day-three.mmd`; SVG/PNG/PDF exports are available from the diagram viewer. Reviewed 2026-10-13; distinguish implementation from hosted acceptance.

## Learning objectives

- Explain dev → staging → main and actual workflow entry points.
- Match a CI run to its source revision and provider deployment.
- Recognize failures and the rollback boundary.

## Practical checkpoints

- [ ] Read deploy.yml and release-candidate.yml in their owning repositories.
- [ ] Explain why private GitHub Free protection cannot be assumed.
- [ ] Describe recovery after a failed hosted check without skipping it.

## Detailed references

- [Ci Cd Pipeline Report](/docs/development/CI_CD_PIPELINE_REPORT)
- [Free Github Plan](/docs/development/FREE_GITHUB_PLAN)
- [Deployment](/docs/engineering/DEPLOYMENT)
- [Recovery](/docs/operations/RECOVERY)

## Actual delivery entry points

Portal and AI use the registered `deploy.yml` staging bridge with `target=staging`, `fixture_mode=temporary` and `application=both`. Robot uses `release-candidate.yml` with `target=staging` and `application=frontend`. Trusted jobs validate actor, source and exact targets before loading secrets. Oracle uses Portal `scripts/oracle_worker.py` with exact qualified staging SHA and separately verified synthetic data. Documentation uses `docs-hosting.yml` and classified public output; engineering Pages needs separate protection qualification.

The retained local runner is a private-only, isolated option and is dormant. GitHub-hosted review and mandatory checks do not depend on it. Private GitHub Free does not provide paid branch/environment protections. Current public repository environment secret availability is separately verified; repository-level fallback is not environment isolation.
