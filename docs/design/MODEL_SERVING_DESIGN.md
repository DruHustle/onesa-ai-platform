# Model serving design

The shared ModelClient protocol retains async health and text streaming. Mock is explicitly
labelled. OllamaModelClient and VLLMModelClient reuse OpenAIModelClient for configured /v1
model discovery, typed turns, generation controls, usage-enabled SSE and mandatory [DONE].
HTTP cancellation closes upstream resources; malformed/truncated streams fail. Total API
deadlines and transport timeouts are bounded; failures never fall back to mock.

Request-owned context records reported usage without changing planner/test-client interfaces.
Successful messages save model/metrics provenance in existing JSONB and populate nullable run
token fields. Public alias default is stable; safe configured model identifier, backend,
context, modalities and quantization/revision provenance are now explicit. URLs/keys/absolute
artifact paths remain private. All input schemas remain text-only.

Apple Silicon uses native loopback Ollama with Docker Desktop host.docker.internal. The
Mac default context is configured at 8192 and observed through native metadata; /v1 cannot
change it per request. vLLM remains a private Linux/NVIDIA option with operator-set context.
Character/history caps are not tokenizer-exact accounting. Real Mac generation is measured;
NVIDIA execution and expanded multilingual/safety/quality assessment remain pending.

See architecture/MODEL_SERVING.md, models/OLLAMA_SETUP.md and INFERENCE_BENCHMARKS.md.
