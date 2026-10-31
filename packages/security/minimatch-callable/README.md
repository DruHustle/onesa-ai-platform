# Scoped minimatch callable adapter

This private adapter exports the callable `minimatch` function from the exact
upstream `minimatch@11.0.1` package. It contains no legacy matcher implementation
and does not claim to be an upstream release or a complete minimatch 3 API shim.
Only `serve-handler@6.1.7` and `@ts-morph/common@0.11.1`, whose installed code calls
`require('minimatch')(path, pattern)`, receive this override. Modern consumers
receive upstream minimatch directly.

The upstream release addresses
<https://github.com/isaacs/minimatch/security/advisories/GHSA-g3hv-75wg-m249>.
Its nonrecursive matcher and bounded pattern preprocessing are retained unchanged.
The dependency alias avoids self-resolution when this adapter is installed under
the legacy `minimatch` dependency name. Both lockfiles record the real upstream
archive and integrity. `UPSTREAM.json` records its provenance and
`UPSTREAM_LICENSE.md` preserves the upstream Blue Oak license; this adapter grants
no new license to other Onesa source.

The repository's package provenance records every source file, shipped file and
archive hash, including the identical copy in the isolated owner tool image.
Required installed-artifact regressions exercise documentation serving, Swagger
file allowlists, TypeScript project glob selection, owner file tracing, ordinary
glob syntax and adversarial pattern growth. Audit thresholds remain unchanged.
Remove the adapter when these two consumers support a fixed upstream callable
or named-export release directly.
