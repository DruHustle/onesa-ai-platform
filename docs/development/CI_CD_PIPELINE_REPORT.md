# CI/CD pipeline implementation and audit — onesa-ai-platform

Current policy update: 2026-10-14 — dev, staging and main remain the three permanent branches. Temporary Dependabot security-fix PRs and reviewed security release candidates are explicitly permitted. Ordinary version-update PR creation stays at open-pull-requests-limit:0; alerts, scans, notifications and weekly full CI remain. The earlier security-fix OFF setting is superseded: current owner-authorized API readback verifies all three repositories enabled:true and paused:false, alerts enabled and zero open alerts. Owner notifications are separately owner-confirmed. Dependency-graph SBOM readback returned 404 and remains unverified; unrelated settings were preserved. Protected coordinator evidence records the scoped receipt. Reviewed security fixes normally flow through dev → staging → main. An urgent candidate may start from exact current production plus reviewed fixes, excluding unfinished dev, qualify in existing isolated staging, receive the owner-controlled release decision and reconcile into dev/staging. There is no new permanent environment, blind auto-merge, production credential exposure to bot PRs or relaxed trigger trust. Temporary cleanup requires verified incorporation and evidence-dependency checks. Historical inventory below does not establish current provider state.

## Historical audit — 2026-10-11

Audit date: 2026-10-11. Prepared locally on `feature/cicd-review-optimization`; no
remote push, merge, provider setting change or live deployment occurred. The explicitly
authorized Dependabot security-update PR setting was enabled and read back on all three
repositories; all other remote settings remain unchanged. This report supersedes
manual-only qualification/feature-push details in earlier safeguard reports while
preserving their production custody boundary.

## Verified state and workflow inventory

Requested operating model: private GitHub Free. Actual readback: **public**, default
branch main, authenticated owner admin/write, no registered self-hosted runners.
The account plan is unavailable, main has no active classic protection/rulesets and
production environments have no required reviewers. The remote Actions default token
is write and PR-approval permission is enabled; each prepared workflow overrides to
least privilege. No supported paid/private protection was assumed.

Existing local workflow count: **14**; final local count:
**15**. Before remotely installed count:
**8**. Added one reusable
static-review workflow; no old workflow was deleted before remote replacement success.
Platform preserves distinct compose/browser/TLS and independent runtime-image verification; these are not equivalent redundant checks. Makefile dependency installs now enforce committed hashes.

`PIPELINE_AUDIT_BEFORE.json` contains every original trigger, runner, permission,
secret **name**, command, target/environment and sampled history. `PIPELINE_AUDIT_AFTER.json`
contains the exact final local configuration including all job commands. These are
sanitized inventories, not secret values. Detailed owner-only usage records live under
ignored `docs/internal/release-audit/cicd/`; they must not be published as app docs.

Sample: last 100 remote runs across workflows, not the whole history. Completed/failure
counts and mean elapsed seconds include historical configuration; elapsed is not
billed runner minutes. Empty entries are not proof a workflow is broken or unused.

