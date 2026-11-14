# Local model serving

Fresh configuration defaults to labelled mock and needs no model weights. This workspace
uses real native Ollama/Qwen3 4B Q4_K_M, context 8192. Configure backend mock/ollama/vllm,
model identifier, private base URL/key and generation controls. The shared client rejects
unavailable/malformed/truncated output and never falls back silently. Public alias default
is stable; authenticated metadata includes safe backend/identifier/context/quantization/revision
and text modality. Discovery checks the actual configured model's presence.

[Native setup](OLLAMA_SETUP.md) keeps inference on loopback and verifies Docker host access.
[Local configurations](LOCAL_INFERENCE.md) preserve the same database/API/applications.
[Evaluation](MODEL_EVALUATION.md) and [benchmarks](INFERENCE_BENCHMARKS.md) link stored actual
synthetic reports and limits. CPU HTTP tests establish contract behavior separately.

compose.gpu.yaml pins the optional official vLLM image/base revision, publishes no inference
port and supports context/memory/tensor-parallel controls. GPU API context matches the
server's 4096-token default. Prepare a separate private NVIDIA configuration with the correct
Hugging Face identifier/revision, endpoint and unquantized/qualified quantization metadata;
do not reuse the active Mac Ollama environment. LoRA selects a separately reviewed adapter.
[NVIDIA guide](VLLM_DEPLOYMENT.md) contains operator steps, not executed GPU qualification.
