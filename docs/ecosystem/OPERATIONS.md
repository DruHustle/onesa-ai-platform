# Operations, monitoring and recovery

## Readiness and outages

Check process liveness, database/core readiness and inference readiness separately. Record deployed revision before diagnosing old logs. Missing database credentials, unsafe role, incorrect root/CMD and missing model endpoints have different corrections. Preserve meaningful 503 failures and independently usable non-model routes. Free service cold starts are not a capacity or availability guarantee.

## Durable accepted work

Portal persists accepted enquiries/applications before asynchronous mail delivery; queue status distinguishes pending, leased, accepted and terminal failed. Final-attempt worker crashes must not leave permanent pending rows. AI identity notifications use bounded leases/attempts too. Robot proposals and sessions cannot recover execution authority automatically after restart.

## Restore acceptance

Inventory the intended database, schema and operational records before migration. Retain an encrypted access-controlled backup with verified checksums. Restore PostgreSQL in an isolated environment with the correct version/extensions and restricted role. Restore objects separately and verify authorization, checksums and deletion semantics. Restore Robot from an online SQLite snapshot; recheck stopped state, sessions revoked and history retained. Never test restore against a live application database.

## Alerts and incident response

Actual alert delivery, recovery owner, quota limits and retention must be configured and exercised. Do not promise monitoring after an interactive session ends unless a real deployed service delivers alerts. Logs must omit tokens, connection URLs, message contents and personal records. Privileged incident evidence remains outside generated documentation. Incident procedures and runbooks are internal references, not public downloads.
