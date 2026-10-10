# Milestone 2 — real Apple Silicon inference

Completed 2026-10-09 in the existing `onesa-ai-platform` repository. The explicit
Apple Silicon request revised M2 acceptance to native Ollama. The platform now uses
real Qwen3 behind the existing authenticated API, applications and public model alias.
[NVIDIA/vLLM qualification](../models/VLLM_DEPLOYMENT.md) remains a separate unverified
deployment target. The next ordered task is M3.2: qualify real semantic embeddings.

## Runtime and preserved contracts

Hardware checked before download: Apple M3 MacBook Air, 24 GiB unified memory,
macOS 27.0.1 arm64, approximately 488 GB available disk. Installed native Ollama
0.40.2 from its official release archive after SHA-256 verification. Only
`qwen3:4b-instruct-2507-q4_K_M` was downloaded; digest:
`0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0`.
Runtime/model files are ignored under data/. No system-wide installation, second
Ollama daemon, Docker Ollama, CUDA installation or training was performed.

Managed daemon binds 127.0.0.1:11434, cloud disabled, context 8192, one loaded model
and one generation worker. Container access via host.docker.internal was verified
without exposing inference externally. Main UI remains **http://localhost:3100**.
Existing database, authentication, conversation/history, RAG, agent and travel contracts
remain working. Safe model/usage/timing metadata is additive; no schema migration.

Shared OpenAI-compatible client implements mock/Ollama/vLLM with configurable controls,
strict SSE termination, sanitized availability/timeout/malformed errors and no silent
fallback. Usage is request-owned; missing token counts stay null. Actual tokens persist
in existing run columns and completed assistant metadata. Protected generation metrics
use bounded labels. Frontend discovers backend/model generically and labels mock clearly.

## Actual verification

- Direct native completion: READY, actual usage 16 input / 2 output tokens, cold
  first-load/request 3.0415 s. /api/ps reported context 8192 and resident allocation
  3,800,291,082 bytes (~3.54 GiB), not peak RSS or full unified-memory usage.
- Authenticated API: real multi-turn codename recall, four persisted messages, grounded
  answer with owned saved source, model-planned text_stats run, ungranted-tool denial,
  valid structured Berlin itinerary, first-delta disconnect without a saved assistant,
  next-generation success, liveness/readiness distinction while Ollama stopped, and
  recovery of the same authenticated context after restarting the managed daemon.
- Chromium real test: actual model badge, context/history reload, visible partial text
  while Stop remained available, cancellation, absence of a completed partial assistant
  after reload and next-generation recovery. Screenshot: ignored
  data/screenshots/chat-real-local.png.
- Four original Chromium mock tests passed on isolated port 3101: chat CRUD/auth,
  documents/sources/tools/travel, mobile keyboard/drawer and locale preference.
- `make integration`: **62 passed** against isolated real PostgreSQL.
  `make check`: **41 passed, 21 skipped**, Ruff/format and strict mypy passed.
  Frontend lint/types/production build, main Docker build/startup, OpenAPI export,
  dependency consistency, all five Compose variants and relative documentation links passed.
  One upstream Starlette HTTPX TestClient deprecation warning remains.
- HTTP simulation tests cover missing model, timeout/unavailable/malformed streams,
  bounded parsing, usage isolation, cancellation/closure and recovery. These tests
  establish adapter contracts; they are distinguished from actual model evidence.

Initial web cancellation acceptance failed: compression buffered deltas until generation
completed and therefore saved a complete answer before disconnect. Disabling Next.js
compression fixed actual streaming. Repeated full API and browser acceptance passed.
Two initial browser test runs used ambiguous selectors; corrected selectors passed.
The browser screenshot also captured an unnecessary refusal on the initial fictional
codename acknowledgment, followed by correct codename recall. This is a qualitative
instruction-following limitation outside the mechanical suite and needs human review.
No observed failures or unverified integrations are hidden by the final counts.

## Evaluation and benchmark results

Stored synthetic records are in [baselines](../models/baselines/qwen3-4b-baseline.json),
with the [authenticated acceptance](../models/baselines/onesa-real-acceptance.json).
The author-curated 13-case suite covers general use, arithmetic, English, German,
French, structured JSON/tool planning, source-grounded and unknown answers, privacy
refusal, injection resistance and context. **12/13 mechanical checks passed**. The
arithmetic answer included correct 10 with explanatory text, failing exact-only output.
One native function-call schema probe passed; it executed no tool. Human review remains
required. These small probes do not establish broad multilingual, reasoning or safety
quality, instruction-following guarantees, certifications or deployment suitability.

| Requests / HTTP concurrency | Mean first text | Mean completion | Mean reported output tokens / full request second | Errors |
| --- | --- | --- | --- | --- |
| 6 / 1 | 0.0717 s | 3.2292 s | 29.7600 | 0/6 |
| 6 / 2 | 2.8894 s | 6.1877 s | 16.4833 | 0/6 |

Temperature 0, output bound 96, warm runs, one worker; concurrency 2 measures queueing.
Rates include request/prompt/queue time and are not isolated decode throughput. First
text may contain multiple tokens. Native client cancellation closed under 0.0007 s;
web acceptance closed at 0.3858 s, with no successful partial assistant saved. Exact
GPU compute-stop timing, peak memory, long-context limits and production stress were
not measured. See [benchmark interpretation](../models/INFERENCE_BENCHMARKS.md).

Qwen3.5 4B/9B quantized tags are optional metadata/commands only. No download, benchmark
or superiority claim exists for them. Vision/speech are future Onesa adapters; upstream
capability metadata is not implemented application functionality. Retrieval remains a
lexical baseline despite the real generation backend. No embedding-service quality,
live travel provider, trained Onesa weights or NVIDIA results are claimed.

## Changes and continuation

Updated shared inference/configuration/chat/observability, generic frontend metadata,
Next.js compression, Compose local/GPU context settings, native service management,
evaluation inventory/suite/benchmarks/platform acceptance and adapter/integration/browser
tests. Setup, serving, contracts, architecture, roadmap, status, handoff and changelog
reflect real state. Native runtime and main Compose app remain running; scratch test
and mock-regression containers are stopped with data preserved. No remote publishing,
project license choice or regulatory/funding claims were made.

For reproduction use [native setup](../models/OLLAMA_SETUP.md),
[evaluation](../models/MODEL_EVALUATION.md) and
[Roadmap](../product/ROADMAP.md). Continue the first unchecked status task, preserving
working components and recording real qualification evidence.
