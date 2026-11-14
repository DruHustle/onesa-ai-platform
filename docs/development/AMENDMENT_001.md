# ONESA AI PLATFORM — MASTER SPECIFICATION AMENDMENT 001

## Strategic Positioning, Market Scope, Model Development and Documentation Update

**Repository:** `onesa-ai-platform`  
**Amendment:** 001  
**Type:** Update to the existing Master Software Engineering, Architecture and Documentation Instructions  
**Priority:** Supersedes conflicting product-positioning and market-scope instructions in the original specification.

## 1. IMPORTANT — CONTINUE EXISTING DEVELOPMENT

This is an amendment to the original Onesa AI development instructions, **not a replacement of the existing project**.

Do not restart development, create a new repository, discard completed work, or unnecessarily restructure the existing implementation.

Continue working in the existing `onesa-ai-platform` repository.

Preserve the original technical requirements, including:

- Open-weight foundation model deployment
- Local inference infrastructure
- FastAPI backend
- Next.js frontend
- PostgreSQL database
- Onesa Chat
- Onesa Travel
- Knowledge retrieval and RAG
- Agent framework
- Multimodal AI capabilities
- Model fine-tuning infrastructure
- Docker and GPU deployment
- Security and authentication
- Automated testing
- CI/CD
- Technical documentation

All previously specified engineering milestones remain valid unless explicitly modified below.

Review the current codebase and documentation before applying this amendment.

## 2. REVISED PRODUCT DEFINITION

Onesa AI is a **European-based, general-purpose, modular artificial intelligence platform** designed for enterprise, developer, institutional, and consumer applications across European and international markets.

The platform enables organizations and developers to build, deploy, operate, and customize intelligent applications using open-weight AI models and independently managed infrastructure.

Onesa AI emphasizes:

1. AI sovereignty and technological independence.
2. Secure, privacy-conscious AI infrastructure.
3. General-purpose and enterprise AI capabilities.
4. Intelligent applications and workflow automation.
5. Open-weight foundation model deployment and customization.
6. Multilingual and multimodal AI.
7. Industrial and commercial AI solutions.
8. Efficient inference and scalable GPU infrastructure.
9. European market relevance and international competitiveness.
10. Adaptability to different industries, languages, countries, and regional contexts.

The platform must not be defined primarily by a particular continent, language group, or national market.

**African languages, knowledge, and regional applications remain supported as additional specialization opportunities, not the platform's principal identity or architectural limitation.**

## 3. EUROPEAN MARKET AND COMMERCIAL ORIENTATION

Design and document Onesa AI as a technology platform with clear relevance to European businesses, institutions, developers, and research organizations.

Important commercial and technical application areas include:

### Enterprise AI

- Internal AI assistants
- Knowledge management
- Document intelligence
- Business process automation
- Research and information retrieval
- Customer support
- Enterprise workflow orchestration

### Industrial AI

- Manufacturing intelligence
- Industrial knowledge assistants
- Engineering document interpretation
- Asset data management
- Industrial IoT integration
- Digital twin applications
- Automation and engineering workflows

### Travel and Tourism

- AI trip planning
- Itinerary optimization
- Tourism information services
- Multilingual travel assistants
- Cross-border travel applications
- Travel research and booking integrations

### Developer Platforms

- AI inference APIs
- Model hosting
- Application integration
- Tool-calling APIs
- Agent development
- Model customization
- AI workflow infrastructure

### Multilingual and Regional Applications

- English
- German
- French
- Spanish
- Other European languages
- African languages, including Shona and Ndebele
- Additional international language and domain specializations

The architecture must remain capable of serving multiple markets through common infrastructure.

Do not hardcode geographic assumptions into shared platform services.

## 4. EUROPEAN FUNDING AND INNOVATION RELEVANCE

The product architecture and supporting documentation should clearly communicate genuine technological and economic relevance to European markets.

Relevant innovation themes include:

**Sovereign AI**

Self-hosted models, independent infrastructure, model portability, and control over AI deployment.

**Trustworthy and Privacy-Conscious AI**

Secure model access, governance, data protection, auditability, and appropriate regulatory readiness.

**Industrial Digitalization**

AI-assisted engineering, manufacturing, digital twins, industrial knowledge systems, and intelligent automation.

**European SME Competitiveness**

Accessible, customizable AI services that help smaller businesses adopt AI technology.

**Applied AI Research**

Efficient inference, model adaptation, multilingual performance, retrieval, evaluation, and distributed GPU infrastructure.

**International Scalability**

European-developed technology serving international markets without requiring separate infrastructure for each region.

Do not claim that Onesa AI automatically qualifies for EU grants, complies with every applicable regulation, or has received certifications.

