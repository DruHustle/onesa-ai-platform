# ONESA AI PLATFORM — MILESTONE 2
## Real Local AI Inference and Model Evaluation

**Repository:** `onesa-ai-platform`  
**Current status:** Application framework implemented and running with mock inference.  
**Objective:** Enable real local model inference without changing the existing application architecture.

You are continuing development of the existing Onesa AI Platform.

Do not recreate the repository, rebuild working modules unnecessarily, or change the European-based, general-purpose platform positioning.

### Task 1 — Review the existing implementation

First inspect:

- Current model client and inference adapters
- API and streaming implementation
- Model registry and configuration
- Docker Compose infrastructure
- Existing tests
- `docs/development/IMPLEMENTATION_STATUS.md`
- `docs/development/SESSION_HANDOFF.md`
- Milestone 2 acceptance criteria

Determine what already works and what remains unimplemented.

Run relevant existing tests and record the baseline.

### Task 2 — Implement local Mac inference

Add an Ollama inference adapter to the existing model abstraction.

Our preferred development model is:

`qwen3:4b-instruct-2507-q4_K_M`

Use the exact available model identifier and check local hardware compatibility before downloading large model weights.

Support the following inference configurations:

- `mock` — tests and CPU-only development
- `ollama` — real local inference on macOS
- `vllm` — real inference on a compatible NVIDIA/Linux host

The backend must be selectable through environment configuration.

Do not hardcode Ollama, NVIDIA, Qwen, or host addresses into frontend components or core business logic.

For Docker Desktop on macOS, correctly handle communication between containerized Onesa services and a host-based Ollama server, including `host.docker.internal` where appropriate.

Do not expose the Ollama service to the public network.

### Task 3 — Complete real inference integration

Connect the real model to the existing Onesa Chat application.

Implement and verify:

1. Text message to actual model inference.
2. Correct streaming response handling.
3. Multi-turn conversation context.
4. Session-aware chat history.
5. Model identifier reporting.
6. Inference timeout handling.
7. Cancellation of active generation.
8. Recovery from inference-server failure.
9. Model-not-loaded handling.
10. Token usage and latency metrics where supported.
11. Model readiness and health checking.
12. Proper error reporting without exposing internal infrastructure.

Preserve existing authentication and conversation ownership rules.

The frontend must show the actual selected inference backend and distinguish mock from real inference.

### Task 4 — Maintain vLLM compatibility

Retain and improve the existing vLLM adapter.

Use the configured OpenAI-compatible inference endpoint.

Prepare reproducible NVIDIA/Linux instructions for:

- NVIDIA driver verification
- NVIDIA Container Toolkit
- Model downloads
- Model loading
- Private inference networking
- Context length configuration
- GPU memory configuration
- Startup and shutdown
- Health checks
- GPU resource monitoring

Do not claim NVIDIA inference has been validated unless it has actually been tested on compatible hardware.

### Task 5 — Build model evaluation infrastructure

Create a reproducible evaluation suite.

Evaluate:

- General conversational quality
- Reasoning
- Instruction following
- English and German performance
- Multilingual capability
- Multi-turn consistency
- RAG grounding and citations
- Structured JSON outputs
- Tool-calling capability
- Hallucination and unsupported claims
- Safety and prompt-injection resistance
- Streaming performance
- Latency and tokens per second

Include additional regional-language evaluation datasets when suitable validated data becomes available.

Maintain evaluation independence from training data.

Store baseline results so future Onesa fine-tuned models can be compared with the original foundation model.

Do not fabricate evaluation scores or report untested model capabilities as verified.

### Task 6 — Inference benchmarking

Create a benchmark utility that can measure:

- Time to first token
- Total generation time
- Output tokens per second
- End-to-end chat response time
- Concurrent request handling
- Cancellation effectiveness
- Memory usage where observable
- Error rate

Record the model version, inference backend, hardware, quantization, prompt length, and test configuration.

Run actual benchmarks on available hardware.

Separate measured results from projected performance.

### Task 7 — Security and regression testing

Ensure:

- The inference server is private.
- User sessions remain isolated.
- Knowledge retrieval respects permissions.
- Model responses cannot bypass registered tool permissions.
- Failed streaming does not corrupt saved conversations.
- Errors do not leak secrets or private network addresses.

