# ONESA AI PLATFORM — AMENDMENT 002
## Interactive Documentation, Visual Architecture and Professional PDF Generation

**Repository:** `onesa-ai-platform`  
**Type:** Documentation and Developer Experience Enhancement  
**Priority:** Implement alongside current development without disrupting existing applications.

### 1. Objective

The existing Onesa AI documentation consists mainly of Markdown files.

Upgrade it into a professional, visually rich, interactive technical documentation system suitable for:

- Software engineers and contributors
- AI/ML engineers
- API consumers
- DevOps and infrastructure engineers
- Technical partners
- European research and funding organizations
- Enterprise clients
- Investors reviewing technical capabilities

The result must include:

1. An interactive documentation website.
2. Professionally designed PDF manuals and reports.
3. High-quality architecture images and diagrams.
4. Interactive API documentation.
5. Database architecture visualizations.
6. Step-by-step deployment and development guides.
7. Searchable, interconnected technical reference material.
8. Automated documentation generation and verification.

**Do not simply create more Markdown files. Produce actual rendered documentation assets and a working documentation application.**

### 2. Preserve the Existing Project

Work inside the existing `onesa-ai-platform` repository.

Do not rebuild Onesa Chat, Knowledge, Agents, Travel, authentication, databases, or inference infrastructure.

Read the existing documentation and source code first.

Use the existing Markdown documents as the starting source material.

Avoid copying them into multiple independently maintained versions.

Maintain documentation accuracy and traceability to actual code.

Distinguish clearly between:

- Implemented and tested
- Implemented but not verified
- Mock/simulated
- Planned or proposed

Continue to preserve the European-based, globally applicable positioning of Onesa AI.

### 3. Build the Documentation Portal

Create a documentation application under:

`onesa-ai-platform-frontend/apps/docs/`

Recommended framework:

**Docusaurus with TypeScript and MDX**

If there is already a compatible documentation framework in the repository, evaluate reuse before introducing a replacement.

Default local development address:

`http://localhost:3200`

Do not conflict with Onesa Chat at port 3100.

Implement a professional documentation interface with:

- Onesa AI branding
- Homepage with documentation categories
- Left navigation sidebar
- Global search
- Breadcrumb navigation
- Section table of contents
- Light and dark themes
- Responsive layouts
- Reading progress where appropriate
- Copyable code snippets
- Syntax highlighting
- Tabbed examples
- Expandable technical explanations
- Documentation version display
- Related-document links
- Downloadable assets
- Searchable API reference

Use the established Onesa branding, and do not invent a new official logo.

Build the portal as a separately deployable component.

It must not interfere with the existing Chat application.

### 4. Interactive Architecture Documentation

Develop architecture pages using Mermaid, SVG, and appropriate React components.

Required diagrams:

**System Architecture**

Show the interaction among:

- Onesa Chat
- Onesa Travel
- Onesa API
- Authentication
- Conversation management
- Model inference
- Agent runtime
- Knowledge/RAG
- PostgreSQL
- Model registry
- Fine-tuning infrastructure

**AI Inference Pipeline**

Show the actual request path:

User → Frontend → API → Model Adapter → Model Server → Response Stream.

Illustrate Mock, Ollama, and vLLM backend options according to their implemented status.

**Microservices and Components**

Show application boundaries, communication methods, and service dependencies.

**Database Architecture**

Produce a readable entity relationship diagram based on actual database models and migrations.

**RAG Architecture**

Show ingestion, parsing, chunking, embeddings, vector storage, retrieval, and context construction.

**Agent Architecture**

Show the model, planning, tool registry, permissions, tool execution, and feedback.

**Deployment Architecture**

Provide separate diagrams for:

- Apple Silicon development
- Docker Compose application infrastructure
- NVIDIA GPU inference deployment
- Proposed distributed GPU deployment

**Model Development Lifecycle**

Show base model → dataset preparation → training → evaluation → model registry → deployment → rollback.

#### Interactive Diagram Requirements

Where useful, users should be able to:

- Zoom and pan
- Open diagrams in a larger view
- Select components to view their responsibilities
- Navigate to related technical documentation
- Inspect component relationships
- Switch between logical and deployment views

Use actual SVG or interactive diagram components.

Avoid unnecessarily elaborate 3D visualizations.

Keep editable Mermaid or diagram source files in the repository.

Export each relevant diagram to SVG and PNG.

