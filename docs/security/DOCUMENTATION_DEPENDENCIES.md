# Documentation dependency security and compatibility

## 28 October 2026 deepmerge backport

The mandatory all-severity Docs audit now reports
[GHSA-gcqx-w48m-w2h4](https://github.com/advisories/GHSA-gcqx-w48m-w2h4).
The official registry still supplies4.3.1 and no patched release. The reported
null-placeholder exploit was reproduced against that exact integrity-checked
package. A local, unpublished `@onesa/deepmerge`4.3.1-onesa.2 backport skips
`__proto__` in both object-copy loops before reading or assigning its value.
Source, CommonJS and UMD distributions carry the same focused change, derived
from the [reviewed upstream proposal](https://github.com/TehShrike/deepmerge/pull/274).
This is an Onesa patch, not an upstream-approved release. Original MIT attribution,
archive identity, exact diffs and portable package integrity are preserved.

Every SVGR and Swagger consumer must resolve the reviewed bytes. Regressions
exercise poisoned source/target objects, null-prototype targets, primitive nested
placeholders, arrays and getters, plus ordinary nested/symbol/custom merges in both
shipped distributions. Full Docusaurus builds and Swagger compatibility remain
required. The audit threshold and advisory checks are unchanged; a zero audit
report alone cannot establish the safety of a private fork. This source change
does not establish a hosted deployment or authorize publication.

Updated 2026-10-09 · internal engineering · documentation 0.2.0.

## Finding and remediation

The original docs lockfile audit reported 33 affected dependency entries (29 high, 4 moderate). These were propagated from two root packages, rather than 33 distinct root vulnerabilities. Current upstream releases still have no published remediation for [braces GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm) and [sprintf-js GHSA-hp3w-g68c-fv3c](https://github.com/advisories/GHSA-hp3w-g68c-fv3c).

Repository-local, private backports implement the fixes under packages/security. These are explicitly named @onesa/braces 3.0.3-onesa.2 and @onesa/sprintf-js 1.1.3-onesa.2; they are not claimed to be upstream releases. Original MIT and BSD-3-Clause notices remain. There is no new project-wide license and no registry publication. Exact source diffs, source/archive hashes and portable tarballs are reviewable. The lockfile resolves every affected transitive consumer to these implementations. npm audit has no registered upstream advisory against local forks, so the audit result alone is insufficient: behavioral security and installed-source integrity tests are mandatory.

## Backport boundaries

braces retains upstream parsing/compilation/expansion APIs. The parser rejects nesting above 64 before recursive cleanup; compile, expand and stringify validate direct AST inputs iteratively. The validation bounds node count, rejects child cycles and permits legitimate parent/previous links. Hard bounds cannot be disabled with options. Exceeding them produces controlled ERR_BRACES_MAX_DEPTH or ERR_BRACES_MAX_NODES errors, rather than native stack exhaustion. Normal globs, escaping, ranges and upstream range limits remain supported.

sprintf-js retains sprintf/vsprintf, named arguments, flags and ordinary numeric formatting. Numeric precision saturates at 0–100 for e/f and 1–100 for g before native formatting; padding width saturates at 10000. Excessive specifiers produce bounded output instead of native precision/allocation failure. Per-call placeholder copies leave the parsed cache intact. These deliberate limits are recorded in the package README and tests.

## Supported runtime and peers

Earlier documentation qualification used Node 24.21.0; new security candidates use Node 24.22.1. CI uses Node 24. A checksum-verified optional native runtime lives in ignored data/runtime/node24-24.22.1; install with `.venv/bin/python scripts/local/install_node24.py`. Make automatically prefers it when present, without modifying system executables. The official distribution and SHA-256 list come from nodejs.org; no system package installer is used.

The docs project uses React/React DOM 18.3.1, the supported intersection of Docusaurus and its Swagger dependencies, with matching TypeScript types. The separate Onesa Chat application retains its existing React version. Runtime and peer alignment remove the earlier unsupported engine/React dependency warnings.

## Reproduction and release checks

```bash
npm --prefix onesa-ai-platform-frontend/apps/docs ci
make docs-security-test
make docs-assets docs-public docs-internal
make docs-release-check
make docs-browser
```

Use Node 24 on PATH for direct npm commands, or the repository-local bin directory. The release gate runs the full adversarial/compatibility suite, validates installed source and tarball hashes, type-checks docs, verifies classified artifacts and runs an unsuppressed npm audit at all severities. CI enforces the same controls. Live browser verification exercises Swagger Try it out/Execute/response rendering in addition to search, PDFs, authorization, revocation, navigation and real assistant generation.

For a backport change, review the source/diff, increment its local version, regenerate exact patches, run `make docs-security-pack`, update direct tarball specs, reinstall and commit reviewed sources, archives, provenance and lockfile together. Changing a tarball under the same version risks cached installations; integrity tests intentionally reject stale files. Replace a backport with an official compatible fixed release only after these regressions and both scope builds pass. Never remove an advisory from the audit, spoof an upstream release, or mark a local fork safe based solely on a zero audit result.

The dependency blocker is resolved locally. Publication still requires an explicitly authorized target/workflow; this change publishes nothing. Semantic embedding, NVIDIA, provider and production qualification are separate outstanding milestones, not package-release failures.

## 24 October 2026 source patches

The Docs lock narrowly updates body-parser 1.20.9, Fast URI 3.1.9 and
serialize-javascript 7.1.3. The existing backports and unrelated locks are retained.
These dependencies participate in the build/dev toolchain; static hosting does not
run Express. A fixed lock does not establish a rebuilt or accepted hosted artifact.
Authoritative advisories: [body-parser](https://github.com/advisories/GHSA-27r3-jxmh-p828),
[Serialize JavaScript](https://github.com/advisories/GHSA-m5mm-p8h7-m29v).
Chat's development tooling resolves Zod 4.6.6 for
[GHSA-mrhx-c7xc-m3w5](https://github.com/advisories/GHSA-mrhx-c7xc-m3w5).
Full locked installs, behavioral backport checks, all-severity audits and final
runtime/artifact qualification remain separate required evidence.

The Node 24.22.1 runtime patch follows the [official 21 October security release](https://nodejs.org/en/blog/vulnerability/october-2026-security-releases), including the bundled Brotli decoder fix. OS Brotli in the separate file scanner is independently constrained to Alpine 1.2.1-r0 or later; a clean npm audit does not cover either native runtime.
