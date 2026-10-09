# Amendment 002.2 implementation and verification report

2026-10-09 · documentation version 0.2.0 · internal engineering · local development acceptance. No remote publication or production readiness is claimed.

## Public documentation

Running URL: http://localhost:3200. Functional independent developer experience includes introduction, quickstart, authentication, applications, integration, streaming, models, high-level architecture, roadmap, release notes, glossary, privacy, troubleshooting, tutorials and validated examples. Local full-text search covers headings, API operations, components and terminology with previews and Command-K/Control-K. Scoped OpenAPI excludes operational/private inference and portal-engineering routes. Seven manuals: technical overview, API reference, developer getting started, agent framework, Knowledge/RAG, security/data protection and model serving. Searchable library supports classification/version/status/date and PDF preview/download.

## Internal documentation

Running URL: http://localhost:3201. Separate build and asset tree, protected on every request through the existing Onesa session/engineering allowlist. Default access denied; anonymous requests return 401, ordinary accounts 403 and identity failure fails closed. Logout revokes direct asset access. No independent password system. Existing architecture, services/design, ADRs, database, AI/model/training/evaluation, deployment/operations, security, tests, roadmap, reports and handoff content is categorized and searchable. Twelve restricted manuals cover all requested categories. HTML, JS/CSS, diagrams, PDF files, search/retrieval JSON and manifests pass through the same server guard. No restricted artifacts appear in the public build.

## Application integration

Chat desktop and mobile navigation includes Documentation; shared feature navigation covers Knowledge, Agents and Travel. Engineering destination is shown only after the API confirms engineering permission. Contextual links use a central route registry; return links connect both portals to the existing applications. Existing English/German application catalogs remain; documentation is English only. URLs are configurable, with frontend container build arguments. Auth secrets never enter navigation URLs.

## Interactive features

Architecture explorer: sixteen requested subsystem views, status-labelled components, details/relationships/reference links, zoom, pan, fit, enlargement and SVG/PNG exports. Database explorer: actual ten SQLAlchemy tables, column SQL types/nullability/keys/defaults, FK/delete behavior, indexes, constraints and three migration references; five generated relationship group diagrams. Candidate model/evaluation registry is file-based and is explicitly not represented as invented database tables.

API playground: OpenAPI-driven Swagger UI, read-only default. Explicit local loopback target only; permitted documented methods/paths, own Origin checks, cookie/CSRF passthrough, bounded request size, no metrics/private inference/engineering route execution. Request execution is not configured for production. The gateway buffers playground responses; direct application examples demonstrate incremental SSE.

Classified gallery shows diagrams and actual synthetic screenshots. Fifteen guided procedures include commands, expected outcomes, screenshots and troubleshooting; NVIDIA instructions remain hardware-unverified. Checklists store local notes and do not validate infrastructure. The assistant uses existing Knowledge embedding/model adapters, with separate public/internal source collections and authorization before internal retrieval. Live public answering used real Ollama with assigned public citations; unknown evidence returns uncertainty. Retrieval remains lexical. Feedback produces a local copy/download report; no remote issue tracker is configured or automatic submission performed.

## Generated artifacts

- Nineteen real A4 PDFs: seven public, twelve internal; covers/classification/version/date/status, contents, numbered headings, headers/footers/page numbers, readable tables/code, vector figures, references and bookmarks.
- Twenty-eight editable Mermaid diagrams with SVG and PNG renders: four public and twenty-four internal, including five actual-schema relationship groups.
- Seven actual synthetic interface captures per scoped library: sign-in, registration, Chat/history/status, Knowledge upload/search, Agents execution, Travel and interface preferences. No simulated screenshots, passwords or tokens exported.
- FastAPI-derived scoped OpenAPI, ten-table metadata, migrations, separate local search indexes, source hashes and permission-scoped retrieval data. Generated exports are under docs/generated/{public,internal}; staging/builds are separate and ignored.

## Verification

84 real PostgreSQL tests passed. CPU checks: 61 passed, 23 integration tests skipped without database. Ruff/format and strict mypy (18 application files) passed. Frontend lint/type/production build and documentation type checking passed. Both documentation website builds passed with broken links treated as errors. Original mock browser flows: 4 passed; real model streaming/context/history browser acceptance: 1 passed. Live documentation browser checks passed search, diagrams, manual counts/preview/download, direct internal denial, engineering identity, logout revocation, desktop/mobile integration, real cited assistance and local playground/private-route rejection. Keyboard/navigation/semantic controls are checked; this is not a full external accessibility certification.

Classification/provenance checks validate approved public sources/assets, code/schema hashes, diagram source/render pairing, PDF hashes/bookmarks/classification/source metadata and absence of restricted pages, database payloads, search content and private markers. Negative public exposure testing deliberately inserts an internal canary after a clean baseline and verifies rejection. CI config adds scope builds, rendering/validation, drift checks and mock cross-application browser verification; remote execution has not occurred.

Dependency blocker resolved: the earlier 33 affected entries arose from braces/sprintf-js. Reviewed local backports now protect nesting/AST traversal and numeric precision/padding; all affected consumers resolve the patched packages. Twelve attack, integrity and real consumer compatibility tests pass after clean installation. npm audit now reports zero findings, and `make docs-release-check` passes without suppression, with audit enforced at all severities. Supported Node 24 and React 18 documentation peers are qualified; existing application React is unchanged. See [dependency remediation](../security/DOCUMENTATION_DEPENDENCIES.md). One upstream TestClient deprecation warning remains. No third-party analytics, remote publishing workflow, model download, new training or project license was added.

Initial failures retained: vague real agent plan failed validation during capture; explicit statistics task succeeded. Generator lookup against lazy framework routes failed and was corrected to actual request-model validation. macOS process command resolution initially prevented gateway stop; strict known framework interpreter handling fixed it. An interrupted mock startup caused four connection failures; restoring services and rerunning passed all four. PDF source changes require regeneration before final validation.

## Continuity

Current model milestone M3, next incomplete task M3.2 real semantic embedding qualification. Documentation stages 1–6 software are implemented; the dependency release blocker is resolved; remote publication requires an approved target workflow. NVIDIA/vLLM, training, live travel integrations and production qualification remain unverified. Repository is now `/Users/andrewgotora/Software Development/GitHub/onesa-ug/onesa-ai-platform`; the user-authorized obsolete directory was deleted while source, model, credentials and database volumes were preserved. Native inference and local portals use the new root. Main app and both portals remain running; isolated verification stacks are stopped with their data preserved after verification.

Remediation follow-up also tests Swagger Try it out/Execute and actual HTTP 200 response rendering, plus final scope rebuilds, classified PDF/diagram regeneration and negative public exposure validation. Exact audit and twelve-test summaries are stored with the internal verification records.
