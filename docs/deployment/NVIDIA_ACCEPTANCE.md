# NVIDIA/vLLM host acceptance — pending actual hardware

The tested Apple M3 host has no NVIDIA driver/device. `gpu_preflight.py` records BLOCKED;
no NVIDIA inference, GPU throughput, CUDA training or quality result has been produced.
The existing pinned vLLM profile remains optional and outside ordinary CPU development.

Prepare a supported Linux NVIDIA host with reviewed driver/runtime compatibility, NVIDIA
Container Toolkit, adequate actual free VRAM/RAM/disk and approved access. The existing
model/context/tensor-parallel configuration is a candidate, not a capacity guarantee.
Install/load an approved model only with the corresponding authorization; this continuation
does not download or launch one. Protect its API key and keep port 8000 private.

After an operator starts the private GPU container, collect real prerequisites:

```sh
.venv/bin/python scripts/acceptance/gpu_preflight.py \
  --container <existing-inference-container> --output data/nvidia-preflight.json
```

This collects driver, model name, total/used/free VRAM from the host and inside the selected
container. A PASS means those prerequisites only. Save immutable image/model revision,
context limit, GPU count/tensor parallelism, runtime/driver versions and instance resources.

On that same host, use isolated TLS staging plus the existing `compose.gpu.yaml` profile with
separate test secrets/model key and approved model artifacts. Preserve main volumes. Verify
`/ready`, authenticated `/models` reports backend `vllm` and the expected model/context;
verify missing/wrong inference keys are rejected from inside the private network. Validate
actual model loading/context using vLLM logs and API output without disclosing its key.

Run the real browser acceptance (`tests/real.spec.ts`) with local TLS and explicit real
inference enabled: generation, incremental text, remembered codename, persisted history,
Stop and successful retry. Run `scripts/acceptance/load.py --workload inference` at 1, 2,
then qualified higher concurrency; the runner is bounded to isolated localhost:3443 and
never substitutes mock inference. Measure TTFT, full response latency, request errors and
reported token rates; pair with repeated `nvidia-smi`/container stats. Run the existing
`evaluation/local.py evaluate` against approved synthetic cases from a private network
location, then retain scored quality baselines and inspect failures. Never publish keys or
raw private user responses in evaluation evidence.

Exercise browser disconnect and verify no partial assistant persistence. In the isolated
API only, temporarily point the model URL at a closed private port, observe readiness 503,
sanitized SSE error and delivered dependency alert. Restore the original endpoint and verify
actual generation and resolved alert. Do not stop a shared inference service for fault testing.
Record OOM/error recovery, concurrency limits and memory behavior before setting performance
requirements. Use target-host backup/rollback tests independently of model qualification.

| GPU acceptance requirement | Current result |
| --- | --- |
| Actual NVIDIA driver/VRAM and container access | BLOCKED: no compatible host |
| Model load/context/private authentication | NOT TESTED |
| Real generation/SSE/cancel/context/disconnect/recovery | NOT TESTED |
| Concurrent model capacity, GPU utilization and quality baseline | NOT TESTED |

Hardware PASS, real inference PASS and reviewed product quality/performance targets are
separate gates. Mac or mock results cannot satisfy any NVIDIA execution requirement.
