# API contract generator dependencies

These locked development tools generate the versioned client from the repository's
`docs/api/openapi.json`. They are separate from the backend and Chat runtime images.
Use Node 24 and install with `npm ci --ignore-scripts --prefix scripts/contract-tools`.

The exact `@redocly/openapi-core@1.34.20` dependency of `openapi-typescript@7.13.0`
receives a scoped callable adapter for upstream `minimatch@11.0.1`, which addresses
[GHSA-g3hv-75wg-m249](https://github.com/advisories/GHSA-g3hv-75wg-m249).
Redocly's installed `lib/utils.js` calls `require('minimatch')(url, pattern)` when
selecting configured HTTP headers. The adapter preserves that call shape without
changing the upstream matcher or downgrading the generator.

The archive is copied byte for byte from the existing reviewed Docs/owner-tool
adapter and is included in `packages/security/provenance.json`. Its packaged README
describes the two consumers reviewed when that archive was created; this directory
records the additional, separately tested Redocly use. No packaged source, license,
integrity or existing consumer override changes. Remove this override when a reviewed
compatible upstream generator dependency supports the fixed matcher directly.

After installation, run:

```sh
node scripts/contract-tools/matcher-security.test.cjs
python3 scripts/ci/npm_audit.py --prefix scripts/contract-tools
make api-client contract-check
git diff --exit-code -- docs/api/openapi.json onesa-ai-platform-frontend/packages/api-client/
```

The matcher tests check installed provenance, ordinary glob syntax, actual Redocly
header selection with synthetic responses, and bounded adverse pattern growth in
an isolated worker. They make no HTTP requests. The generator checks require the
usual locked backend environment and must leave generated OpenAPI and client bytes
unchanged. These local checks do not establish hosted acceptance.
