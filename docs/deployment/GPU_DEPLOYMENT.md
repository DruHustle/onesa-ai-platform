# GPU deployment — configuration ready, execution pending

Requires a verified Linux/NVIDIA host, compatible driver/container toolkit, and measured
VRAM capacity. Run `nvidia-smi`, `python scripts/diagnostics/check_gpu.py` in the intended
GPU environment, and verify container GPU access before requesting model downloads.
The Mac has no NVIDIA/CUDA tooling. Native Apple M3/Ollama generation is now verified;
that evidence does not establish NVIDIA/vLLM execution. See models/VLLM_DEPLOYMENT.md.

After capacity/license/revision review, configure model name, private API key, context,
gpu-memory utilization and tensor-parallel size in .env. Defaults use an official immutable
Qwen revision, 4096 context, 0.85 utilization and one tensor-parallel worker; they are
starting settings, not hardware feasibility claims. No quantization mode is enabled blindly.

```sh
docker compose -f compose.yaml -f compose.gpu.yaml --profile gpu up --build -d
```

This explicit operator command may download/cache weights. Inference remains private.
A separate GPU host can be addressed through ONESA_MODEL_BASE_URL on a private network.
Run `scripts/diagnostics/check_model.py` with model/backend/URL exported against an already
running server; it checks discovery and records actual latency/tokens when usage is provided.

For an evaluated local LoRA adapter, mount ONESA_MODEL_ARTIFACT_DIR and apply
compose.gpu.lora.yaml after compose.gpu.yaml. Set adapter directory/name/rank and the
immutable base revision. The API selects the adapter alias without frontend changes.
The LoRA profile is configuration-validated; loading/quality/rollback still need hardware tests.
See MODEL_SELECTION.md and UPSTREAM_REVISION.md for official evidence and remaining checks.
