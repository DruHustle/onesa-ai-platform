# Model selection baseline

Foundation: `Qwen/Qwen3-4B-Instruct-2507`; configurable through ONESA_MODEL_NAME.
This workspace runs its Ollama `qwen3:4b-instruct-2507-q4_K_M` distribution natively
on Apple M3 with context 8192. The mock loads no weights; NVIDIA/vLLM execution remains
pending. See [actual baseline](MODEL_EVALUATION.md) and [native setup](OLLAMA_SETUP.md).

The official [model card](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507)
identifies Apache-2.0 licensing, a 4B text model, and vLLM serving support. This is
upstream evidence, not proof of successful execution in this repository. Review
license obligations, exact revision, hardware and serving compatibility for each deployment.
Model licensing does not settle this project's own software license.

Use the official [vLLM GPU installation guide](https://docs.vllm.ai/en/stable/getting_started/installation/gpu/)
for the selected serving release's platform/CUDA/PyTorch requirements. A pinned optional
image/release is preserved in compose.gpu.yaml. Choose context length and quantization only after diagnostics
and memory measurements on the target Linux/NVIDIA host. Parameter count alone
does not establish VRAM feasibility; account for weights, KV cache, batching, and
runtime overhead. Do not request the full advertised context blindly.

Evaluation priorities: useful conversation/code outputs, general assistant reasoning and relevant European/international languages,
enterprise/industrial/travel accuracy, permitted usage, latency/memory, and a reproducible baseline.
Optional regional/African language adaptation follows baseline qualification.
Phase B provides multi-domain adaptation with independently versioned adapters/releases
and general-assistant regression evaluation. It replaces only evaluated artifacts/configuration behind the stable model
client. Only the explicitly requested native Qwen3 4B model was downloaded; no training
was performed. Qwen3.5 comparisons remain optional uninstalled inventory entries.
