# Onesa engineering and agent policies

This is the single policy file for `onesa-ai-platform`, including Codex/agent instructions,
contribution rules, security reporting and repository governance. Keep policies here;
do not recreate separate setup, implementation-status or session-handoff documents.
Read the README, current roadmap/release checklist, relevant architecture and existing
code before editing. Continue incomplete work; do not restart implemented features.
Update the changelog, contracts and affected operational documentation when behavior
changes. Record unverified functionality honestly in the applicable release checklist
or roadmap. Explicit user instructions and previously authorized scope take precedence.
Preserve local modifications, history and data; stage only reviewed paths.
Use free services only; do not provision paid resources or accept paid upgrades
without explicit budget authorization.

## Contribution rules

This repository is independently maintained within `onesa-ug`. Keep its frontend and
backend in their existing subdirectories. Do not initialize a workspace-level Git
repository, add sibling projects as submodules, or couple their release cycles.

Create a feature branch from `main`, make focused changes, and open a pull request.
Preserve work already staged or modified locally. Require one independent review;
use two reviews for authentication, personal data, infrastructure or robot actuation.
Describe the problem, resulting behavior, validation and deployment/rollback impact.
Update API contracts, migrations and documentation with behavior changes.

Run the commands in `docs/engineering/BUILD_AND_TEST.md` and
`python3 scripts/repository_hygiene.py` before staging. Inspect `git diff --cached`
and `git status --short`. Never stage private records, uploads, dumps, models or secrets.
Use synthetic fixtures; a private repository is not a secret store. Keep environment
examples as placeholders. New dependencies need provenance and license review.
Do not introduce a project license until ownership and licensing are approved.

Application builds and releases are independent. Changes to a shared contract must
remain compatible during separate rollouts. Production promotion, remote pushes and
visibility changes require explicit authorization. See `AGENTS.md` and
`docs/engineering/DEPLOYMENT.md`. Branch protections are recommendations until configured.

## Security policy

Supported software: the latest reviewed revision of `main`; no historical release
support promise is made before a release/support policy is approved.

Report vulnerabilities privately through GitHub's private vulnerability reporting
if enabled, or an organization owner using an existing private channel. Do not file
credentials, customer records, exploitation details or personal data in public issues.
A dedicated security contact and response targets must be assigned before production.

Do not store API credentials, production environment files, private corporate records,
model weights, database dumps or user uploads in Git or CI artifacts. Use a secret
manager and access-controlled storage. Separate frontend public configuration from
backend secrets. Local `.env` files must remain ignored; examples contain placeholders.
Use least-privilege database/service identities and protected production environments.

If a credential was committed, revoke/rotate it first, assess access and logs, and
notify the security owner privately. Ignoring or untracking a file does not remove
it from history. Remove it from future commits only after reviewing staged work;
historical removal requires a separately approved, coordinated remediation plan.
Never automatically rewrite history or force-push. Confidential documents already
in history block publication until an owner approves an appropriate remediation.

`python3 scripts/repository_hygiene.py --history` scans available reachable history,
staged content and publishable working files without printing matched values.
This heuristic cannot prove absence of secrets or confidential prose. Enable GitHub
secret scanning/push protection where the organization plan supports it, and conduct
human data-classification review before publishing or uploading CI artifacts.

## Repository governance

### Visibility and access

Recommend **private** for this repository while ownership, security and data review
are incomplete. Keep the company portal private even when its approved website is
public. Keep AI intellectual property, training provenance and robot control software
private until owners approve any public release. Assign least-privilege team access;
require organization 2FA and a named security/release owner. Do not change visibility
as part of local setup. Private GitHub storage does not authorize uploading records.

### Protect main

After the first approved push, target `main` with a ruleset: pull requests, one
independent approval (two for sensitive changes), dismiss stale approvals, resolved
review conversations and passing checks. Block force pushes and deletion. Restrict
bypass rights to audited emergency owners. Require reviews of workflow/infra/security
changes; assign real CODEOWNERS teams once membership is confirmed. Keep signed
commits as an organization policy decision. Select actual status checks after their
first execution; do not require nonexistent jobs. Avoid path-filtered required
checks that may remain pending. Protect release tags and the `production` environment
with reviewers and prevent self-approval. Availability depends on the GitHub plan.

Required checks: `publication-hygiene`, plus the application checks listed in
`docs/engineering/BUILD_AND_TEST.md`. Do not promote an artifact built from a different
revision or use secrets in untrusted fork pull requests. Image release workflows package candidates. Cloud deployments use the independently
selectable GitHub workflow documented in `docs/engineering/VERCEL_RENDER.md`.

Sources: [GitHub rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets),
[secret scanning availability](https://docs.github.com/en/code-security/how-tos/secure-your-secrets/detect-secret-leaks/enable-secret-scanning),
[GitHub CLI repository creation](https://cli.github.com/manual/gh_repo_create).


## AI-specific continuation and model boundaries

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

## Next.js frontend editing

For `onesa-ai-platform-frontend/apps/chat`, read the relevant version-matched guide
in that application's `node_modules/next/dist/docs/` before writing Next.js code.
APIs and conventions may differ from older releases; heed deprecation notices.
Root AGENTS.md replaces the generated nested policy. `agentRules: false` prevents
Next.js development tooling from recreating a second AGENTS.md.

Use `docs/product/ROADMAP.md` for pending milestones and
`docs/engineering/AI_CONFIGURATION_INVENTORY.md` for the verified provider inventory
and configuration/provisioning work. Preserve local Ollama, private environments and
user data. Free services only; no paid provisioning, training or additional model
downloads without explicit authorization. Hosted inference remains blocked until real
authenticated hosting and acceptance exist; never silently substitute mock inference.
