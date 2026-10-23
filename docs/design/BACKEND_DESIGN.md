# Backend design

FastAPI create_app wires validated settings, optional PostgreSQL engine, ModelClient,
itinerary planner and domain routers. SQLAlchemy sessions are request-scoped; short
transactions enforce ownership. Engine pooling uses pre-ping and a 3-second connection
timeout. Readiness requires the known Alembic head when a database is configured.

Auth/CRUD endpoints use synchronous functions in FastAPI's worker threads. Streaming,
model planning and upload reads use async functions; some short database operations
inside these paths are synchronous. This is a bounded MVP, not a high-throughput async
ORM claim. Move blocking work to isolated workers/async sessions after measured load.

Pydantic validates inputs and forbids extra fields. HTTP/domain errors use sanitized
error envelopes and correlation IDs; validation never echoes submitted passwords.
A 6 MiB ASGI body bound precedes parsing. Chat locks a conversation only during lease
acquisition/completion; deadline+10-second expiry prevents permanent busy states.

Domain boundaries and real behavior are described in architecture/DATA_FLOWS.md.
No code executes arbitrary model-proposed commands or user-provided external URLs.
Runtime OpenAPI, Swagger and ReDoc routes are disabled. Contract generation still
uses the application schema offline; publication follows documentation classification.


## Industrial Investigation V1

Investigation creation serializes the user’s identifier, saved-count check and insert
in one transaction; parallel submissions preserve the per-user limit and idempotency.

`industrial_evidence.py` contains original, versioned synthetic inputs and deterministic
interval/quality/provenance validation. Calculation windows contain only normalized
UTC start/end, so a preview and its saved investigation have identical observed facts
independent of the creation UUID. `industrial.py` reuses Auth, Knowledge embeddings,
ModelClient and shared model admission. Owned investigation rows keep snapshots, facts,
generation states, revision-checked internal drafts and immutable prior review decisions.
No retrieval cache or organization tenancy is introduced. A current asset/version/anchor
and literal source quotation are required; generation cannot modify calculated facts.
Provider failure, empty output, cancellation and interrupted persistence remain explicit.
Whitespace-only fields are rejected. Each claimed generation records configured
model identity, observed token counts where available, unknown cost and its terminal
outcome; cancellation or interrupted recovery does not invent a response or elapsed
time. Long-running completion revalidates the current session, account and access grant
before returning private state. Terminal facts remain recoverable after access renewal.

Evidence validation rejects contradictory records sharing a signal ID or a reference
`(id, version, anchor)` key, even when each reference independently has a valid text
hash. Exact repeats and distinct reference versions/anchors remain valid; validation
does not rewrite or deduplicate the saved snapshot. Signal timestamps are compared
after UTC normalization. The bundled conflict scenario remains valid because it uses
different reference versions; coverage must still flag that semantic disagreement.
Offline regressions are in `tests/test_industrial_identity.py`. This strengthens the
synthetic evidence boundary without adding an external-data ingestion endpoint or
establishing general semantic correctness of model hypotheses.

The workspace locks selection during mutations, including cancellation. A completion
race is reconciled with one read rather than another write. Refresh updates the visible
draft and its baseline together, after explicit discard confirmation for unsaved work.
Review is permitted only for that saved, displayed revision. Ordinary requests have a
bounded observation deadline; a timeout is not proof that a server mutation failed.

Additive migration `20261021_industrial` creates only the new table and user ownership
index. Its downgrade refuses destructive rollback. With the demo disabled, the new API
accepts the prior schema or the new additive head. Enabling it requires the new head.
An older binary still requires its old head: a schema rollback must use the reviewed
forward compatibility/recovery process, never delete saved investigations. Actual hosted
migration and runtime grants need separate staging verification before production.

### V1.1 review delta and evaluation

The observation loop and final persistence both require the exact claimed running
revision. Cancellation followed by a new generation cannot keep the old local
observer consuming its lease until the newer generation finishes. Local task
cancellation still does not guarantee upstream provider computation has stopped.

Incomplete downtime, including excluded bad/unknown-quality events, now abstains
before retrieval/model execution. The displayed known duration remains a lower
bound. No historical investigation is rewritten. Citation identity, applicable
version/anchor and literal quotation checks are structural: a perfectly quoted
source can accompany an unsupported causal claim. The versioned evaluator retains
that counterexample and leaves human support ratings unfilled.

`scripts/evaluate_industrial.py` consumes the frozen synthetic manifest in
`tests/fixtures/industrial-evaluation-v1.1.1.json`, which hash-binds and extends the unchanged original 39-case parent. Its optional `--database` mode
requires an explicitly configured loopback `_test` database, executes existing
API/state regressions with mocked inference, and separates those results from
factual checks, model quality, actual usage and human acceptance. No schema change,
production migration, database repair or new provider is introduced by this delta.