| Workflow | Final triggers | Runner | Before sample: completed / failed / mean seconds | Purpose / usefulness |
| --- | --- | --- | --- | --- |
| `_local-validation.yml` | workflow_call | ['self-hosted', 'Linux', 'ARM64', 'onesa-platform-local'] | No runs in sample | Dormant private-only local runner; no active CI caller; retain until hosted replacement is verified remotely |
| `_pipeline-review.yml` | workflow_call | ubuntu-latest | No runs in sample | Reusable blocking offline workflow/secret scan, local annotations and pipeline regressions |
| `ci.yml` | push, pull_request, workflow_dispatch | reusable, ubuntu-latest | 37 / 5 / 412.6 | Product CI, relevant PR selection and mandatory summary; full checks on release-source pushes |
| `deploy.yml` | workflow_dispatch | ubuntu-latest | No runs in sample | Retained manual native-protection deployment; private production jobs excluded; no push trigger |
| `docs-hosting.yml` | workflow_dispatch | ubuntu-latest | 2 / 0 / 352.0 | Retained native-protected docs publication; private credentials excluded; no second application deploy authority |
| `free-authorization.yml` | workflow_dispatch | ubuntu-latest | No runs in sample | Manual owner approval/revocation binding exact evidence digest; no deployment or provider keys |
| `free-qualification.yml` | workflow_dispatch, workflow_run | ubuntu-latest | No runs in sample | Automatically derive exact-commit CI/build/staging evidence; owner dispatch fallback; no provider keys |
| `inspect-hosting.yml` | workflow_dispatch | ubuntu-latest | 7 / 0 / 23.1 | Retained owner diagnostic; production credentials excluded on private-Free |
| `release-build.yml` | workflow_dispatch | ubuntu-latest | No runs in sample | Retained qualified production packaging; credentials/build excluded on private-Free |
| `release-images.yml` | workflow_dispatch | ubuntu-latest | No runs in sample | Manual Platform image packaging; no automatic registry publication/production push |
| `release-qualification.yml` | workflow_dispatch | ubuntu-latest | No runs in sample | Retained supported-native-protection qualification path; manual only; private-Free uses free-qualification |
| `release-review.yml` | workflow_dispatch | ubuntu-latest | No runs in sample | Retained manual native-protection owner review; no independent reviewer invented |
| `release-staging.yml` | workflow_dispatch, workflow_run | ubuntu-latest | No runs in sample | Single scoped Actions staging authority; automatic mode private-only, owner-only and opt-in |
| `repair-hosting.yml` | workflow_dispatch | ubuntu-latest | 18 / 4 / 191.7 | Retained bounded manual repair; production credentials excluded on private-Free; no automatic destructive repair |
| `repository-hygiene.yml` | push, pull_request, workflow_dispatch | ubuntu-latest | 36 / 4 / 13.9 | Independent publication/history hygiene gate; all relevant PRs and release-source pushes |

## Shared implementation status

| Repository | Frontend CI | Backend CI | Automated review | Staging | Qualification | Production release | Monitoring | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Company Portal | Next.js lint/types/build/browser/contracts | Node tests/DB/contracts/image/startup | Read-only annotations + blocking scans | Scoped manual + opt-in auto; not deployed | Exact technical artifact + owner reviews | External owner handoff; blocked pending controls | Receipt/probes configured; live not run | Local implementation; owner activation pending |
| AI Platform | Next.js lint/types/build/browser/docs/TLS/contracts | Python tests/DB/pgvector/API/image/startup | Read-only annotations + blocking scans | Scoped manual + opt-in auto; not deployed | Exact technical artifact; hosted model/operations required | External owner handoff; blocked pending controls | Receipt/probes configured; live not run | Local implementation; owner activation pending |
| AI Robot | Static interface/proxy/types/browser/contracts | Cloud API/simulation/safety/image/startup | Read-only annotations + blocking scans | Scoped manual + opt-in auto; not deployed | Cloud-only technical artifact; hardware excluded | External owner handoff; physical separate | Manual staging monitor + receipt; live not run | Local implementation; durable storage/owner pending |


## Usage, runners and measured efficiency

Three successful historical CI runs yielded rounded job-runtime slot sums of
**30, 30, 31 minutes** (mean
**30.3**). Heavy jobs in the newest sample: documentation 527s, browser 392s, tls-acceptance 310s.
These historical public-repository timings do not measure the new local pipeline,
GitHub private billing or the stopped local VM. A transparent planning estimate is
`monthly full-run equivalents × 30.3` minutes, plus hygiene/staging/security and
actual scheduling overhead. For example 20 full-run equivalents would yield
**606.7 historical CI slot minutes**, before added review/summary overhead and
before savings; this is a scenario, not a forecast of actual monthly usage. There is
no verified private-month usage or monetary estimate because the billing endpoint is
unavailable to the token. Do not extend OAuth permissions automatically.

Observed unexpired artifact bytes: **29,489,474**,
57 total artifact records (complete readback).
Cache bytes: **2,087,805,396**,
10 active caches. These byte counts are
API snapshots, not billable-storage accounting. Portal's historical artifact bytes
already exceed the hypothetical private-Free 500 MB allowance; review retention
before migration, without deleting evidence blindly.

