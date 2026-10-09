# Documentation dependency security and compatibility

Updated 2026-10-09 · internal engineering · documentation 0.2.0.

## Finding and remediation

The original docs lockfile audit reported 33 affected dependency entries (29 high, 4 moderate). These were propagated from two root packages, rather than 33 distinct root vulnerabilities. Current upstream releases still have no published remediation for [braces GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm) and [sprintf-js GHSA-hp3w-g68c-fv3c](https://github.com/advisories/GHSA-hp3w-g68c-fv3c).

Repository-local, private backports implement the fixes under packages/security. These are explicitly named @onesa/braces 3.0.3-onesa.2 and @onesa/sprintf-js 1.1.3-onesa.2; they are not claimed to be upstream releases. Original MIT and BSD-3-Clause notices remain. There is no new project-wide license and no registry publication. Exact source diffs, source/archive hashes and portable tarballs are reviewable. The lockfile resolves every affected transitive consumer to these implementations. npm audit has no registered upstream advisory against local forks, so the audit result alone is insufficient: behavioral security and installed-source integrity tests are mandatory.

## Backport boundaries

braces retains upstream parsing/compilation/expansion APIs. The parser rejects nesting above 64 before recursive cleanup; compile, expand and stringify validate direct AST inputs iteratively. The validation bounds node count, rejects child cycles and permits legitimate parent/previous links. Hard bounds cannot be disabled with options. Exceeding them produces controlled ERR_BRACES_MAX_DEPTH or ERR_BRACES_MAX_NODES errors, rather than native stack exhaustion. Normal globs, escaping, ranges and upstream range limits remain supported.

sprintf-js retains sprintf/vsprintf, named arguments, flags and ordinary numeric formatting. Numeric precision saturates at 0–100 for e/f and 1–100 for g before native formatting; padding width saturates at 10000. Excessive specifiers produce bounded output instead of native precision/allocation failure. Per-call placeholder copies leave the parsed cache intact. These deliberate limits are recorded in the package README and tests.

## Supported runtime and peers

Documentation is qualified on Node 24.21.0. CI uses Node 24. A checksum-verified optional native runtime lives in ignored data/runtime/node24; install with `.venv/bin/python scripts/local/install_node24.py`. Make automatically prefers it when present, without modifying system executables. The official distribution and SHA-256 list come from nodejs.org; no system package installer is used.

The docs project uses React/React DOM 18.3.1, the supported intersection of Docusaurus and its Swagger dependencies, with matching TypeScript types. The separate Onesa Chat application retains its existing React version. Runtime and peer alignment remove the earlier unsupported engine/React dependency warnings.

## Reproduction and release checks

```bash
npm --prefix onesa-ai-platform-frontend/apps/docs ci
make docs-security-test
make docs-assets docs-public docs-internal
make docs-release-check
make docs-browser
```

Use Node 24 on PATH for direct npm commands, or the repository-local bin directory. The release gate runs all twelve adversarial/compatibility checks, validates installed source and tarball hashes, type-checks docs, verifies classified artifacts and runs an unsuppressed npm audit at all severities. CI enforces the same controls. Live browser verification exercises Swagger Try it out/Execute/response rendering in addition to search, PDFs, authorization, revocation, navigation and real assistant generation.

For a backport change, review the source/diff, increment its local version, regenerate exact patches, run `make docs-security-pack`, update direct tarball specs, reinstall and commit reviewed sources, archives, provenance and lockfile together. Changing a tarball under the same version risks cached installations; integrity tests intentionally reject stale files. Replace a backport with an official compatible fixed release only after these regressions and both scope builds pass. Never remove an advisory from the audit, spoof an upstream release, or mark a local fork safe based solely on a zero audit result.

The dependency blocker is resolved locally. Publication still requires an explicitly authorized target/workflow; this change publishes nothing. Semantic embedding, NVIDIA, provider and production qualification are separate outstanding milestones, not package-release failures.