Preserve all existing backend and browser tests.

Add tests for the Ollama adapter and cross-backend compatibility.

Run linting, typing, builds, unit tests, integration tests, and supported browser tests.

### Task 8 — Update the technical documentation

Update or create:

- `docs/models/LOCAL_INFERENCE.md`
- `docs/models/OLLAMA_SETUP.md`
- `docs/models/VLLM_DEPLOYMENT.md`
- `docs/models/MODEL_EVALUATION.md`
- `docs/models/INFERENCE_BENCHMARKS.md`
- `docs/architecture/MODEL_SERVING.md`
- `docs/deployment/GPU_DEPLOYMENT.md`

Also update the implementation status, roadmap, change log, and session handoff documents.

Documentation must accurately reflect the actual implementation and distinguish verified and unverified capabilities.

### Acceptance criteria

Milestone 2 is completed when:

1. Onesa Chat can communicate with a real locally hosted model.
2. Chat responses are genuinely generated by the model.
3. Streaming works correctly.
4. Conversation context is preserved.
5. Database persistence remains functional.
6. Model selection is configuration-driven.
7. Mock inference continues to work.
8. Automated tests pass.
9. Model evaluation and benchmarking tools produce real reports.
10. The repository includes accurate Mac and NVIDIA deployment instructions.

### Final instructions

Start by checking the existing implementation.

Implement missing functionality incrementally.

Do not stop at planning or documentation.

Keep the current Onesa Chat application working.

If Ollama or a suitable model cannot run on the available Mac hardware, still complete the adapter and tests, document the blocker, and preserve the vLLM deployment path.

At completion, report exactly which real inference workflows were successfully tested, which were simulated, and which require additional hardware.

**Start implementing Milestone 2 now.**

# ONESA AI PLATFORM — MILESTONE 2 APPLE SILICON IMPLEMENTATION

**Repository:** `onesa-ai-platform`

**Objective:** Complete real local AI inference for Onesa Chat on an Apple Silicon Mac with at least 24 GB of unified memory, while preserving compatibility with future NVIDIA/vLLM infrastructure.

This instruction extends the existing Milestone 2 specification. Do not restart or rebuild the repository.

## 1. Existing system

The Onesa platform already includes a Next.js frontend, FastAPI API, PostgreSQL, authentication, conversations, knowledge retrieval, agent tools, travel functionality, and a mock inference backend.

The frontend is currently served at:

`http://localhost:3100`

Preserve these components, routes, user data, database migrations, and working interfaces.

Read the existing implementation status, architecture, model-serving configuration, and session handoff documentation before making changes.

## 2. Inference architecture

Implement or complete support for three interchangeable inference backends:

- `mock`: deterministic responses for development and automated tests
- `ollama`: local Apple Silicon inference
- `vllm`: future NVIDIA/Linux inference

Prefer a shared OpenAI-compatible inference client with backend-specific configuration and capability handling, if this fits the existing architecture.

Do not duplicate model-serving logic unnecessarily.

The backend must be switchable through environment configuration, without requiring changes to the frontend or database schema.

## 3. Local model configuration

Use Ollama natively on macOS.

Initial model:

`qwen3:4b-instruct-2507-q4_K_M`

Initial context target:

8,192 tokens.

The model should be hosted on the Mac and accessed by the containerized FastAPI backend using:

`http://host.docker.internal:11434/v1`

Verify whether Ollama is already installed and running before attempting installation.

Do not install a redundant inference instance inside Docker.

Do not start another Ollama process if its API port is already occupied.

Check existing configuration and use established environment variable conventions.

## 4. Real inference features

Implement and verify:

1. Actual model-generated chat completions.
2. Streaming responses.
3. Multi-turn conversation context.
4. Correct inference model identification.
5. Message persistence.
6. Per-request latency measurement.
7. Configurable output token limits.
8. Explicit readiness checks.
9. Model availability checks.
10. Graceful timeout handling.
11. Request cancellation and client disconnect propagation.
12. Consistent error responses.
13. Recovery after Ollama restarts.
14. Preservation of existing user authentication and data isolation.

Ensure the interface accurately distinguishes mock inference from real inference.

Never report mock responses as actual model-generated outputs.

## 5. Model comparison support

Prepare Onesa to evaluate multiple local models.

