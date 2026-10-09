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
