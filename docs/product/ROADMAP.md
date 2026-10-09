# Roadmap and milestone evidence

| Milestone | Delivered | Remaining evidence |
| --- | --- | --- |
| 0 Discovery/design | Continuation workflow, PRD/architecture/contracts, build/test baseline | No invented architecture sign-off |
| 1 Chat MVP | PostgreSQL/auth/persistence/Next.js/SSE/Compose and real browser flow | Broader UX/security review |
| 2 Local model | Shared Ollama/vLLM client, real Apple M3/Qwen3 serving, evaluation/benchmarks; pinned GPU/LoRA config | Actual compatible NVIDIA host loading/generation/memory/throughput |
| 3 Knowledge | TXT/PDF, versioned pgvector, lexical baseline/HTTP embedding adapter, sources/reindex/ownership | Real semantic embedding endpoint and hostile-file isolation |
| 4 Agent runtime | Shared-model planner interface, registered local tools, grants/limits/cancellation/history | Any future effectful tools require separate reviewed integrations |
| 5 Travel MVP | Typed saved/revisable mock/model itinerary planner and UI | Live maps/weather/flight/accommodation providers and their credentials |
| 6 Fine-tuning framework | Provenance/validation/splits/checksums/config dry-run, optional LoRA/QLoRA/evaluation/registry | Approved language datasets, CUDA runtime lock, actual training/baseline/release review |
| 7 Release controls | CI/audits/body bounds/logs/metrics/non-root/TLS template/restore/health probe | Actual TLS/host qualification, model load/stress, independent security, retention/alerts |

Milestone 2 acceptance now targets native Apple Silicon per the explicit request; NVIDIA
execution remains a separate unverified deployment qualification. Independent M3–M6 software
was implemented/tested without GPU dependency; no real-model or production acceptance is
inferred from mock passes. Phase B preserves public alias/API/UI while changing evaluated
weights/adapters. See IMPLEMENTATION_STATUS.md for exact tests and next actions.

Amendment 001 aligns every existing milestone with European-based general-purpose and
international positioning, preserving the order above. Phase B covers general/enterprise/
industrial/travel/multilingual and optional regional adaptations. Profile metadata is delivered;
actual specialized models, multimodal capabilities and enterprise integrations remain proposed.
No branding or specialization work delays the already working Chat MVP or M2 inference acceptance.
