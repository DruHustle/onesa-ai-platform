# Local inference configurations

| Backend | Purpose | Endpoint | Verification |
| --- | --- | --- | --- |
| mock | CPU tests / development | No model server | Deterministic labelled regression tests |
| ollama | Native Apple Silicon development | Host loopback /v1; containers use host.docker.internal | Real Qwen3 generation verified |
| vllm | NVIDIA/Linux serving | Configured private OpenAI-compatible /v1 | CPU HTTP contracts pass; target GPU execution pending |
| llamacpp | Separate CPU model server on ARM64 | Authenticated private OpenAI-compatible /v1 | Transport tests cover the integration. VM qualification is pending. |

Set ONESA_MODEL_BACKEND, ONESA_MODEL_NAME and ONESA_MODEL_BASE_URL; retain public alias default.
Context, output tokens, temperature, quantization/revision provenance and timeout are explicit.
The frontend discovers backend/model through authenticated /models; no host/model routing is
hardcoded there. Changing backend does not modify schema, conversations or authentication.

Current local .env selects qwen3:4b-instruct-2507-q4_K_M, Ollama /v1, Q4_K_M and 8192 context.
Existing API, database and port 3100 are preserved. Ordinary make up uses that configuration;
compose.ollama.yaml is an explicit development override for a separately configured environment.
For mock tests set ONESA_MODEL_BACKEND=mock and use an isolated Compose project/database; never
truncate application data. Actual browser tests are opt-in via ONESA_REAL_INFERENCE=1.

See OLLAMA_SETUP.md for native runtime/networking and VLLM_DEPLOYMENT.md for future Linux serving.
The [llama.cpp model manifest](llamacpp-model.json) pins the server candidate and the existing Qwen3 quantization. The release templates use its alias with an 8192-token context and one generation at a time. Measure generation latency, peak memory and resource contention against Identity and PasoFi before promoting the runtime. Keep the model server and its weights outside the application repository and use a protected HTTPS endpoint for production.
The runtime registry snapshots in benchmark/evaluation reports retain identifier/digest,
quantization/backend/capabilities/context and measured outputs. onesa-ai-platform-backend/evaluation/model_inventory.json
lists proposed comparison candidates; it is not proof those candidates are installed or superior.
