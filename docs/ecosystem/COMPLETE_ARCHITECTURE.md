# Complete Onesa system architecture

> Purpose: explain implemented trust boundaries and qualification. Audience: engineers and reviewers. Classification: internal engineering design. Owner: Onesa repository maintainers. Verified: 2026-10-13 against source and cited staging evidence; production acceptance remains incomplete. Applicable revisions are identified below and in generated provenance.

## Scope and source of truth

The company, AI and Robot repositories are independent deployments, not submodules. Read the reviewed public ecosystem guide for product boundaries. The public documentation is an allowlist; detailed schema, administrative API and operational references are internal only. Review source-revisions.json when cross-project architecture changes and regenerate contracts from each pinned implementation.

## Communication boundaries

Browsers use their own product's same-origin proxy and scoped sessions. Company public operations and Portal administration have different allowed paths/origins. AI uses invitation/identity and ownership policies. Robot has a separate operator identity; proposed AI integration must consume authorized versioned APIs instead of private database tables. PostgreSQL and object storage are not model servers.

## Qualification

Portal staging source `5062f7f` passed hosted workflow 38328994648, including private storage/scanning and isolation. Its same-source Oracle ARM64 worker passed benign/EICAR/failure/quarantine and bounded deduplication/retry/stale-lock/failure-cap/restart tests. AI staging source `8c576371` passed hosted workflow 38331890487 against the isolated staging database, using real Cloudflare inference, streaming, semantic embeddings and permission-filtered retrieval. Corrected Python database connections preserve verify-full and channel binding with the system trust store. The owner-authorized readback on 2026-10-13 verifies the production Portal database schema (20 tables/seven migrations before the additive governance rollout). Production AI serving credentials are configured and provider inference/embeddings have separate verification. Exact application production rollout, operational qualification and privacy publication remain distinct gates; no full production acceptance is implied.

Robot's separate Turso staging journal and physical prohibition remain intact. Exact-source staging CI passed at `97a84bf8`; hosted workflow 38330809449 failed at existing operator login HTTP401 before journal mutation or backend deployment. The current password is preserved. Production durability and physical hardware remain unqualified.

Engineering documentation is actually published at [protected staging](https://staging.onesa-engineering-docs.pages.dev), source `8c576371`, deployment `c1630e6d`. Owner identity/MFA, all-path JWT enforcement, private/no-store/noindex responses and fifteen anonymous origin/preview resource redirects passed. Full hosted interactions at the unchanged UI revision covered 16 architecture sections, four learning days, 292 exports and 18 layouts with no blocking automated accessibility findings. Public Preview workflow 38327330427 passed independently. No production or custom internal DNS publication is inferred. Source repositories currently read PUBLIC, so hosting protection does not establish source confidentiality. Restricted release evidence and actual records are excluded from both documentation outputs.

Use [Architecture & Workflows](/architecture), [Engineering Onboarding](/onboarding) and the [visual source index](VISUAL_WORKFLOWS.md).

## Architecture changes

Keep application release authorization, scopes and rollback paths independent. A public documentation release can be qualified separately, provided no internal artifacts or application changes are promoted. Cross-project snapshots pin actual source commits and hashes; updates must be reviewed rather than silently following unrelated repository main branches.
