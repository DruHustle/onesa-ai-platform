# Semantic retrieval local qualification

Date: 2026-10-10, Europe/Berlin. Scope: the owner approved local qualification of
Qwen3-Embedding-0.6B after the recommendation. No paid hosting, remote publication,
training, comparison-model download or production data reindexing was performed.

The approved candidate weights were downloaded from the official publisher and
SHA-256 verified. Revision: `97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3`;
weight hash: `0437e45c94563b09e13cb7a64478fc406947a93cb34a7e05870fc8dcd48e23fd`.
The publisher lists Apache-2.0 licensing and configurable 32–1024 output dimensions.
This does not assign a license to Onesa's own product. [Official model card](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B).

## Fixed evaluation and decision

The versioned, author-created fixture contains 24 synthetic passages and 48 EN/DE
questions, including cross-language retrieval and hard negatives. These texts are
not corporate policies or verified company facts. Thresholds were declared before
inference: top-1 >=85%, recall@3 >=95%, each language top-1 >=80%, and a 256-dimensional
top-1 drop <=5 percentage points compared with 1024. No examples were removed or
thresholds changed after seeing results.

| Candidate | Top-1 | Recall@3 | EN top-1 | DE top-1 |
|---|---:|---:|---:|---:|
| Lexical 256 | 25.00% | 35.42% | See raw report | See raw report |
| Qwen 256 | 93.75% (45/48) | 97.92% (47/48) | 95.83% | 91.67% |
| Qwen 1024 | 97.92% (47/48) | 97.92% (47/48) | 95.83% | 100.00% |

**Retain 256 dimensions as the locally qualified first candidate**, preserving the
existing pgvector schema. The 4.17-point top-1 tradeoff against 1024 is real; retaining
256 is a compatibility/storage decision within the preset threshold, not a claim
that dimensions have no effect. No database migration occurred.

Failed top-1 cases at 256: remote-access-en (rank 4), remote-access-de and
software-licenses-de. At 1024, remote-access-en still ranks below the top three.
These security/license questions remain limitations requiring human source review.
A retrieval match does not verify policy truth or authorize a sensitive action.

Median loopback batch latency (8 inputs, mixed document/query lengths) was 0.235 s
at 256 and 0.202 s at 1024. This one short sequential run is not a throughput, capacity
or production SLA measurement; dimensional latency ordering is not statistically
established. The runtime used Apple M3 MPS, float32, max 2048 tokens and normalized
outputs. Raw rankings/timings, fixture hash and provenance are preserved in
[the machine-readable baseline](../models/baselines/semantic-retrieval-20261010.json).

## Application and security acceptance

The independent loopback service validates the pinned weight hash at startup, loads
local files only with remote code disabled, requires bearer authentication, bounds
bodies/batches/characters/tokens, refuses truncation and returns 429 for overlap.
Responses are no-store; sanitized errors do not echo input or raw encoder failures.
The optional service dependencies do not enter the core API image/lockfile.

The core HTTP client explicitly requests 256 dimensions and applies Qwen's retrieval
instruction only to queries. No document prompt is added. Production HTTP embeddings
require authenticated HTTPS, excluding development/loopback endpoints. Model/protocol
revision is versioned with document vectors; incompatible versions are excluded rather
than mixed or silently replaced with lexical retrieval.

Core regression: 116 backend tests passed, four optional/platform skips; Ruff/format
and strict mypy passed. The three opt-in real-model tests passed separately.

Three real PostgreSQL/model tests passed: cross-language owned retrieval and isolation/
deletion; lexical-to-semantic reindex plus preservation of old vectors on upstream
failure; and an actual existing native Qwen chat answer grounded in semantic sources
with the completed answer/source identifiers persisted. All records were synthetic in
a disposable database, separate from the existing application/user databases. The live
service's authentication, private response headers and actual 256-vector output passed
again after restart. Chromium and WebKit each passed the actual semantic upload/search/native streaming
and reopened-conversation/source-persistence workflow (two passes). The test was
corrected to explicitly reopen the saved conversation after reload, matching the
existing UI; the initial test assumed auto-selection and failed. Genuine synthetic
screenshots are stored under ignored data/embeddings/browser. Frontend lint/types pass.
The original local app, its .env and existing documents were not changed. Packaging-tool advisories found in the new environment were remediated;
the final separate-runtime dependency audit reported zero known findings.

Evidence: ignored `data/embeddings/` contains download/install/audit/raw retrieval
records; `data/audit-20261009/evidence/embeddings-*` contains reproducible command logs.
The exact tested 50-package macOS graph is hash-locked from official PyPI release
metadata. An ignore-installed pip dry-run verified all pinned dependencies/hashes
without altering the tested environment. Initial pip-tools hashing timed out on
package downloads; the installed-graph metadata generator avoids untested re-resolution.

The optional service has a separate macOS hash lock and [run instructions](../../onesa-ai-platform-backend/embedding_service/README.md).

## Remaining acceptance

This completes local M3.2 software/owned-document qualification on the stated synthetic
EN/DE scope. It does not qualify production hosting, all advertised languages, customer
corpora, large documents, sustained load or all security properties. Test an approved
private EU target with TLS, resource/queue limits, monitored failures, secret rotation,
retention and controlled owner-approved reindex/rollback before switching live data.
Linux/CPU/GPU service execution needs separate dependency/image/performance acceptance.

The active local/private configuration remains lexical and existing document vectors
are preserved. The optional Qwen profile is ready for a deliberate controlled switch.
Overall cross-project production release remains NO-GO for other recorded blockers.
