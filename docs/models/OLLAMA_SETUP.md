# Native Ollama on Apple Silicon

Verified host: Apple M3, 24 GB unified memory, macOS 27.0.1 ARM64. Official
[macOS requirements](https://docs.ollama.com/macos) support Apple M-series hardware on
macOS 14+. Hardware/storage were checked before the authorized initial model download.
The exact [Qwen3 tag](https://ollama.com/library/qwen3:4b-instruct-2507-q4_K_M) is available.

Ollama 0.40.2 was installed from the official ollama/ollama GitHub release's ollama-darwin.tgz
inside ignored data/runtime/ollama. Release SHA-256 was verified against its asset digest.
No Homebrew/system-wide installation or second inference container was added. For a fresh
Mac, use the official installation path or download that pinned native archive from
[the official release](https://github.com/ollama/ollama/releases/tag/v0.40.2), verify its release
asset digest before extraction, and place its runtime at data/runtime/ollama/ollama.
Do not download or execute unverified third-party installers.

```sh
.venv/bin/python scripts/local/ollama_service.py status
.venv/bin/python scripts/local/ollama_service.py start
data/runtime/ollama/ollama pull qwen3:4b-instruct-2507-q4_K_M
data/runtime/ollama/ollama list
```

start checks port 11434 first and never starts a duplicate. The repository-owned service binds
127.0.0.1, stores weights under data/models/ollama, disables cloud use, sets context 8192,
one loaded model and one parallel generation. Logs/PID live under ignored data/runtime.
If an established Ollama is already running, use it rather than starting another; inspect
its context/model configuration. The management script refuses to stop a PID that does not
match this repository's runtime. An existing external server needs its own lifecycle controls.

```sh
.venv/bin/python scripts/local/ollama_service.py restart
.venv/bin/python scripts/local/ollama_service.py stop
```

Keep the native service running for make up/Chat. Configure private .env with backend ollama,
model qwen3:4b-instruct-2507-q4_K_M and URL http://host.docker.internal:11434/v1, context 8192,
Q4_K_M provenance and observed model digest. Keep existing database/metrics secrets and Origin.
The [OpenAI compatibility reference](https://docs.ollama.com/api/openai-compatibility) describes
the shared /v1 protocol; choose context through server configuration rather than claiming a
per-request /v1 override. Use /api/ps to observe resident context/allocation.

Docker Desktop's [host networking guidance](https://docs.docker.com/desktop/features/networking/)
provides host.docker.internal. This repository verified an API container reaching loopback-bound
Ollama at that address. Do not bind 0.0.0.0 to work around connectivity. Check the native version
endpoint, container DNS/proxy/firewall and /models first; do not overwrite a working server.
Ollama ignores local API bearer keys. Loopback binding and local trust are the access boundary.

Only the first Qwen3 model was downloaded. Optional comparison commands, when requested:

```sh
data/runtime/ollama/ollama pull qwen3.5:4b-q4_K_M
data/runtime/ollama/ollama pull qwen3.5:9b-q4_K_M
.venv/bin/python -m evaluation.local evaluate data/new-qwen35-report.json \
  --base-url http://127.0.0.1:11434/v1 --model qwen3.5:4b-q4_K_M
```

Both tags were checked against the official library. Recheck storage/runtime compatibility
before downloading. Their upstream vision/tool claims are not Onesa image support or a quality
comparison. No Qwen3.5 weights, evaluations or superiority claims exist here.