Instead, document demonstrable technical capabilities and identify which regulatory, commercial, and funding requirements require additional verification.

The system should provide evidence suitable for future funding proposals, such as architecture diagrams, benchmarks, evaluation results, milestones, technical reports, and documented innovation activities.

## 5. MODEL DEVELOPMENT STRATEGY — UPDATED PHASE B

The original two-phase model development strategy remains unchanged.

### Phase A — Existing Open-Weight Foundation Model

Deploy and operate a general-purpose open-weight foundation model.

The initial candidate remains:

`Qwen/Qwen3-4B-Instruct-2507`

Keep the model configurable and replaceable.

The initial model should retain broad general-purpose capabilities.

Do not prioritize a geographically specialized model over general-purpose quality during the first deployment.

### Phase B — Onesa Model Customization and Fine-Tuning

Fine-tuning is now defined as a general-purpose, multi-domain model development capability.

The training platform must support adapting open-weight foundation models for:

- General assistant performance
- Enterprise knowledge and workflows
- Industrial and engineering applications
- Travel and tourism
- European languages
- Multilingual reasoning
- Specialized business domains
- Regional knowledge and language adaptation
- African languages and contexts
- Other future specializations

Do not assume that all specializations must be combined into one fine-tuned checkpoint.

Prefer a reusable base model with independently versioned adapters or specialized model releases when technically appropriate.

Preserve general assistant performance through regression evaluation against the original foundation model.

Fine-tuning must be accompanied by reproducible evaluation, dataset provenance, and model versioning.

## 6. MODEL FAMILY DESIGN

Design the model registry so it can support future specialized Onesa model releases.

Proposed logical model profiles include:

**Onesa General**
General-purpose conversational and reasoning tasks.

**Onesa Enterprise**
Business knowledge, document intelligence, and organizational workflows.

**Onesa Industrial**
Engineering, manufacturing, industrial data, and automation-related applications.

**Onesa Travel**
Travel planning, destination knowledge, and tourism-focused tasks.

**Onesa Multilingual**
Multilingual communication, translation, and language-specific adaptation.

**Onesa Regional**
Optional regional and cultural knowledge specialization, including African languages and markets.

These are proposed profiles, not existing trained models.

Do not create separate large model deployments for all profiles during the initial development phase.

Implement the model registry and deployment configuration so such profiles can be supported later.

Maintain accurate model provenance and licensing information.

## 7. DATABASE AND API IMPLICATIONS

Review the original database and API design to ensure it supports generalized model and application customization.

### Model Registry

Support metadata for:

- Base model
- Model family
- Model version
- Model purpose
- Supported languages
- Supported domains
- Fine-tuning adapter
- Training dataset version
- Evaluation results
- Deployment status
- Licensing and provenance

Language and regional fields must not be restricted to African languages or a fixed list of countries.

### Knowledge Engine

Support independent knowledge collections for:

- Enterprise documents
- General knowledge
- Engineering and industry
- Travel information
- Language resources
- Country-specific content
- Regional content

Use flexible metadata rather than hardcoded geographic categories.

### Agent Runtime

The tool and agent architecture must be independent of specific markets.

For example, Onesa Travel should use the same agent runtime as an enterprise research assistant, but register different tools and permissions.

### API Design

Public APIs should expose general capabilities and explicit configuration, not embed regional assumptions into endpoint names.

The existing API versioning and core contracts should remain stable.

Do not introduce unnecessary breaking API or database changes merely to update product positioning.

## 8. FRONTEND AND BRAND POSITIONING

Update Onesa Chat and future application copy so that the product presents itself as a general-purpose AI service.

Avoid describing the platform primarily as:

- An African chatbot
- An Africa-only AI model
- A Zimbabwe-specific assistant
- An AI system limited to regional languages

Instead, use positioning consistent with:

**Onesa AI — Intelligent Technology Without Boundaries**

Suggested product description:

"Onesa AI is a modular, self-hosted artificial intelligence platform built on open-weight foundation models. It enables businesses, developers, and organizations to create secure, customizable AI applications, from conversational assistants and enterprise knowledge systems to intelligent agents and industry-specific solutions."

Treat the suggested tagline as draft copy, not an approved official brand asset.

Keep interface language configurable.

English may be the initial interface language.

Architect for internationalization, including German and other supported languages.

Do not imply that a language is supported by the model unless its performance has been verified.

## 9. UPDATE ALL EXISTING TECHNICAL DOCUMENTATION

Review existing documentation and modify any sections that conflict with the revised positioning.

At minimum, inspect and update:

### Product

- `README.md`
- `docs/product/PRD.md`
- `docs/product/ROADMAP.md`

### Architecture