Initial comparison candidates:

- `qwen3:4b-instruct-2507-q4_K_M`
- `qwen3.5:4b-q4_K_M`
- `qwen3.5:9b-q4_K_M`

Do not download all candidates immediately.

First validate the existing Qwen3 4B model.

Provide commands to download and test the other models when requested.

The model registry should track:

- Model identifier
- Base model
- Quantization
- Inference backend
- Available modalities
- Context configuration
- Evaluation results
- Actual runtime metrics

Use model capability metadata so text-only models are not sent image inputs.

Do not mark the Qwen3.5 models as better without comparative evidence.

## 6. Model evaluation and benchmarking

Build a repeatable benchmark tool that records:

- Model name and revision
- Mac hardware and memory
- Quantization
- Context size
- Time to first token
- Total response latency
- Tokens per second
- Request success rate
- Memory usage where observable
- Concurrent inference behavior
- Tool-calling correctness
- English/German instruction following
- General conversational quality
- Knowledge-grounded response quality

Include a small, curated baseline evaluation set.

Ensure evaluations remain reusable when Onesa introduces its fine-tuned models.

Distinguish measured values from estimates.

## 7. Docker networking

Inspect the existing Docker Compose configuration.

Ensure the API container can access the host-based Ollama service.

Use the supported Docker Desktop host-gateway mechanism.

Do not expose Ollama on `0.0.0.0` solely to solve a networking issue.

If direct host access fails, diagnose connectivity and implement an appropriately restricted local development solution.

Only the Onesa backend should communicate directly with the inference server.

The browser must continue using the existing authenticated Onesa API.

## 8. Future NVIDIA deployment

Preserve the vLLM implementation path.

Document how the same Onesa model-client interface can connect to a private vLLM server running on Ubuntu with NVIDIA GPUs.

Do not attempt to install NVIDIA drivers or CUDA on macOS.

Do not rewrite existing business logic to depend on Ollama.

Keep model deployment configurable so future fine-tuned Onesa weights can replace the foundation model through model registry and configuration changes.

## 9. Testing

Run the existing backend and browser tests before making modifications.

Implement additional tests covering:

- Ollama backend configuration
- OpenAI-compatible request mapping
- Streaming response parsing
- Inference timeouts
- Connection failures
- Cancellation
- Multi-turn context
- Model-not-found responses
- Backend switching
- User data isolation
- Regression tests for mock inference

Use HTTP mocks for automated tests, not live model weights.

Run at least one actual local inference integration test when Ollama and the model are available.

Report real inference tests separately from mocked tests.

## 10. Documentation

Update or create accurate technical documentation covering:

- Apple Silicon inference architecture
- Ollama installation and configuration
- Inference API integration
- Docker networking
- Model comparison
- Context length configuration
- Performance benchmarking
- Error recovery
- Future vLLM migration
- Actual test results

Update:

- `docs/development/IMPLEMENTATION_STATUS.md`
- `docs/development/SESSION_HANDOFF.md`
- `docs/development/CHANGELOG.md`

Maintain consistency with the European-based, internationally applicable positioning of Onesa AI.

## 11. Acceptance criteria

This milestone succeeds when:

1. Onesa Chat at `http://localhost:3100` connects to Ollama through FastAPI.
2. The selected Qwen model produces genuine responses.
3. Responses stream into the chat interface.
4. Conversations retain context and remain persisted.
5. Knowledge, Agents, and Travel remain operational.
6. The existing automated tests continue to pass.
7. Backend switching works without modifying the frontend.
8. Local inference metrics are recorded.
9. Deployment documentation is reproducible.
10. Future vLLM deployment remains supported.

If an environment limitation prevents an acceptance test, implement all testable software, report the limitation, and leave the criterion explicitly pending.

## 12. Execution instructions

Begin by inspecting the current repository.

Run baseline tests.

Implement the smallest necessary changes to enable Ollama inference.

Verify an actual request directly against Ollama.

Then verify an actual request through the Onesa API.

Finally verify it in the Onesa Chat web interface.

Fix failures and update documentation.

Do not stop at a plan.

Do not begin model fine-tuning or unrelated feature development.

At completion, report the exact model used, inference backend, tests run, measured performance, remaining limitations, and the next engineering task.

**Start implementing and verifying real local inference now.**
