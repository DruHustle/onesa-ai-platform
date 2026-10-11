# Public and engineering documentation access

This public portal includes reviewed product guides, high-level architecture, public integration contracts, tutorials and approved manuals. Search and downloads use the same classification allowlist. API explorers are read-only on the static public host; they do not send credentials to production.

## Internal engineering experience

Detailed implementation schemas, administrative APIs, infrastructure configuration, incident procedures and restricted engineering PDFs are built separately. The existing gateway requires an active Onesa AI session with engineering allowlist permission on every page, index, script, diagram and PDF. Sign out revokes access; identity service failure denies access. Internal assets must never be served by this public Vercel project.

The AI application's Engineering docs link can be enabled only with an approved authenticated internal origin. An independently protected internal hosting target and cross-origin identity design still need hosted acceptance. No internal hostname or synthetic login credential is published here. Until that deployment exists, use the authorized local engineering gateway and repository build guide. This public site deliberately does not offer a link to an invented live internal service.

## Source and release traceability

Approved public sources, API schemas and rendered artifacts are generated from reviewed source revisions. Manuals contain classification, version, generation date and checksums. Documentation versions identify the reference build, not a product production-release verdict. [Downloads](/downloads), [architecture](/architecture) and the API explorer expose approved assets only.

## Repository source boundary

The current repositories are public. Software design and schema source references
in those repositories can be read independently of the protected engineering build.
Gateway access controls protect the hosted pages and generated downloads; they do
not make Git source private. Confidential records, incident evidence, credentials
and user documents must stay out of public source and public documentation.
