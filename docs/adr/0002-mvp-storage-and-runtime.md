# ADR 0002: Bounded MVP storage and runtime

Date: 2026-10-09. Status: adopted.

Context: deliver working dependent features without premature services/packages.

Decision: keep Chat, Knowledge, Agents and Travel as routes in one Next.js application,
sharing auth and deployment. Keep reusable Python interfaces in domain modules until
multiple consumers justify extracting installable packages. PostgreSQL JSONB stores
message content/sources, typed itinerary days/activities and bounded agent step outcomes;
these are structured validated records, not opaque AI transcripts. Keep bounded extracted
document text in PostgreSQL; raw-file/S3 lifecycle and asynchronous parser workers are
future extensions. Use exact owner-filtered pgvector search for this small MVP.

Provide a deterministic lexical vector baseline for CPU tests and a versioned HTTP
embedding adapter with an explicit fixed 256-dimension schema. This is not a claim that
lexical hashing is semantic model inference. Dimension changes require a migration and
reindexing. The real model client and embedding service remain separate dependencies.

Consequences: simple transactional ownership/deletion and one frontend lockfile/deployable.
JSONB structure is validated by Pydantic; normalized child tables/indexes can be added if
queries require them. PDF work is bounded but not process-isolated; production hostile-file
hardening remains a qualification item. External travel providers remain explicitly
unavailable instead of fabricated. Agents only execute safe registered local computations.

Alternatives: separate frontends/services, raw files/object storage now, normalized tables
for every itinerary/step, large embedding-model downloads in CI. These add infrastructure
without improving the verified initial workflows. Do not interpret these decisions as
completing unconfigured GPU, semantic embedding, provider or production integrations.
