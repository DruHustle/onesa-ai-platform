# Private NVIDIA/Linux deployment — execution unverified

The same OpenAIModelClient underlies vLLM and Ollama. On an intended Ubuntu/NVIDIA host,
record OS/GPU/driver/VRAM with nvidia-smi and scripts/diagnostics/check_gpu.py. Review
[vLLM GPU requirements](https://docs.vllm.ai/en/stable/getting_started/installation/gpu/)
for the pinned release's driver/CUDA/hardware compatibility; no CUDA/driver is installed on Mac.

Install a distribution-appropriate NVIDIA driver and the NVIDIA Container Toolkit using
[NVIDIA's installation guide](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html).
Configure Docker with nvidia-ctk runtime configure --runtime=docker and restart the daemon on
that host, accounting for other workloads. Verify GPU access inside a compatible pinned CUDA
container before downloading model weights. These host changes were not performed here.

Prepare private .env on that host: ONESA_MODEL_BACKEND=vllm, ONESA_MODEL_NAME=Qwen/Qwen3-4B-Instruct-2507,
ONESA_MODEL_BASE_URL=http://inference:8000/v1, a private API key, immutable upstream revision,
ONESA_MODEL_CONTEXT_LENGTH=4096 initially (increase after memory measurement), utilization 0.85
and tensor parallel size 1. Do not reuse Ollama's model tag/digest as a Hugging Face revision.
compose.gpu.yaml pins the vLLM image and has private inference networking with no published port.

```sh
docker compose -f compose.yaml -f compose.gpu.yaml --profile gpu config --quiet
docker compose -f compose.yaml -f compose.gpu.yaml --profile gpu up --build -d
docker compose -f compose.yaml -f compose.gpu.yaml --profile gpu logs inference
nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv
```

The explicit startup command may download the reviewed pinned base into model-cache. Prestage
artifacts for an offline deployment; never silently pull an unreviewed revision. Use readiness,
configured model discovery and real generation probes, then evaluation/benchmark utilities
against the private endpoint. A separate GPU host requires approved private routing/TLS access.

```sh
docker compose -f compose.yaml -f compose.gpu.yaml --profile gpu stop
```

Preserve volumes during routine shutdown/restart. LoRA override selects a separately reviewed
adapter without app/schema changes. Resource sizing, context, throughput, cancellation, actual
GPU loading, model quality and rollback still require target-host execution evidence.
