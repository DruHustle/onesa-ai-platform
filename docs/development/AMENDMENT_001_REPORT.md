# Amendment 001 completion report

Date: 2026-10-09. Applied in the existing onesa-ai-platform repository.

Historical amendment-session evidence below predates the explicitly authorized native
Ollama/Qwen3 installation. Current runtime/progress supersedes its no-download and
NVIDIA-only next-task statements; see [M2 report](MILESTONE_2_REPORT.md).

## Product and documentation

Onesa AI is positioned as European-based, general-purpose, modular infrastructure serving
European and international enterprise, developer, institutional and consumer applications.
Sovereign deployment, enterprise/industrial use cases and multi-domain customization are
explicit. African languages/regional knowledge remain optional international specializations.
The original engineering reference is retained with a supersession notice. No new official
brand asset, verified language capability, commercial success, certification or funding claim
was introduced. GDPR/EU AI Act considerations use official Commission references and separate
software controls from deployment, organizational and legal review.

## Architectural and working-code changes

- Training language-tag syntax replaces the en/sn/nd/mixed enum. Legacy records remain valid;
  optional free-form domains support industrial/enterprise and future specializations.
- Local immutable candidate metadata supports six proposed families, purpose, language/domain
  labels, license/provenance, not-deployed status and embedded evaluation/config hash evidence.
  These are candidate metadata, not trained/deployed profiles or a database promotion service.
- Optional paired unchanged-base evaluation reports per-language proxy regression with exact
  case alignment and no automatic promotion. Human general-assistant/domain review is required.
- English/German navigation/sign-in catalogs, configurable default and persisted preference
  establish the internationalization boundary. Other workspace/API text remains English;
  model output and routing are unchanged. German copy still needs broader linguistic review.
- Shared APIs/storage/knowledge/tools/travel already contain no country routing/validation
  whitelist. Document IDs select independent owner-scoped sets; stored named collections and
  typed metadata filters remain proposed work. Enterprise tools, organizational RBAC and
  industrial integrations require additional implementation and verification.

Public OpenAPI is byte-for-byte unchanged. No migration, repository reset, new per-profile
model server or milestone reordering occurred. The existing Qwen candidate is preserved.

## Files updated or added

| Area | Files |
| --- | --- |
| Repository/configuration | README.md, AGENTS.md, .env.example, compose.yaml |
| Training functionality | training/pipeline.py, training/registry.py, training/evaluate.py |
| Frontend functionality | onesa-ai-platform-frontend/apps/chat/src/lib/i18n.tsx, src/app/layout.tsx, src/app/page.tsx, src/app/globals.css, src/components/feature-shell.tsx |
| Regression tests | onesa-ai-platform-backend/tests/test_training.py, onesa-ai-platform-frontend/apps/chat/tests/chat.spec.ts |
| Product | docs/product/PRD.md, ROADMAP.md, MARKET_SCOPE.md, USE_CASES.md, EUROPEAN_MARKET_RELEVANCE.md |
| Architecture | docs/adr/0003-european-international-platform.md; docs/architecture/SYSTEM_ARCHITECTURE.md, COMPONENTS.md, DATA_FLOWS.md, DIAGRAMS.md, AI_SOVEREIGNTY.md |
| Models | docs/models/MODEL_SELECTION.md, MODEL_REGISTRY.md, MODEL_EVALUATION.md, MODEL_CUSTOMIZATION_STRATEGY.md, MODEL_CARD_TEMPLATE.md |
| Training documentation | docs/training/DATASET_STRATEGY.md, DATASET_FORMAT.md, FINE_TUNING.md, EVALUATION.md, MODEL_RELEASE.md |
| Supporting contracts/operations | docs/api/API_REFERENCE.md, docs/design/FRONTEND_DESIGN.md, docs/security/PRIVACY_AND_DATA_PROTECTION.md, docs/deployment/PRODUCTION_DEPLOYMENT.md, LOCAL_DEVELOPMENT.md, docs/testing/TEST_CASES.md |
| Continuation/evidence | docs/README.md; docs/development/AMENDMENT_001.md, ENGINEERING_REFERENCE.md, IMPLEMENTATION_STATUS.md, SESSION_HANDOFF.md, CHANGELOG.md, AMENDMENT_001_REPORT.md |

Folder-relative names in each row belong to its stated directory. OpenAPI was regenerated
for verification but is unchanged. Ignored data/amendment-001 contains current hardware and
model-precondition observations; screenshots remain under data/screenshots/.

## Verification results

- Full real PostgreSQL suite: **47 passed**. New tests cover extensible/legacy languages,
  domain metadata, base regression and proposed profiles remaining undeployed.
- Ordinary checks: Ruff lint/format and strict mypy passed; **27 passed, 20 PostgreSQL
  tests skipped** without an integration URL. One upstream TestClient deprecation warning.
- Frontend lint/type/production build: passed. Node 24 Compose rebuild/start/readiness:
  passed, with persistent application data preserved.
- **4 Chromium tests passed**: original chat, document/tool/travel, mobile flows and
  new locale selection/reload persistence/reset. Local UI remains http://localhost:3100.
- Historical pre-amendment prepared dataset still verifies. Public OpenAPI reproduced
  identical bytes; relative documentation links resolve. Dependency graphs unchanged.
- M2 diagnostics rerun: macOS ARM64, no NVIDIA tooling/PyTorch and no configured vLLM
  endpoint. Real model probe correctly requires an already-running private server.
  No model download, actual inference/training, remote CI or external deployment occurred.

## Current milestone, next task and remaining work

**M2.3: foundation-model acceptance on a compatible NVIDIA host** remains the first
incomplete task. Continue existing diagnostics/GPU configuration there and record actual
loading, generation/cancellation, memory and performance before specialization.

Subsequent qualification remains actual semantic embeddings/travel providers; general-assistant
and multilingual/domain datasets/evaluation; reviewed CUDA lock and real adapters; complete
interface translations; organizational collections/RBAC/workflows where required; multimodal
adapters; and production residency/TLS/security/load/data-lifecycle/monitoring qualification.
No invented legal, funding, linguistic or production acceptance is recorded.
