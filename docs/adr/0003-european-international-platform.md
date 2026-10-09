# ADR 0003 — European-based general-purpose platform

Date: 2026-10-09. Status: accepted under user-requested Amendment 001.

## Context

The original engineering reference prioritized African-language/regional Phase B adaptation.
Amendment 001 supersedes that positioning while retaining the working platform, stack,
Phase A/Phase B strategy and milestone order. Training Example.language actually enforced
four labels; candidate registry metadata lacked generalized purpose/family/coverage.

## Decision

Position Onesa AI as European-based infrastructure for European and international enterprise,
industrial, developer, institutional and consumer applications. African languages, including
Shona/Ndebele, remain optional specialization areas. Preserve Qwen as the configurable initial
general-purpose candidate and the stable default API alias.

Replace the dataset's language enum with bounded, normalized language-tag syntax and optional
free-form domain labels. Existing en/sn/nd/mixed records remain valid. Extend immutable local
candidate records with logical family, purpose, languages/domains, license/provenance,
not-deployed status, evaluation contents and report/config hashes. Add paired evaluation
against unchanged base predictions; no automatic promotion or linguistic-quality claim.

Separate interface catalogs/preferences from model coverage. English remains default; German
navigation/sign-in translations are available with other text still English. Add catalogs
incrementally after review. No geographic model routing or country whitelist exists.

## Consequences

No database migration, serving deployment multiplication, endpoint rename or breaking public
API change is needed. Existing owned document_ids identify independent knowledge sets; stored
named collections/metadata filters remain proposed extensions, not delivered enterprise tenancy.
Tools/permissions stay market-independent; enterprise/industrial tools and travel providers
require actual integrations. Vision/speech remain future capabilities.

Metadata describes a candidate's intended specialization, not verified coverage. Actual release
needs baseline regression, license/provenance review and target-GPU evidence. EU hosting is an
operator choice; self-hosting does not discharge organizational/legal responsibilities. Funding
and certification claims require separate verification. M2.3 remains the next engineering task.

Subsequent implementation note (2026-10-09): the explicit Apple Silicon M2 request
completed real Qwen3 acceptance with native Ollama. NVIDIA remains a separate deployment
qualification; the current ordered status advances to M3 semantic embeddings. This
changes serving acceptance evidence without changing this positioning decision.
