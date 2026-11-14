# AI sovereignty and deployment control

Implemented: portable Python/Next.js/PostgreSQL containers; configurable private model and
embedding endpoints; revision-pinned open-weight serving profile; adapter substitution behind
stable APIs; private application/inference separation; local storage and owner-scoped access.
These let an operator select European-owned/European-hosted infrastructure or another approved
location without geographic forks. No European production host is deployed or verified here.

Residency is configured by choosing application, database/volume, backup, inference/embedding
hosts and all future providers in the required locations. Record provider legal ownership,
subprocessors, support access, key custody and network paths separately. URLs alone do not
prove residency. Compose has no automated geofencing, egress enforcement or residency audit.
Keep private network endpoints, access controls and sensitive backup retention under operator control.

GPU profile startup can contact registries/model hosting to obtain images/weights. Prestage
reviewed artifacts and qualify an offline image/model/embedding supply chain when independence
requires it. Browser/provider/telemetry/dependency paths also need explicit egress review; no
air-gap claim is made. Independent infrastructure still depends on hardware and open-source
components with license and lifecycle obligations.

Software evidence covers auth/CSRF/ownership, source/run records, safe request logs and artifact
hashes. Comprehensive audit trails, enterprise tenancy/RBAC, data lifecycle and production
monitoring remain work. Self-hosting is an architectural control, not automatic GDPR/EU AI Act
compliance. See security/PRIVACY_AND_DATA_PROTECTION.md for organizational/legal boundaries.
