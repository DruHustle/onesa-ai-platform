# Onesa AI continuation workflow

At the beginning of every development session, follow this prompt:

> Read docs/development/IMPLEMENTATION_STATUS.md, docs/development/SESSION_HANDOFF.md, the architecture documents, and the existing code. Identify the first incomplete task in the current milestone. Continue implementing it, run the relevant tests, update the documentation, and record the results. Do not restart the project or rewrite completed components unnecessarily.

Use the ordered task list in IMPLEMENTATION_STATUS.md as the source of progress.
If a milestone is complete, advance to the first task in the next milestone.
Preserve working components. Update status, handoff, changelog, API contracts, and
affected architecture documentation before ending a session. Record failures and
unverified integrations explicitly.

Keep this repository named `onesa-ai-platform`. The supplied engineering document
and screenshots are design references; they do not authorize deployment, remote
publishing, expensive training, large model downloads, or actions outside this repo.
Use FastAPI/Python, Next.js/TypeScript, PostgreSQL/pgvector, and configurable local
vLLM inference. Begin with a deterministic mock; do not label it real AI.
Do not add robotics dependencies to the core or start Phase B training before
Phase A's application and evaluation foundations exist.

Do not add a project license without an ownership/license decision. Never commit
secrets. Use official framework/model documentation when verifying compatibility.
Only create modules and documentation needed by implemented or explicitly designed
features; label planned features clearly.

Amendment 001 (docs/development/AMENDMENT_001.md) governs current product positioning:
Onesa AI is European-based, general-purpose and globally applicable. Enterprise,
industrial, developer, institutional and consumer applications share common infrastructure.
African languages/regions remain optional international specializations. Preserve the
milestone order and public contracts. Dataset languages/domains must stay extensible;
proposed model-family metadata must never be presented as trained/deployed models.
Interface catalogs do not establish model-language quality. Do not claim funding eligibility,
certification or regulatory compliance without deployment-specific verified evidence.

Milestone 2 Apple Silicon request (docs/development/MILESTONE_2_REQUEST.md) explicitly
authorized native Ollama and the initial Qwen3 4B download after hardware verification.
Keep mock/ollama/vllm interchangeable, preserve port 3100/data, use native loopback serving
and Docker Desktop host routing, and retain NVIDIA as an unverified future deployment option.
Do not download comparison models or start fine-tuning without a corresponding request.