Current published Free limits: 2,000 monthly Actions minutes and 500 MB artifact
storage per owner/account allowance, 10 GB cache per repository. Do not multiply the
owner's minute allowance by three repositories. Keep new review/diagnostic artifacts
three days and release receipts seven days; old large artifacts are unchanged. The historical audit proposed monthly version updates; current ordinary version PR
creation is limit 0. Retain security fixes, on-demand packaging, PR cancellation and measured
usage alerts/budget-stop settings. Removing feature push duplication saves one full
CI invocation per feature push that also produces a PR run; numeric time/percentage
savings for the new pipeline require authorized remote runs and are not claimed.

No repository runner is registered. The existing local Lima VM `onesa-portal-ci` is
stopped (ARM64, four CPUs, 6 GiB RAM, 60 GiB disk). Its persistent shared Docker and
lease state are not verified as an ephemeral untrusted-PR sandbox. It was not started,
registered or exposed. Hosted Ubuntu is the safe current execution path. Before any
future trusted-only local use: independently isolate identities/networks/storage,
clean workspace and caches between jobs, deny production credentials and untrusted
PR execution, enforce lease/resource limits, and provide explicit hosted fallback
rather than queueing critical checks indefinitely on an offline runner.

## Historical checks, findings and credential gaps — 2026-10-11

Pipeline release regression suites and real-tool negative tests run locally; exact
final counts and application validation are recorded in the final commit report.
All workflow syntax checks pass. Zizmor has **zero blocking** findings and
**5 Low advisory** findings, with the two documented trigger exceptions.
Gitleaks has zero unresolved publishable-source matches. Existing full application
browser/DB/image/ROS suites remain required in CI; they are not claimed as freshly
executed live provider acceptance by these local tests. Platform local non-DB tests
skip database cases without an isolated test DB; that is not complete DB qualification.

Platform's Gitleaks scan initially reported three generic-api-key matches in the
production-deployment guide and rollback Compose override. A local value comparison
confirmed all captured secrets were exactly `pre-split-20261009`, a public local-image
tag suffix. `.gitleaks.toml` permits only this exact captured value AND these two paths,
retaining all default rules. It does not ignore directories, high findings or arbitrary
tokens. Other repository scanners and human publication review remain mandatory.

Missing staging Actions secret names from remote inventory:

- `STAGING_FIXTURES_JSON`
- `STAGING_MIGRATION_DATABASE_URL`
- `STAGING_RENDER_API_KEY`
- `STAGING_RENDER_SERVICE_ID`
- `STAGING_VERCEL_AUTOMATION_BYPASS_SECRET`
- `STAGING_VERCEL_ORG_ID`
- `STAGING_VERCEL_PROJECT_ID`
- `STAGING_VERCEL_TOKEN`

Names are not values. Existing production/shared repository secrets still require
owner migration/rotation. Provider credentials are unavailable in this process/local
environment files, so fresh authenticated project/service configuration and token
scope readback could not be completed. Existing provider settings, free service limits,
real alert delivery, hosted inference and durable Robot storage remain owner checks.
**No staging or production deployment/monitoring was executed.** Synthetic fixture
passes and local builds do not change that status.

## Current operating instructions

The active [CI/CD runbook](../engineering/CI_CD.md) supersedes the duplicated
11 October operating instructions. It defines dev → staging → main, the temporary
security-update exception, ordinary version PR limit 0, exact-source qualification
and external credential custody. The inventory and validation below remain dated
audit evidence, not a current provider state or deployment claim.

## Final local validation and exact changed files

`PIPELINE_VALIDATION.json` records command results and sanitized diagnostic summaries.
Release regression tests: 43 passed; pipeline real-tool negative tests: 17 passed.
Workflow syntax/security and history/publication hygiene pass. No provider call occurs
in the failed-CI handoff demonstration; this does not prevent the underlying Git push.

Application checks: backend mypy and Ruff checks, 87 backend tests passed with 73 DB-dependent skips, frontend lint/types/production build and proxy boundary test passed. Documentation validation also passed after refreshing ignored provenance/PDF assets, including 2 source-policy and 13 security tests. Tests use the backend directory configuration; a root-directory mypy invocation is not the supported check.

The following files are changed in this local implementation. Ignored restricted
owner evidence is excluded. All changes are on feature/cicd-review-optimization;
commit IDs are reported in the task response; the commits also include the preceding
private-Free safeguards through their branch ancestry. No branch was pushed or PR opened.

