# Complete Onesa system architecture

## Scope and source of truth

The company, AI and Robot repositories are independent deployments, not submodules. Read the reviewed public ecosystem guide for product boundaries. The public documentation is an allowlist; detailed schema, administrative API and operational references are internal only. Review source-revisions.json when cross-project architecture changes and regenerate contracts from each pinned implementation.

## Communication boundaries

Browsers use their own product's same-origin proxy and scoped sessions. Company public operations and Portal administration have different allowed paths/origins. AI uses invitation/identity and ownership policies. Robot has a separate operator identity; proposed AI integration must consume authorized versioned APIs instead of private database tables. PostgreSQL and object storage are not model servers.

## Qualification

As reviewed on 2026-10-13, Oracle Portal staging jobs, ClamAV scanning and bounded queue/recovery tests have passed. Workers AI generation and semantic embedding probes and an earlier hosted AI acceptance passed. Portal and AI staging SQL bindings were corrected to distinct *-staging projects; new source deployments and hosted acceptance must requalify those bindings. Robot simulation uses a separate Turso staging journal; rolling-deployment lease handoff and production durability still require hosted acceptance. Physical actuation remains disabled. Engineering Pages has only a harmless staging placeholder. The origin and wildcard-preview Access applications, approved-identity MFA policies and both environment bindings are now verified. Fifteen anonymous page/asset/index/download probes redirect to Access login. Authorized-user/MFA completion and internal-content hosted acceptance remain pending. Local tests and documentation builds do not establish production qualification. Full private release evidence is excluded from both sites.

Use [Architecture & Workflows](/architecture), [Engineering Onboarding](/onboarding) and the [visual source index](VISUAL_WORKFLOWS.md).

## Architecture changes

Keep application release authorization, scopes and rollback paths independent. A public documentation release can be qualified separately, provided no internal artifacts or application changes are promoted. Cross-project snapshots pin actual source commits and hashes; updates must be reviewed rather than silently following unrelated repository main branches.
