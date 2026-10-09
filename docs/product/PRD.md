# Product requirements baseline

Status: working local platform baseline. Chat/auth/persistence, documents/retrieval,
bounded tools and saved travel are implemented and verified with mock inference.
Real GPU/semantic embedding/provider/production execution remains pending.

Onesa AI is a European-based general-purpose modular AI platform for enterprise, developer,
institutional and consumer applications in European and international markets. Organizations
can build, deploy and customize intelligent applications on independently managed open-weight
infrastructure. Priorities include sovereignty, privacy-conscious access, useful general AI,
multilingual/multimodal extensibility, commercial/industrial applications and portable GPU serving.
African languages/regional knowledge remain additional specializations, not the primary identity.

See MARKET_SCOPE.md and USE_CASES.md for audiences and implemented/proposed boundaries.
The suggested “Intelligent Technology Without Boundaries” tagline remains draft copy.
Interface catalogs are independent of evaluated model capabilities. No certification,
regulatory compliance or funding eligibility follows from product positioning.

## MVP scope

Milestone 1 must allow registration/login, creating/renaming/deleting conversations,
sending messages, receiving labelled mock responses incrementally, and reopening
saved history. Users can only read and mutate their own data. No model credentials
or internal addresses appear in user-facing responses. CPU-only development and CI
must not download model weights. Desktop/mobile and keyboard flows must work.

Accept the MVP only after migration tests, auth/isolation tests, model failure and
stream cancellation tests, frontend checks/build, and a browser smoke flow pass.
Docker Compose must start API, PostgreSQL, and chat UI with documented configuration.
Performance targets will be established by measured baselines, not invented here.

## Milestone scope and pending acceptance

M2 enables real vLLM inference; M3 document ingestion/embeddings/pgvector; M4 agents;
M5 Travel; M6 dataset preparation and fine-tuning configuration; M7 release hardening.
M3–M6 software is now delivered; real-model/provider/training acceptance is still pending.
Vision and speech remain future model capabilities. Robotics is a downstream client;
no robot control or robotics dependencies belong in the platform core.

External travel prices, availability, and schedules require provider evidence.
Bookings require separately authorized integrations and confirmation. No expensive
training jobs, remote deployments, or large model downloads are part of the MVP.

## Constraints and open decisions

Use Python 3.11+, FastAPI, SQLAlchemy 2/Alembic, Next.js/TypeScript, PostgreSQL,
Docker Compose, and local NVIDIA/vLLM infrastructure. No Redis/Kubernetes until
requirements justify them. Model selection is configurable; Qwen is a candidate,
not a claim of hardware feasibility. License/ownership, production domain, GPU
capacity, retention policy, and suitable training data remain unresolved.
