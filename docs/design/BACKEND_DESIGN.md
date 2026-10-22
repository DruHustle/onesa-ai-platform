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

Additive migration `20261021_industrial` creates only the new table and user ownership
index. Its downgrade refuses destructive rollback. With the demo disabled, the new API
accepts the prior schema or the new additive head. Enabling it requires the new head.
An older binary still requires its old head: a schema rollback must use the reviewed
forward compatibility/recovery process, never delete saved investigations. Actual hosted
migration and runtime grants need separate staging verification before production.
