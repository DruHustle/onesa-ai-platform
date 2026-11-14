# Private Qwen embedding service

Optional model serving lives separately from the core FastAPI application/runtime.
The API consumes an authenticated OpenAI-style `/v1/embeddings` endpoint. This
implementation is locally qualified on Apple Silicon, not deployed or qualified
for Linux/Render production. Do not put model weights in Git or the API image.

The fixed candidate is `Qwen/Qwen3-Embedding-0.6B`, Apache-2.0, revision
`97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3`. The service checks the weight SHA-256
`0437e45c94563b09e13cb7a64478fc406947a93cb34a7e05870fc8dcd48e23fd` before loading.
Loading is local-only with `trust_remote_code=False`; no automatic model download
occurs at service startup. Dependencies remain outside core API requirements.

## Local build and serving

From repository root, create a separate Python 3.11 virtual environment. The supplied
lock is specific to the qualified macOS environment; resolve and audit a separate
platform lock before any Linux deployment. Installation requires package downloads.
The owner approved this specific model's local qualification on 2026-10-10.

```sh
python3.11 -m venv data/runtime/embedding-env
# Install the exact tested graph, including remediated packaging tools:
data/runtime/embedding-env/bin/python -m pip install --require-hashes -r onesa-ai-platform-backend/embedding_service/requirements-macos.lock
```

Download only the pinned revision from the [official model repository](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B).
Store it at `data/models/qwen3-embedding-0.6b/<revision>` and verify the publisher
checksum. The local qualification's download manifest is ignored at
`data/embeddings/download.json`. Preserve existing models and user data.

Set `ONESA_EMBEDDING_API_KEY` privately (at least 32 characters). From backend root:

```sh
../data/runtime/embedding-env/bin/python -m embedding_service.server \
  --model-directory ../data/models/qwen3-embedding-0.6b/97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3 \
  --device mps --port 8364
```

Use `--device cpu` only after independent performance qualification; the acceptance
record is MPS. The service binds `127.0.0.1` and does not expose its API publicly.
`/health` reports startup readiness after loading. Embedding requests require bearer
authentication; body size is bounded at 64 KiB, batches at 16 texts/32,768 characters,
and each text at 8,192 characters/2,048 tokens. Overlong inputs fail rather than truncate.
Only one inference executes at once; overlapping calls get 429 instead of unbounded
queueing. Responses are non-cacheable and errors exclude documents/raw exceptions.

To regenerate the lock after a separately reviewed/qualified dependency update, run
`../data/runtime/embedding-env/bin/python -m embedding_service.lock_installed` from
backend root. It locks the installed macOS dependency graph using official PyPI
release hashes. The initial pip-tools hash-generation attempt timed out on package
artifact downloads; this generator fetches metadata and preserves tested versions.

## API integration and controlled reindex

Use `backend.env.example` as a candidate profile; never replace existing private
configuration blindly. The core requests **256 dimensions**. For this Qwen profile,
search queries receive `Instruct: ...\nQuery:...`; document passages do not receive
that prefix. Pin the revision and protocol identifier together. Other HTTP providers
can retain an empty query instruction. HTTPS plus a bearer key are mandatory for
production HTTP embeddings; server-side TLS/ingress remains a target-host task.

The active configuration remains lexical until deliberately switched. Existing
lexical documents will be excluded by the candidate version filter until reindexed;
there is no silent cross-model fallback. Reindex per approved owner/document, review
results and retain a backup/rollback plan. A failed embedding request leaves old
vectors intact. Successful reindex replaces that document's old vector rows, so
returning to an older model requires reindexing again. No user documents were
reindexed during qualification; only disposable synthetic records were used.

## Verification

From backend root, with the existing backend test environment and local service:

```sh
PYTHONPATH=. ../.venv/bin/python -m evaluation.qualify_embeddings \
  --key-file ../data/embeddings/service-key \
  --output ../data/embeddings/retrieval.json
```

The fixed synthetic fixture is `evaluation/semantic-retrieval.v1.json`. Its thresholds
are declared before inference. Compare lexical, normalized Qwen 256 and Qwen 1024.
The three opt-in PostgreSQL tests require an isolated `ONESA_TEST_DATABASE_URL` ending
`_test`, `ONESA_SEMANTIC_TEST_ENDPOINT=http://127.0.0.1:8364/v1` and
`ONESA_SEMANTIC_TEST_KEY_FILE` pointing to the private key file. Set
`ONESA_REAL_INFERENCE=1` only to exercise the already authorized native Qwen chat
model; this test does not install any chat weights. Run `tests/test_semantic_integration.py`.

See [qualification report](../../docs/development/SEMANTIC_RETRIEVAL_QUALIFICATION.md).
Synthetic EN/DE acceptance does not establish quality across all advertised languages,
customer domains, long documents or production capacity. EU hosting, private network/TLS,
resource sizing, secrets rotation, monitoring and real target-host tests remain required.
