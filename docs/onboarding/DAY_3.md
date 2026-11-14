# Day 3 — Understand delivery

Read the protected [Oracle VM architecture and troubleshooting](../engineering/ORACLE_VM_OPERATIONS.md) for the current shared host layout, exact health routes,
resource boundaries and safe incident response.

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

Local runners are removed; private validation uses included hosted capacity only. GitHub-hosted review and mandatory checks do not depend on it. Private GitHub Free does not provide paid branch/environment protections. Current public repository environment secret availability is separately verified; repository-level fallback is not environment isolation.


## Security update exception

The permanent branches remain dev, staging and main. Temporary Dependabot security-fix PRs and reviewed urgent candidates are permitted; ordinary version PR automation stays limit 0. Use credential-free hosted PR checks and the [security release procedure](../engineering/DEPLOYMENT.md#security-releases-and-permanent-branches). An urgent candidate excludes unfinished dev, qualifies in existing isolated staging and requires owner-controlled production release plus reconciliation into dev/staging. Never copy production secrets into bot jobs or enable blind auto-merge.
