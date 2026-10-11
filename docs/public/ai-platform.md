# AI Platform technical overview

## Application design

The Next.js chat application exposes Chat, Knowledge, Agents, Travel and settings. Its server-side API boundary forwards to FastAPI while keeping backend credentials out of browser bundles. The FastAPI backend enforces identity, ownership, request limits, configured origins and schema compatibility. PostgreSQL stores application state separately from Portal data.

Registration may require an invitation. Recovery uses expiring, one-use tokens and a durable notification workflow. Secure sessions and CSRF protection apply to authenticated mutations. Two-user ownership tests cover conversations, documents, agents and itineraries. A configured frontend alone does not prove backend availability.

## Conversations and inference

Conversation creation and history persist independently of generation. Chat routes share a model abstraction with mock, Ollama and vLLM adapters. Streaming, cancellation, errors and timeouts are explicit. The local Ollama model tag is not assumed interchangeable with a Hugging Face vLLM checkpoint. No fine-tuned Onesa weights are established by the registry scaffolding.

The isolated hosted staging core has passed identity, ownership, restart and idle-connection checks. Mandatory generation and embedding endpoints remain unavailable. Missing inference must produce an honest unavailable response; a deterministic mock cannot qualify real hosted chat. Core readiness and inference readiness are deliberately separate.

## Knowledge and retrieval

The pipeline validates files, parses and chunks them, obtains versioned embeddings, persists vectors and searches within the requesting user's permitted documents. Citations identify retrieved sources; retrieval does not authorize cross-user access. Updates and deletion must preserve index consistency. pgvector dimensions and the embedding model/version must agree. The established default is the clearly labelled 256-dimensional lexical hashing baseline, not semantic model embeddings. The HTTP semantic adapter is implemented, but its production service/model and hosted retrieval path remain unqualified. A chat endpoint does not prove an embedding endpoint works. Private file persistence must be qualified separately from database persistence.

## Agents and Travel

Agents enforce registered tool schemas, explicit allowed tools, bounded execution, ownership and audit history. Model text does not grant permission. Deterministic permitted tools can function without generation; model-dependent planning cannot be claimed available without the real model.

Travel persists owned trips and validates planning inputs. Generated suggestions are not live travel inventory, booking, pricing or confirmation. Provider adapters and current information remain unqualified unless their actual path has been tested.

## Training and evaluation

Dataset preparation, evaluation separation, configuration and registry foundations exist. Expensive training is not launched by a documentation build. Provenance, licensing and authorization govern any training input; customer conversations are not automatically training material. Checkpoints, GPU memory and model release evidence remain separate qualification gates.

[Open Onesa AI](https://platform.onesa.eu/) · [Authentication](authentication.md) · [Models](models.md) · [API explorer](/api-explorer).
