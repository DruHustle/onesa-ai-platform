# Architecture diagrams

Onesa AI is European-based, general-purpose and applicable to European and international
markets. Shared services have no geographic routing or country/language whitelist.
African/regional use cases are optional specializations. See ADR 0003 and AI_SOVEREIGNTY.md.

Solid components below are implemented software. GPU/external/production execution is
pending even where the configuration/adapter exists.

```mermaid
flowchart TD
  Users --> Web[Next.js Chat / Knowledge / Agents / Travel]
  Web --> API[Private FastAPI API]
  API --> Auth[Auth / sessions / CSRF]
  API --> Chat[Conversation and SSE service]
  API --> Knowledge[Document ingestion and retrieval]
  API --> Agents[Bounded planner and tool registry]
  API --> Travel[Typed itinerary planner]
  Auth --> DB[(PostgreSQL / pgvector)]
  Chat --> DB
  Knowledge --> DB
  Agents --> DB
  Travel --> DB
  Chat --> Client[Shared ModelClient]
  Agents --> Client
  Travel --> Client
  Client --> Mock[Labelled deterministic mock]
  Client --> Ollama[Native loopback Ollama / Qwen3 4B — measured on Apple M3]
  Client -. GPU execution pending .-> GPU[Private vLLM / Qwen or Onesa adapter]
  Knowledge --> Lexical[Lexical vector baseline]
  Knowledge -. Service execution pending .-> Embeddings[Configured HTTP embedding model]
  Training[Separate dataset / training / evaluation tools] -. Evaluated artifact only .-> GPU
```

```mermaid
sequenceDiagram
  participant Browser
  participant API
  participant DB as PostgreSQL
  participant Model as Shared model client
  Browser->>API: Origin-checked registration/login
  API->>DB: Hash password / persist hashed session
  API-->>Browser: Session + CSRF cookies
  Browser->>API: Chat, cookie, Origin, CSRF
  API->>DB: Check ownership and lease, commit user/run
  API->>Model: Bounded message stream
  Model-->>API: Deltas
  API-->>Browser: message_start / content_delta
  alt complete
    API->>DB: Commit complete assistant and sources, clear lease
    API-->>Browser: message_end
  else failed or disconnected
    API->>DB: Failed/cancelled run, clear lease, no completed partial text
    API-->>Browser: error if connection remains
  end
```

```mermaid
sequenceDiagram
  participant API
  participant Knowledge
  participant Embedding as Lexical or HTTP embedding adapter
  participant DB as pgvector
  participant Model
  API->>Knowledge: Authorized document IDs and question
  Knowledge->>Embedding: Query vector
  Knowledge->>DB: Filter owner and version; cosine search
  DB-->>Knowledge: Source excerpts
  Knowledge-->>API: Attributed evidence
  API->>Model: Untrusted evidence + question
  Model-->>API: Output stream
  API->>DB: Persist completed answer and source records
```

```mermaid
flowchart LR
  Browser --> Proxy[Caddy TLS — production execution pending]
  subgraph Application host
    Proxy --> Web[Next.js]
    Web --> API[FastAPI]
    Migration[One-shot Alembic] --> DB[(Private PostgreSQL)]
    API --> DB
  end
  subgraph Optional GPU host
    API -. private network .-> VLLM[vLLM]
    VLLM --> Weights[Revision-pinned base / evaluated adapter]
  end
```

```mermaid
flowchart LR
  Base[General-purpose pinned foundation] --> Eval[Base / candidate held-out evaluation]
  Data[Approved multi-domain / multilingual data] --> Adapt[Separate versioned adapters — training pending]
  Adapt --> Eval
  Eval --> Registry[Candidate family / purpose / provenance metadata]
  Registry -. manual reviewed selection only .-> Active[One configured active model / stable API]
  Families[Proposed General / Enterprise / Industrial / Travel / Multilingual / Regional] -. metadata only .-> Registry
```

European/international audiences use this same pipeline. The diagram describes implemented
metadata/evaluation tools and proposed artifacts, not existing trained models or release approval.
