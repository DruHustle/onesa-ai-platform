# Onesa private deepmerge security backport

`@onesa/deepmerge` 4.3.1-onesa.2 is a local, unpublished fork of deepmerge 4.3.1
under its original MIT license. It is not an official upstream fixed release.
The exact official archive identity is in UPSTREAM.json; its original README and
license are retained. No install, build or publish scripts run in this package.

The demonstrated GHSA-gcqx-w48m-w2h4 / CVE-2026-93753 case changes a returned
object's prototype when a JSON `__proto__` property is copied from the source or
target, including null-prototype targets, null/primitive nested placeholders and
array elements. Both object-copy loops now skip this key before accessing its
value or assigning it. The same reviewed patch is applied to source, CommonJS
and UMD distributions; `security.patch` contains their exact diffs.

Ordinary own properties, symbols, cloning, array/custom merge behavior, TypeScript
declarations and existing inherited-property guards are preserved. This patch
never promises to sanitize a deliberately hostile custom merge implementation.
It does not remove or waive an advisory. The Docs all-severity audit, every
installed transitive consumer's byte identities, exploit regressions and real
Docusaurus/Swagger builds remain mandatory. A zero audit result alone cannot
verify this local fork. Replace it only after an official compatible fix passes
these checks. No registry publication or new project license is authorized.
