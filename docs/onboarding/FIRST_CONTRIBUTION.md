# First Engineering Contribution

Open the [interactive contribution workflow](/architecture?diagram=first-contribution). Read the owning repository's `AGENTS.md`, current roadmap, test guide and actual deployment evidence before changing source. Start with a bounded documentation or UI correction on the existing `dev` branch; preserve concurrent changes. No additional branch is needed.

1. Trace affected source, API model, storage and permissions. Explain the expected behavior and a meaningful verification.
2. Make the smallest complete correction. Update the canonical diagram, contract or runbook if behavior changes. Use synthetic data; do not modify secrets or production records.
3. Run focused checks and publication hygiene. For diagrams run `.venv/bin/python scripts/docs/generate.py`, `node scripts/docs/render.mjs`, both classified builds and `.venv/bin/python scripts/docs/validate.py`.
4. Inspect `git diff --check`, `git diff --cached` and `git status --short`; stage only reviewed paths. Commit and push `dev`, then open or update its PR to `staging`.
5. Require the exact source's full CI, security checks and hosted synthetic acceptance. Failure returns to `dev`; a local pass or unchecked checkbox does not qualify production.
6. Promote qualified `staging` to `main` only through the owner-authorized release path with real technical, privacy, operations and content gates. The single owner's existing authorization does not waive failing checks.
7. Verify provider deployment IDs, actual source, live behavior and recovery. Record redacted evidence in the restricted audit trail. Keep physical robot control disabled.

## Completion checklist

- [ ] Existing dev branch and concurrent work preserved.
- [ ] Focused checks, security and documentation validated.
- [ ] Reviewed diff excludes secrets and live records.
- [ ] Exact-source CI and staging acceptance recorded.
- [ ] Production qualification and live verification recorded if promotion occurs.

[Delivery](DAY_3.md) · [Security](../security/SECRETS_MANAGEMENT.md) · [Recovery](../operations/RECOVERY.md).
