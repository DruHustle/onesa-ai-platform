# Onesa ecosystem

Onesa UG is the parent technology company. The Company Portal supports the company website and private business administration. Onesa AI Platform is its first AI product. Onesa AI Robot is an independently released robotics software project. Each owns a separate Git repository, frontend and backend; documentation hosting does not merge their application releases.

## Logical boundaries

The Company Portal uses Next.js and a Fastify API for published corporate content, enquiries, applications, document workflows and administration. The AI Platform uses Next.js and FastAPI for identity, conversations, Knowledge, Agents and Travel. Robot uses a static operator interface, a same-origin Node proxy and FastAPI for authenticated software simulation. Products have separate sessions, authorization and data stores. A product link is not single sign-on.

## Evidence labels

**Implemented** describes source code. **Locally verified** describes a tested fixture. **Hosted core verified** means the deployed non-model API was checked. **Mock** means deterministic synthetic output. **Unavailable** means a mandatory dependency is missing. **Proposed** means design only. These labels are different from a production release approval.

| Component | Current qualification |
| --- | --- |
| Company website | Hosted public site exists; corrected application candidate still needs production acceptance |
| Portal administration and business workflows | Implemented and isolated-test verified; hosted database role, worker, storage and operational acceptance remain incomplete |
| AI identity, conversations and deterministic permitted tools | Hosted isolated staging core verified; public production not qualified |
| Hosted AI generation and semantic retrieval | Unavailable until authenticated real generation and embedding dependencies are provisioned and tested |
| Local Ollama | Previously verified development path; not a hosted production endpoint |
| Mock model | Test fixture only; never a silent production fallback |
| Robot operator workflows and independent safety gate | Implemented and isolated-test verified software simulation; persistent hosted qualification pending |
| Physical robot, connected ROS nodes, audio/vision and VLA | Proposed or unavailable; no hardware control or physical safety certification |

## Deployment boundaries

Vercel hosts frontends and this separate public static documentation site. Render hosts application APIs where configured. Portal and AI use separate PostgreSQL databases; Robot currently uses private SQLite and requires persistent storage. Object storage is separate from PostgreSQL. External model serving is not automatically part of Render's private network. Production needs an authenticated transport with explicitly approved endpoints.

The corporate site must remain usable when inference is unavailable. Neither AI nor Robot may query Portal-private tables. Robot integration with the AI API is proposed; its model output must never bypass independent motion validation.

See [Company Portal](company-portal.md), [AI Platform](ai-platform.md), [Robot](robot.md), [deployment](deployment-overview.md), [public architecture](architecture.md) and [documentation access](documentation-access.md). Interactive diagrams and downloadable approved manuals describe these same boundaries.
