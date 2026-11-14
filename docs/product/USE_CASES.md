# Applications and extension boundaries

| Audience / use case | Implemented reusable foundation | Proposed or unverified work |
| --- | --- | --- |
| Enterprise internal assistant / customer support | Owned chat, documents, retrieval/source history, authentication | Organization tenancy/RBAC, connectors, review workflows, actual model quality |
| Research / document intelligence | Bounded TXT/PDF extraction and lexical pgvector retrieval | Semantic embedding service, larger corpora, approved benchmarks, specialized parsing |
| SMEs / business automation | Shared-model tool planner, grants, local bounded tools and run history | Effectful business tools, enterprise workflow orchestration, economic validation |
| Industrial engineering / manufacturing | General document/tool interfaces, no regional restrictions | Engineering formats, asset/IoT integrations, digital twins, safety validation |
| Travel / tourism / cross-border planning | Preferences, typed saved/revisable itineraries, provider-availability reporting | Maps/weather/prices/flights/accommodation/booking integrations and credentials |
| Developers / institutions | Versioned API, configurable model client, private Compose, training framework | Production hosting/SLA, API-key auth, distributed orchestration, actual model customization |
| Multilingual / regional adaptation | Flexible training language/domain metadata and logical model profiles | Reviewed datasets and evaluations for each language/domain, real adapters |

Enterprise and industrial assistants can use the same registry/planner interfaces as travel
while registering different tools and explicit grants. Travel currently uses its typed planner;
it has no live tools and does not yet route an external booking workflow through agents.
No industrial control, booking execution, vision/speech or robotics capability is claimed.
