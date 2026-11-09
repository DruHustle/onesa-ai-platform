# Historical consolidated Docs workflow source

These exact files preserve newer Docs workflow logic that was stored at the root
of `DruHustle/onesa-ug`, outside the AI Platform product subtree. They are source
references, not active workflows or proof of a standalone release qualification.

Source commit: `0341f51dfc6bf41ee84bedb0dbac4de40f2725b5`.

| Original source path | Preserved reference | SHA-256 |
| --- | --- | --- |
| `.github/workflows/onesa-protected-docs-metadata.yml` | `onesa-protected-docs-metadata.yml.txt` | `bff551333f585a576bb15a5d660a7efb54ac16b87c820e10fda367b8195e01b5` |
| `.github/workflows/onesa-public-docs-build.yml` | `onesa-public-docs-build.yml.txt` | `f6eb9b9b577c75197bfb55c1f7ad78bf03e3f5e231da957980a02b05128aa514` |
| `scripts/ci/materialize_docs_source.py` | `materialize_docs_source.py.txt` | `b18a3d43c19f10f8d0cfe2972ed8e5fa3701d5aab15bfcabc45241322cbe5a7a` |

The metadata workflow and its verifier bind the original repository name, numeric
repository ID, root tree, product tree, workflow graph and owner custody. Moving
source does not rename an existing proof or authorize a different repository.
The public build's local-history materializer also requires the original pinned
Portal/Robot ancestry. These references deliberately retain those exact identities.

The standalone `.github/workflows/docs-hosting.yml` continues to own its existing
Docs build path. Before retiring a commissioned consolidated Docs controller,
move its private source/custody and establish fresh standalone qualification through
the existing owner controls. Preserve old journals and unresolved outcomes. No
workflow here carries provider credentials or deployment permission, and no historical
metadata is relabeled as accepted standalone evidence.

The complete original root workflow inputs and their history remain in the
restore-tested `onesa-ug` preservation bundle. This folder keeps the product-specific
Docs logic discoverable in its standalone home.