- `.github/dependabot.yml`
- `.github/workflows/_local-validation.yml`
- `.github/workflows/_pipeline-review.yml`
- `.github/workflows/ci.yml`
- `.github/workflows/deploy.yml`
- `.github/workflows/docs-hosting.yml`
- `.github/workflows/free-authorization.yml`
- `.github/workflows/free-qualification.yml`
- `.github/workflows/inspect-hosting.yml`
- `.github/workflows/release-build.yml`
- `.github/workflows/release-images.yml`
- `.github/workflows/release-qualification.yml`
- `.github/workflows/release-review.yml`
- `.github/workflows/release-staging.yml`
- `.github/workflows/repair-hosting.yml`
- `.github/workflows/repository-hygiene.yml`
- `.gitleaks.toml`
- `AGENTS.md`
- `Makefile`
- `README.md`
- `docs/development/CHANGELOG.md`
- `docs/development/CI_CD_PIPELINE_REPORT.md`
- `docs/development/FREE_GITHUB_PLAN.md`
- `docs/development/PIPELINE_AUDIT_AFTER.json`
- `docs/development/PIPELINE_AUDIT_BEFORE.json`
- `docs/development/PIPELINE_VALIDATION.json`
- `docs/development/PRIVATE_FREE_SAFEGUARDS.md`
- `docs/engineering/BUILD_AND_TEST.md`
- `docs/engineering/CI_CD.md`
- `onesa-ai-platform-backend/Makefile`
- `scripts/ci/analyze.py`
- `scripts/ci/install_tools.py`
- `scripts/ci/paths.py`
- `scripts/ci/security.py`
- `scripts/ci/summary.py`
- `scripts/ci/test_pipeline.py`
- `scripts/ci/tools.lock.json`
- `scripts/release/evidence.py`
- `scripts/release/free_gate.py`
- `scripts/release/hosted.py`
- `scripts/release/test_free_gate.py`
- `scripts/release/test_free_workflow_policy.py`

### Authorized push review — 2026-10-11

Generated development-lockfile hashes for all 81 already-pinned packages. A clean dependency calculation validates hashes instead of relying on an existing local environment; no package versions changed.

GitHub pull-request validation found and prompted this correction before any authorized deployment. Production/staging provider prerequisites and owner approvals remain separately required.


## Initial staging workflow registration — 2026-10-12

GitHub refused release-staging.yml dispatch while that new file existed only on dev
and staging. Use the existing registered entry point before main installation:
`gh workflow run deploy.yml --ref staging -f target=staging`.
The entry point calls the same release-staging.yml at the dispatch source revision,
uses the called job's Staging environment, and passes only an explicit allowlist of STAGING secret names.
Manual staging provenance accepts only those two known workflow paths on staging,
with exact source and owner checks; all original CI, target/database isolation and
hosted acceptance gates remain mandatory. Production jobs require target=production
on main plus the existing authorization. No default-branch or production promotion
is needed merely to dispatch staging. The bootstrap caller is for the currently public
repository; normal release-staging dispatch remains available after main installation.

Corrected public production jobs use their production provider secret names, while
release-staging keeps STAGING names. A name alone does not prove provider least
privilege; remote rotation/isolation and private production credential custody remain
owner acceptance requirements. No production environment values were changed.


The reusable staging caller must forward every used STAGING secret by name, even when
its value exists only in the called Staging environment. The called workflow declares
those names required; value/target validation still occurs before deployment. No
production credential names or blanket secrets: inherit are passed. GitHub silently
resolved unpassed names to empty strings in the first runtime preflight; source tests
now compare used, declared and forwarded names to prevent that mismatch. See
[GitHub reusable workflow secrets](https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows).


Hosted preflight failures now emit only fixed diagnostic codes (for example RENDER_ACCESS,
STAGING_DATABASE_BINDING or STAGING_INFERENCE_CONFIGURATION). Unknown errors keep a
generic code; private values/URLs/responses/exception strings are never emitted. This
identifies the owner's exact failed requirement without relaxing a release gate.


Staging uploads its receipt before the final hosted acceptance requirement. The final
step now fails for FAIL/BLOCKED/incomplete results, including a false PASS paired with
nonpassing checks. Provider deployment success remains separately recorded; a green
workflow cannot conceal authentication, readiness, inference or storage failures.
