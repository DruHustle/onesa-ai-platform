# Privacy and data protection

PostgreSQL stores account identifiers, password/session hashes, private messages and
sources, extracted documents/vectors, tool goals/outcomes and structured trips. Operational
logs omit content and tokens. All content retrieval is owner-scoped. Conversation deletion
cascades its messages/runs; document deletion cascades indexed chunks. Previously persisted
chat answers/source excerpts remain conversation history until that conversation is deleted.

There is no automatic training export/use of private user conversations. Training input must
carry provenance, license, consent, review and an explicit training approval. Regex PII
screening is a limited aid, not anonymization or legal validation. Toy examples are not
approved datasets, and no linguistic ground truth for Shona/Ndebele has been invented.

Retention periods, account export/deletion workflows, legal jurisdiction, privacy notices,
object storage policy and encrypted backup retention must be selected by the operator.
No regulatory certification or full legal compliance is claimed.

## European deployment and organizational responsibilities

An operator can select European application/database/backup/model/embedding hosts using the
existing storage/network/endpoint configuration. Record actual locations, provider ownership,
support access and subprocessors; review every external provider and transfer. No residency
geofencing, European production deployment or self-hosting compliance guarantee is implemented.

Choose controller/processor responsibilities, permitted purposes and lawful bases, notices,
contracts, rights handling, retention/deletion/export and risk assessment for the actual
processing. The Commission describes these role-dependent responsibilities in its
[GDPR application guidance](https://commission.europa.eu/law/law-topic/data-protection/information-business-and-organisations/application-gdpr_en).
These are deployment/organizational obligations alongside, rather than satisfied by, software controls.

Assess EU AI Act applicability for each actual model/application, provider/deployer role and
intended use. Record required transparency, oversight, documentation and risk controls through
qualified review of current rules; the Commission's
[AI Act framework](https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai)
is the starting source. No classification, certification or blanket compliance determination is
claimed here. Review current requirements before release; do not infer exemptions from SME
size, open weights, a European location or self-hosting.

Implemented evidence includes auth/ownership, deletion of selected conversations/documents,
source/run records, safe correlation logs and candidate provenance/evaluation hashes. Full
account erasure/export, policy-based retention (including backups/source copies), enterprise
RBAC/audit, production access/monitoring and incident procedures still need qualification.