- `docs/architecture/SYSTEM_ARCHITECTURE.md`
- `docs/architecture/COMPONENTS.md`
- `docs/architecture/DATA_FLOWS.md`
- `docs/architecture/DIAGRAMS.md`

### Model Development

- `docs/models/MODEL_SELECTION.md`
- `docs/models/MODEL_REGISTRY.md`
- `docs/models/MODEL_EVALUATION.md`

### Training

- `docs/training/DATASET_STRATEGY.md`
- `docs/training/FINE_TUNING.md`
- `docs/training/EVALUATION.md`
- `docs/training/MODEL_RELEASE.md`

### Commercial and Innovation Documentation

Create, where appropriate:

- `docs/product/MARKET_SCOPE.md`
- `docs/product/USE_CASES.md`
- `docs/product/EUROPEAN_MARKET_RELEVANCE.md`
- `docs/architecture/AI_SOVEREIGNTY.md`
- `docs/models/MODEL_CUSTOMIZATION_STRATEGY.md`

These should explain:

- European market applications
- International applicability
- Enterprise and industrial use cases
- Sovereign AI deployment
- Technology differentiation
- Model customization
- Platform extensibility

Documents should distinguish implemented functionality from proposed functionality.

Do not create duplicate documentation if the same content is already maintained clearly elsewhere.

## 10. ENGINEERING IMPLEMENTATION REQUIREMENTS

This amendment is primarily a product strategy and architecture-alignment update.

Do not rewrite functioning code unnecessarily.

However, if the implementation contains geographic or language-specific limitations inconsistent with the revised strategy, refactor them.

Examples include:

- Hardcoded African language lists
- Region-specific model routing
- Geographic assumptions in API validation
- Fixed regional dataset schemas
- Country-specific knowledge storage
- Application logic that assumes one geographic market
- Inflexible multilingual configuration

Use configuration, typed metadata, and extensible interfaces wherever appropriate.

Maintain existing tests and add regression tests for changed behavior.

## 11. EUROPEAN DEPLOYMENT AND DATA PROTECTION

Retain the original security and privacy requirements.

Ensure the architecture can support deployment on European-owned or European-hosted infrastructure when selected.

Document:

- Data residency configuration
- Authentication and authorization
- GDPR-relevant data processing responsibilities
- Data retention and deletion
- Self-hosted inference
- Model and application auditability
- Secure access to enterprise data
- Infrastructure portability
- Application and inference isolation
- Regulatory considerations, including the EU AI Act where applicable

Do not equate self-hosting with automatic legal compliance.

Identify deployment-specific, organizational, and legal obligations separately from software engineering controls.

## 12. MAINTAIN THE EXISTING IMPLEMENTATION ROADMAP

Do not change the engineering milestone order unnecessarily.

Continue the original implementation sequence:

1. Onesa Chat MVP
2. Real local model inference
3. Knowledge retrieval and document intelligence
4. Reusable agent framework
5. Onesa Travel application
6. Model fine-tuning framework
7. Production readiness

Apply the updated positioning and general-purpose architecture across all milestones.

Do not delay the initial Onesa Chat delivery for new branding work, market-research documents, or optional specialization features.

## 13. REQUIRED ACTIONS NOW

Perform the following actions in the existing `onesa-ai-platform` repository.

1. Read the original specification and current implementation progress.
2. Inspect existing product, architecture, model, and training documents.
3. Identify statements positioning Onesa AI primarily as an Africa-focused model or platform.
4. Update these statements to reflect the new European and international positioning.
5. Retain African languages and regional specialization as additional capabilities.
6. Review the data models, configuration, model registry, and APIs for unnecessarily hardcoded regional limitations.
7. Apply only the technical changes required to keep the platform extensible.
8. Update architecture diagrams where necessary.
9. Record this amendment and its implications in the architecture decision records.
10. Update the roadmap, implementation status, and session handoff documents.
11. Run relevant tests and report the results.
12. Resume the existing implementation milestone from where development previously stopped.

Do not discard working code or regenerate the application from scratch.

## 14. COMPLETION REPORT

After applying this amendment, provide:

- Summary of product-positioning changes
- Files updated
- Architectural implications
- Code changes, if any
- Test results
- Remaining work
- Current implementation milestone
- Next engineering task

Clearly distinguish changes to documentation from changes to working functionality.

## FINAL DIRECTIVE

Onesa AI is a **European-based, globally applicable AI technology platform**.

Its primary identity is general-purpose AI infrastructure, model deployment and customization, enterprise intelligence, intelligent applications, and AI sovereignty.

African languages and regional applications are part of the platform's international capabilities, but do not define or limit its overall scope.

**Apply this amendment to the existing `onesa-ai-platform` project, preserve completed engineering work, update the documentation, and continue implementation from the current milestone.**