Use SVG for scalable documentation graphics and high-resolution PNG for presentations and other media.

Ensure text labels do not overlap or become unreadable.

### 5. Generate Professional PDF Documentation

Create a reproducible PDF generation pipeline.

Use print-specific styles and a suitable HTML-to-PDF approach such as Playwright Chromium, or another justified document-generation approach.

Generate actual PDF files, not Markdown files merely renamed to `.pdf`.

Produce the following technical documents:

**01 — Onesa AI System Architecture.pdf**

Include system overview, components, boundaries, diagrams, key decisions, and deployment architecture.

**02 — Onesa AI Software Design Specification.pdf**

Include application structure, backend design, model adapters, agent runtime, component interfaces, and software design decisions.

**03 — Onesa AI API Reference.pdf**

Include documented endpoints, authentication, request and response schemas, errors, and examples derived from the actual OpenAPI specification.

**04 — Onesa AI Database Design.pdf**

Include the actual database schema, table definitions, foreign keys, indexes, migration architecture, and ERD.

**05 — Onesa AI Deployment and Operations Manual.pdf**

Include macOS development, Docker, Ollama, NVIDIA/vLLM deployment, environment configuration, monitoring, backup, and recovery procedures.

**06 — Onesa AI Model Development and Fine-Tuning.pdf**

Include base-model strategy, model registry, training architecture, LoRA/QLoRA, dataset management, evaluation, and deployment lifecycle.

**07 — Onesa AI Technical Overview.pdf**

Create a concise professional document appropriate for technical partners, research organizations, enterprise prospects, and funding discussions.

Cover the platform's purpose, architecture, implemented capabilities, technology differentiation, European relevance, model independence, and development roadmap.

This document must accurately distinguish delivered software from proposed work.

#### PDF Design Requirements

Each document must include:

- Professional cover page
- Document title
- Version
- Generation date
- Document status
- Table of contents
- Numbered sections
- Page numbers
- Headers and footers
- Readable typography
- Consistent spacing
- Properly formatted code examples
- Tables that do not overflow
- Architecture diagrams
- Internal links/bookmarks where supported
- References to relevant technical documents

Use A4 page dimensions as the primary format.

Use consistent Onesa AI design tokens.

Ensure diagrams fit the page and remain readable.

Prefer vector graphics.

Avoid large blank sections, clipped images, broken links, and overlapping text.

PDFs are static reference documents; preserve links and bookmarks, while keeping live interactive behavior in the documentation website.

### 6. Interactive API Explorer

Build an API documentation section directly from the implemented FastAPI OpenAPI schema.

Use a suitable API viewer such as Swagger UI or Scalar.

The API reference should support:

- Endpoint discovery
- HTTP methods and URLs
- Required authentication
- Request parameters
- JSON schemas
- Example payloads
- Response codes
- Error handling
- Streaming API documentation
- Copyable request examples

Enable interactive API execution only against an explicitly configured development or authorized testing environment.

Never embed private API keys or credentials in the generated documentation.

Do not expose administrative or private inference endpoints to public documentation users.

Keep the generated API reference synchronized with the FastAPI application.

### 7. Visual Database Documentation

Generate database documentation from actual SQLAlchemy models and Alembic migrations.

Required artifacts:

- Entity relationship diagram
- Table relationship overview
- Foreign-key visualizations
- Data lifecycle diagrams
- Conversation persistence flow
- Knowledge ingestion and embedding flow
- Model registry data relationships

Provide a navigable database reference in the documentation portal.

Clicking a documented table should reveal its columns, types, constraints, relationships, and indexes.

The diagrams must reflect the implemented database, not only an earlier proposed schema.

Export database diagrams as SVG and PNG and include suitable versions in the database design PDF.

### 8. Screenshots and Visual Tutorials

Capture screenshots of the actual running Onesa applications using Playwright.

Where operational, document:

- Onesa Chat
- User authentication
- Conversation history
- Model selection or inference status
- Knowledge upload
- Knowledge retrieval
- Agent tools
- Travel planning
- Application settings

Create image-based setup guides.

Include screenshots alongside explanations and code examples.

Use a deterministic test account and synthetic data.

Do not expose passwords, authentication tokens, real user information, private documents, or secrets.

If a feature cannot be captured, mark the screenshot as unavailable rather than creating a misleading image.

### 9. Deployment Tutorials

Provide visually guided deployment documentation.

Include:

**mac