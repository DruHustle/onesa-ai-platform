# Onesa local sprintf-js security backport

Private compatible fork of upstream sprintf-js 1.1.3; original BSD-3-Clause license/copyright retained. This is not an upstream release. Advisory: https://github.com/advisories/GHSA-hp3w-g68c-fv3c.

Numeric precision is saturated at the modern ECMAScript native bounds: 0–100 for e/f and 1–100 for g. Excessive width is saturated at 10000 before padding allocation. Normal formatting within those limits is unchanged. Excessive specifiers produce bounded output rather than an uncaught native RangeError. A per-call placeholder copy leaves the parsed cache untouched. The public sprintf/vsprintf exports, named arguments, flags and valid formatting remain upstream implementations.

security.patch records the exact modification. Adversarial and argparse/Remarkable compatibility tests are required by the release gate. The scoped name identifies the locally changed implementation; npm audit alone cannot verify it. Remove the override when an upstream compatible fixed release passes the same tests.
