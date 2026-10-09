# Secrets management

Run scripts/bootstrap_env.py once: it writes random URL-safe database/model/metrics values
in a new mode-0600 .env and refuses overwrite. Git and Docker contexts exclude .env. Never
print/commit session tokens, keys or real connection credentials. Example/test credentials
are only for dedicated disposable `_test` databases.

The model/embedding API keys stay in private server configuration, never browser metadata.
Metrics has its own credential. Production refuses short/missing metrics configuration and
insecure cookie/origin settings. Session tokens are stored only as hashes; refresh/logout
rotate/revoke them. The browser stores cookies, not localStorage credentials.

For production use an operator-managed secret store/mounted files and controlled env
injection. Rotate database/model/metrics credentials with coordinated consumers; an env
change alone does not reset an existing PostgreSQL volume's password. Protect encrypted
backups and TLS state. No external secret store/rotation automation is configured here.

## Acceptance 005 secret custody and rotation

`bootstrap.py` creates independent staging credentials once under ignored
`data/acceptance-005/`, private directories (0700) and env file (0600). Mounted secret files
are host-directory protected and readable by the non-root selected container. Owner credentials
are restricted to migration/provisioning/recovery; API uses the separate CRUD role and the
backup worker uses SELECT only. The local AES key is not a production key-management service.
Never run `compose config` without `--quiet` into published evidence or upload private env,
CA keys, cookie jars, backups or raw Docker inspection. Production images contain source and
locked dependencies; runtime environment and secrets are supplied separately.

Rotation is an operator procedure, not an executed claim: create a protected candidate
credential, update the PostgreSQL role and the corresponding private runtime secret together,
restart only affected staging services and verify readiness/owned workflows/new backup.
Update Prometheus credential file and API token together; update Alertmanager/worker token
in tandem and repeat delivery. Revoke affected AuthSession rows through a reviewed privileged
operation for compromised sessions. Do not log SQL with passwords. For backup-key rotation,
retain protected old keys with their archive version until every retained snapshot has been
reencrypted or expired and a new-key restore has succeeded; replacing the current key alone
makes old archives unrecoverable. Keep key custody independent from archive custody off-host.

`check_secrets.py` scans tracked and non-ignored new source files for known credential patterns.
`scan_artifacts.py` additionally scans current development/staging secret values through
actual generated assets and selected exported image layers. These gates do not detect every
possible secret or replace a production secret manager. Secrets and private evidence stay
ignored; sanitized result JSON is the only acceptance evidence copied into documentation.
