# Performance checks

scripts/benchmarks/http_load.py is a bounded HTTP health probe, not a model benchmark.
On 2026-10-09, 20 local requests with 4 workers returned 20 HTTP-200 responses; mean latency
was approximately 17.7 ms and observed p95 approximately 54.4 ms. These values include client
connection setup, came from a tiny sample on the development machine, and are not SLAs.

Model diagnostics can record actual generation latency/tokens when a configured server
provides usage. No GPU, inference-token throughput, VRAM, semantic embedding performance,
authenticated load/stress, multi-host or production capacity measurements exist yet.
Before release measure representative concurrency/context/document sizes and dependency
failure/recovery, documenting hardware, configuration, sample sizes and bottlenecks.

## Prepared frontend startup behavior

The initial sign-in page shows its branded main content during the session check, with
authentication controls disabled until that check completes. The browser gives session
bootstrap eight seconds, cancels it on timeout or unmount, and exposes connection retry
in place. Anonymous sessions, invitation restrictions and service failures retain their
distinct responses. This deadline is a recovery bound, not a hosted latency target.

Markdown and syntax highlighting load when message content is rendered; plain text
remains visible while that code loads. Ordinary chat is usable while the optional
document list loads. A document supplied in the URL must still be verified as accessible
before sending. Session, CSRF, ownership, inference and streaming contracts are unchanged.

`apps/chat/tests/startup.spec.ts` exercises these cases through synthetic browser network
fixtures in the normal `test:e2e` suite. Build the frontend before targeted local runs as
described in [Build and Test](../engineering/BUILD_AND_TEST.md). Prepared source and local
fixture results do not prove that these changes are live or establish production timings.

## Acceptance 005 workloads

`scripts/acceptance/load.py` is bounded to explicitly isolated https://localhost:3443, verifies
the local CA, uses only random synthetic accounts/documents and reports measured operations,
HTTP errors, failed users, raw latency samples, nearest-rank p50/p95, first text, actual reported
token rates and sampled container resources. Application capacity requires the labelled mock
and exercises sessions, SSE/history, uploads/search, explicit granted tools and persisted travel.
`--workload inference` measures real chat separately at controlled concurrency; it must be paired
with backend/model metadata and actual model readiness. These small tests are not a stress/soak
or target-server capacity guarantee. Product SLO owners have not approved numeric requirements;
the provisional mock smoke thresholds (2 seconds p95/first text and 1% failed users) are proposed
qualification criteria, not a customer SLA. See the acceptance report and sanitized raw results.
