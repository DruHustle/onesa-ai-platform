# Supported model integrations

One configured ModelClient serves Chat, RAG answers, agent planning and Travel. Backends are mock (deterministic, no AI), Ollama (real local generation verified on Apple Silicon), and vLLM (implemented protocol adapter; NVIDIA execution unverified). Backend changes preserve public alias default and application contracts.

The verified baseline is Qwen3 4B Q4_K_M with 8192 context. The small synthetic evaluation passed 12 of 13 strict checks; exact-only arithmetic formatting failed despite a correct answer. This is not broad multilingual, reasoning or safety qualification. Qwen3.5 candidates are uninstalled metadata. Vision and speech remain proposed application adapters. No Onesa weights have been trained.

Selecting a model requires server configuration and a qualified installed model; no end-user selection UI is shipped. Do not download comparison weights or start training without authorization.
