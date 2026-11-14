# Onesa AI Platform

The platform brings together **Applications** and **Industrial AI**. Applications
include the existing protected Chat, Knowledge, Agents and Travel workspace.
Industrial Investigation is available as an isolated, protected synthetic software
 demonstration. Ordinary AI production keeps Industrial disabled. Wider industrial
 integrations remain under development. Robotics / Physical AI is Onesa’s separate
 development line.

## Industrial Investigation — isolated synthetic demonstration

Maintenance and reliability engineers can inspect a repeated-stop investigation for
one permitted asset and UTC window. Deterministic facts and interval totals remain
separate from source-linked hypotheses, missing evidence and an editable internal
draft. Saved source versions, evidence hashes and self-review decisions make the
result traceable. The demonstration has not established customer benefit or
independent domain acceptance. There is no live factory, PLC, actuator or CMMS
write integration.

The first proposed limited pilot evaluates permitted event histories and versioned
maintenance references against a predefined human-reviewed task. The new JSON import
adapter is a development candidate qualified initially with synthetic inputs; it is
not an advertised live connector or approval for customer data.

[Discuss a focused pilot scope](https://onesa.eu/en/contact?topic=industrial).

## Apps powered by the Onesa AI Platform

The same intelligence engine can support different industries. Alongside the
existing application experiences, business and investment decision support and
smart farming are planned applications:

- **Recommendations and decision support** — Travel planning, business feasibility
  and investment research. Help users compare options, explore scenarios and assess
  risks using relevant information, clearly stated assumptions and supporting sources.
- **Smart farming** — Help farmers choose suitable crops and plan cultivation step
  by step, from planting to harvest. Combine soil conditions, seasonal weather
  forecasts, water availability, production costs and market demand to support
  practical decisions.

See [application directions](applications.md#application-directions) for the
implementation status and required data integrations.

## Application design

The Next.js chat application exposes Chat, Knowledge, Agents, Travel and settings. Its server-side API boundary forwards to FastAPI while keeping backend credentials out of browser bundles. The FastAPI backend enforces identity, ownership, request limits, configured origins and schema compatibility. PostgreSQL stores application state separately from Portal data.

Registration may require an invitation. Recovery uses expiring, one-use tokens and a durable notification workflow. Secure sessions and CSRF protection apply to authenticated mutations. Two-user ownership tests cover conversations, documents, agents and itineraries. A configured frontend alone does not prove backend availability.

## Conversations and inference

Conversation creation and history persist independently of generation. Chat routes share a model abstraction with explicitly configured Cloudflare Workers AI, mock, Ollama and vLLM adapters. Streaming, cancellation, errors and timeouts are explicit. The local Ollama model tag is not assumed interchangeable with a Hugging Face vLLM checkpoint. No fine-tuned Onesa weights are established by the registry scaffolding.

Hosted application release checks have exercised real Workers AI generation and semantic
embeddings, alongside authentication, ownership and application workflows. Current
configuration readback selects Cloudflare in staging and production; it is not a new
inference or model-quality test. Missing inference produces an explicit unavailable
response. Core readiness and inference readiness remain deliberately separate.

## Knowledge and retrieval

The pipeline validates files, parses and chunks them, obtains versioned embeddings, persists vectors and searches within the requesting user's permitted documents. Citations identify retrieved sources; retrieval does not authorize cross-user access. Updates and deletion must preserve index consistency. pgvector dimensions and the embedding model/version must agree. Local development defaults to the clearly labelled 256-dimensional lexical hashing
baseline. The hosted configuration uses the versioned Workers AI Qwen semantic profile;
the HTTP adapter remains separately configurable. A chat response does not prove an
embedding endpoint works. The applicable release must verify both retrieval and private
persistence; configuration alone cannot qualify them.

## Agents and Travel

Agents enforce registered tool schemas, explicit allowed tools, bounded execution, ownership and audit history. Model text does not grant permission. Deterministic permitted tools can function without generation; model-dependent planning cannot be claimed available without the real model.

Travel persists owned trips and validates planning inputs. Generated suggestions are not live travel inventory, booking, pricing or confirmation. Provider adapters and current information remain unqualified unless their actual path has been tested.

## Training and evaluation

Dataset preparation, evaluation separation, configuration and registry foundations exist. Expensive training is not launched by a documentation build. Provenance, licensing and authorization govern any training input; customer conversations are not automatically training material. Checkpoints, GPU memory and model release evidence remain separate qualification gates.

[Open Onesa AI](https://platform.onesa.eu/) · [Authentication](authentication.md) · [Models](models.md) · [API explorer](/api-explorer).
