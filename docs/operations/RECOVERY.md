# Recovery

Conversation/run state survives API restart in PostgreSQL. Active generation leases expire
after the configured deadline+10 seconds; next request marks the prior run failed and starts
a new owned run. Partial assistant output is never saved as successful completion. Agent runs
are bounded and stale unfinished runs fail on inspection; there is no restart-resumable queue.

Backups use pg_dump and restoration into a new `_restore` database. Verify migration revision,
counts and representative content/ownership before manual promotion. The local restoration
of users/messages/documents/trips/agent records was exercised; production disaster recovery,
off-host copies, encryption and RPO/RTO remain unconfigured.

Recover serving by selecting a previously evaluated model/adapter and compatible platform
revision. Multi-host routing/failover and automatic deployment rollback are future capabilities.
See RUNBOOK.md, BACKUP_RESTORE.md and implementation status for exact observed evidence.

## Executed acceptance 005 recovery

The encrypted automation described here supersedes the earlier local unencrypted-template
limitation. `infra/operations/worker.py` performs custom-format pg_dump using a separate
SELECT-only role, validates archive structure, encrypts with AES-256-GCM and fresh random
nonce, atomically publishes and retains seven days by default. Plaintext exists only within a
private temporary directory; processing/hashing is streamed. An independently mounted 32-byte
key and authenticated operations token are separate from DB owner credentials. Startup and
actual timer execution were exercised at a short 30-second test interval, then restored to
3600 seconds. A synthetic expired encrypted copy and manifest were pruned; recent backups
were preserved. Credential failure generated a real delivered backup alert and resolution.

All implemented private document storage is inside PostgreSQL: extracted text, vectors,
metadata, stored excerpts and references. The encrypted DB backup therefore covers it alongside
users, sessions, conversations/messages/generation runs, agent records and trips. Original
uploaded binary files are discarded after extraction; there is no external object store/file
reference requiring a separate restore today. If one is added, versioned object snapshots and
referential integrity qualification must accompany database snapshots. Model cache and approved
training artifacts are separate asset/provenance workflows, not private document storage.

```sh
# Set archive name from privately authenticated operations status; never print credentials.
docker compose --env-file data/acceptance-005/staging.env -p onesa-acceptance-005 \
  -f compose.yaml -f compose.production.yaml -f compose.acceptance.yaml \
  --profile recovery run --rm \
  -e ONESA_RESTORE_DATABASE=onesa_manual_restore \
  -e ONESA_RESTORE_ARCHIVE=<existing-name.dump.enc> restore
```

Restore authenticates the entire ciphertext before creating a database, uses owner credentials
only in the separate recovery container, requires a new safe `_restore` name and refuses an
existing database. It does not drop/clean the live DB. Tests reject tampered, wrong-key and
truncated ciphertext. `scripts/acceptance/operations.py` exercises actual delivery/recovery and
creates a unique restore database; all public-table counts and sorted row-content fingerprints
must match. Evidence covers every implemented data table and migration revision. Keep
restored validation databases until the operator has reviewed evidence; no promotion occurs.

`rollback.py` tags the still-preserved main API/frontend images, applies them only to staging,
checks the same session and user/conversation/document/agent/trip records, and returns to the
new staging images. Schema `608f3f79f76e` is unchanged. Migration upgrade/downgrade round trips
are tested in the isolated test DB; rollback across a future incompatible schema requires a
reviewed migration/restore plan and cannot be assumed safe.

Local same-host volumes do not survive total host loss. Independent encrypted off-host copies,
separate recoverable key custody, operator access/recovery drill, production-scale retention,
RPO and RTO decisions are BLOCKED. Record the measured snapshot/restore time and point-in-time
integrity separately from any business recovery objective; zero loss within a matched snapshot
is not a zero production RPO claim. Configure object/disk encryption and disaster recovery on
the actual host before public promotion.
