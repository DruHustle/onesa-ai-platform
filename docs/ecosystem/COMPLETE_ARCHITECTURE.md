# Complete Onesa system architecture

## Scope and source of truth

The company, AI and Robot repositories are independent deployments, not submodules. Read the reviewed public ecosystem guide for product boundaries. The public documentation is an allowlist; detailed schema, administrative API and operational references are internal only. Review source-revisions.json when cross-project architecture changes and regenerate contracts from each pinned implementation.

## Communication boundaries

Browsers use their own product's same-origin proxy and scoped sessions. Company public operations and Portal administration have different allowed paths/origins. AI uses invitation/identity and ownership policies. Robot has a separate operator identity; proposed AI integration must consume authorized versioned APIs instead of private database tables. PostgreSQL and object storage are not model servers.

## Qualification

Hosted AI staging core has been checked, while generation and semantic embeddings are still unavailable. Portal's database-role/worker/runtime acceptance remains blocked. Robot persistent hosted acceptance and all physical hardware functions remain unqualified. Local tests, mock screenshots and documentation generation do not change those verdicts. Full private release evidence remains excluded from site generation.

## Architecture changes

Keep application release authorization, scopes and rollback paths independent. A public documentation release can be qualified separately, provided no internal artifacts or application changes are promoted. Cross-project snapshots pin actual source commits and hashes; updates must be reviewed rather than silently following unrelated repository main branches.
