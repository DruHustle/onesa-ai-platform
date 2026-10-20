# Supported model integrations

One configured ModelClient serves Chat, RAG answers, agent planning and Travel. Adapters include Cloudflare Workers AI, mock (deterministic, no AI), Ollama (real local generation verified on Apple Silicon), and vLLM (implemented protocol adapter; NVIDIA execution unverified). Backend changes preserve public alias default and application contracts.

## Current hosted configuration

Configuration readback on 20 October 2026 identifies Cloudflare Workers AI generation
with Qwen3-30B-A3B-FP8 and Qwen3-Embedding-0.6B semantic retrieval using the versioned
256-dimensional profile. Hosted application release checks have exercised real generation
and embeddings. Configuration readback alone is not an inference test or an uptime
guarantee. The current service is not entirely self-hosted; provider processing and
transfers need their deployment-specific review.

## Separate local evaluation

The evaluated local baseline is Qwen3 4B Q4_K_M with 8192 context. The small synthetic evaluation passed 12 of 13 strict checks; exact-only arithmetic formatting failed despite a correct answer. This is not broad multilingual, reasoning or safety qualification. Qwen3.5 candidates are uninstalled metadata. Vision and speech remain proposed application adapters. No Onesa weights have been trained.

Selecting a model requires server configuration and a qualified installed model; no end-user selection UI is shipped. Do not download comparison weights or start training without authorization.
