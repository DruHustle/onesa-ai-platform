# Backup and restore

Run from repository root with the same `.env` and Compose project as the deployment:

```sh
scripts/database/backup.sh data/backups/backup-YYYY-MM-DD.dump
scripts/database/restore.sh data/backups/backup-YYYY-MM-DD.dump onesa_new_restore
```

Set ONESA_PROJECT_NAME for an alternate Compose namespace. Backup uses custom-format
pg_dump, private umask, a temporary file and atomic rename; existing targets are refused.
Restore accepts only a new safe database name ending `_restore`, refuses existing databases
through createdb, and uses pg_restore --exit-on-error. It never cleans/overwrites the primary.
Inspect schema revision and row counts/content before any manual promotion.

Verified on 2026-10-09: a fresh verification snapshot restored migration head, 4 users,
4 messages, 1 document, 1 trip and 1 agent run into onesa_final_restore. A second restore
also demonstrated the earlier snapshot. These are local scratch tests, not production RPO/RTO.

Backups contain private content and password/session hashes. Encrypt/store off-host with
controlled access and test restoration regularly. Encryption, off-host retention, scheduled
backups and operational restore-time targets require deployment-specific configuration.

## Split verification and retention

The split snapshot `data/backups/platform-split-20261009.dump` was restored into
`onesa_split_20261009_restore`. All eleven public tables matched row counts and
content fingerprints, including sessions, chunks, rate buckets and inference runs.
Repeat without displaying private records:

```sh
.venv/bin/python scripts/database/verify_restore.py onesa_split_20261009_restore --output data/backups/new-verification.json
.venv/bin/python scripts/database/retain_backups.py data/backups --days 30
# After reviewing the preview, add --apply to remove expired dumps, keeping the latest.
```

The whole backup-and-local-restore invocation took less than one second in this
small developer database. This is a tool measurement with local cached storage,
not an operational recovery objective. Target RPO/RTO, scheduled encrypted off-host
copies, credential custody and restore duration on production-sized data are pending.
The existing original/extracted knowledge content, embeddings and user state live
in PostgreSQL, so this snapshot covers their implemented storage. Future object
storage needs private versioned backup and an independently verified restore.
Model weights and original evaluation/runtime artifacts remain under ignored root
`data/`; preserve this tree separately with approved private encrypted snapshots.
Never publish data snapshots with the code/image. Generated classified documentation
can be reproduced; protected internal exports still require access-controlled backup.
