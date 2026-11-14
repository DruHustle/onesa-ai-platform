# Backup and restore

## Current Oracle scope and restored-copy erasure replay

Recurring encrypted AI and Robot production backups are enabled on the existing
Oracle operations system. Their hourly timers were activated on 2026-10-17 after
one authorized off-instance snapshot and independent isolated restore per product.
The current timer readback, verified on 2026-10-18 (Europe/Berlin), shows both
timers active/enabled and both services completing successfully. The AI restore
covered 18 PostgreSQL tables; the Robot restore covered its task and lease tables.
Existing Portal backup and monitoring timers remain separate and active.

Each product uses its own prefix in the existing private storage and a 64 MiB
ciphertext-prefix budget. Automatic archive deletion remains disabled pending the
owner's retention decision. A full budget must produce a monitored failure, not
silent pruning or a false successful backup. Use the existing restricted activation,
timer and restore receipts for exact objects, digests, key identity and measured times;
none of those private identifiers belongs in a website export.

Safe metadata checks on the approved VM are:

```sh
systemctl list-timers onesa-database-backup-ai.timer onesa-database-backup-robot.timer
systemctl show onesa-database-backup-ai.service onesa-database-backup-robot.service \
  --property=Result --property=ExecMainStatus --property=ExecMainExitTimestamp
```

These reads do not start a backup. Correlate successful service exit with the existing
operations success receipt and off-instance verification; a timer file alone is not
backup acceptance. If runtime configuration changes, the profile's identity/hash
guard stops the backup. Review the actual target and approved binding rather than
bypassing that guard or copying credentials into a runbook.

The earlier 2026-10-16 one-time AI snapshot remains historical recovery evidence.
Scheduled copies, independent key recovery, isolated restoration and permission to
activate a restored application are separate decisions. No live restore is authorized
by the backup schedule, and an observed hourly interval is not an approved RPO/RTO.

Before activating any restored copy, reconcile erasures after its snapshot and
invalidate restored sessions, invitations, grants, queued mail, upload/model leases
and unfinished inference. The existing lockdown command now has an explicit
isolated replay mode:

```sh
python3 scripts/release/restore_lockdown.py \
  --container onesa-isolated-ai-restore-<run-owned-hex> \
  --database onesa_<run>_restore \
  --replay-ledger <private-reviewed-ledger.json> --apply-isolated-replay
```

The container must be running with network `none`, no published ports or persistent
mounts, and explicit `org.onesa.restore-scope=isolated`, `org.onesa.product=ai` and
`org.onesa.restore-snapshot-sha256` labels matching the verified archive. The command
validates the name, labels and immutable container ID before any SQL. This command
never contacts the live database or restores into an application container.

The mode-600 owner-held ledger uses schema `1`, product `ai`, the verified
`source_backup_sha256`, timezone-aware `backup_created_at`/`reconciled_through`, and
complete `events` and `legal_holds` objects. Both objects contain the arrays
`deleted_users`, `deleted_conversations`, `deleted_documents`, `deleted_trips` and
`deleted_agent_runs`; empty categories must be explicit. Values are canonical UUIDs.
An event conflicting with a hold is rejected before SQL. Supply actual authoritative
post-snapshot events, not draft policy periods or invented approvals. Keep record
identifiers and the ledger out of public documentation and CI artifacts.

Replay is atomic and idempotent. User/record deletion uses the application's foreign
key cascades; document replay also removes associated staged-upload chunks. Failure
rolls back the transaction. All restored capabilities remain revoked, and unfinished
inference/agent work is failed rather than resumed. The receipt states
`activation_authorized: false`: the owner must still establish complete ledger
coverage through the required recovery watermark, archive/schema/record integrity,
key availability and release authorization. Missing or incomplete ledger evidence
blocks activation. This tool does not create a production erasure policy or prove
that an old snapshot includes deletions made after its recorded watermark.

Run `python3 -m unittest discover -s scripts/release -p test_restore_replay.py`
for isolated input/target/hold rejection checks. Real PostgreSQL fixture evidence
is retained privately; synthetic results are distinct from production-data restore.

## Local Compose backup commands

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
