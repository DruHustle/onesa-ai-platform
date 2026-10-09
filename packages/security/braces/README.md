# Onesa local braces security backport

Private compatible fork of upstream braces 3.0.3, retained MIT license/copyright. This is not an upstream release. Advisory: https://github.com/advisories/GHSA-vfj7-8cjw-p6xm.

The parser rejects nesting above 64 before any recursive cleanup. Compile, expand and stringify validate direct AST inputs iteratively, bounding depth/nodes and rejecting child cycles while permitting normal parent/prev back-links. Limits are hard bounds and cannot be disabled through caller options. Ordinary glob patterns, ranges, escaping and public module APIs remain upstream implementations. Controlled errors use ERR_BRACES_MAX_DEPTH / ERR_BRACES_MAX_NODES.

security.patch records changes to the upstream files; lib/depth.js is the added guard. The scoped package name identifies a genuinely changed local implementation; audit does not establish this fork's safety. Required adversarial and compatibility tests live in scripts/docs/security.test.cjs. Remove this override when a compatible upstream release fixes all tested entry points.
