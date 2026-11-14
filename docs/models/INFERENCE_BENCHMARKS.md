# Inference benchmarks and evidence

The utilities run already-installed real models and never download weights. Automated adapter
checks use HTTP mocks. Reports include model identifier/digest, configured context/quantization,
actual Ollama metadata, client hardware, prompt character length/reported prompt tokens, output
limits/temperature, first nonempty text delta, completion latency, usage-based rate, error rate,
concurrency and cancellation. Missing usage stays null; no tokenizer estimates are substituted.

```sh
.venv/bin/python -m evaluation.local benchmark data/new-benchmark-c1.json \
  --base-url http://127.0.0.1:11434/v1 --requests 6 --concurrency 1 --max-tokens 96
.venv/bin/python -m evaluation.local benchmark data/new-benchmark-c2.json \
  --base-url http://127.0.0.1:11434/v1 --requests 6 --concurrency 2 --max-tokens 96
```

Output paths must be new. Run sequentially without evaluation/interactive load; repeated prompts
can benefit from caches. Native service uses one parallel generation, so concurrent HTTP requests
measure queueing, not two parallel GPU workers. Rates divide reported completion tokens by full
request time (including prompt/queue/transport); they are not isolated decoder throughput.
First delta is time to first visible text, not necessarily a one-token chunk. Warm/cold and run
configuration matter. Six requests are a development baseline, not production capacity.

Ollama /api/ps allocation is observable resident model/KV allocation, not peak process RSS or
complete unified-memory consumption. Unknown/remote hardware stays explicit. Cancellation records
client HTTP closure and follow-up latency; exact server compute cessation is not inferred solely
from those observations. API-level disconnect/recovery is separately checked by platform acceptance.
Measured reports and interpretation are appended after actual runs; no projected scores are used.

## Measured Apple Silicon baseline — 2026-10-09

Apple M3 MacBook Air, 24 GiB unified memory; native Ollama 0.40.2, model
qwen3:4b-instruct-2507-q4_K_M, context 8192, Q4_K_M. Exact digest and raw synthetic
records are stored in [baselines](baselines/qwen3-4b-benchmark-c1.json).
One generation worker; six requests per run; output bound 96 tokens, temperature 0.

| HTTP concurrency | Successful requests | Mean first text | Mean completion | Mean reported tokens / full request second |
| --- | --- | --- | --- | --- |
| 1 | 6/6 | 0.0717 s | 3.2292 s | 29.7600 |
| 2 | 6/6 | 2.8894 s | 6.1877 s | 16.4833 |

[Concurrency 2 records](baselines/qwen3-4b-benchmark-c2.json) show queueing with one
worker. Warm caches and small samples limit comparison. Cold direct first loading/request
was 3.0415 s for READY (16 prompt / 2 completion tokens). Ollama reported resident
allocation 3,800,291,082 bytes, about 3.54 GiB; peak unified-memory/RSS was not measured.
Client cancellation closed within 0.0007 s and subsequent requests succeeded; this does
not prove an exact time when GPU compute stopped. The authenticated web acceptance
closed after first delta at 0.3858 s, saved no partial assistant, and recovered generation.
No production stress, long-context boundary, NVIDIA or alternative-model benchmark is claimed.
