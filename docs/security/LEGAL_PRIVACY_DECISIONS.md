# Legal and privacy decisions before publication

Publication is blocked pending company management and qualified legal review. The repository
contains technical safeguards and draft guidance; it does not identify an approved controller,
provide an approved privacy notice or establish regulatory compliance.

| Decision | Factual implementation / outstanding work | Required owner | Status |
| --- | --- | --- | --- |
| Controller and website legal notice | Company legal identity, address, contact, jurisdiction and responsible operator not supplied/approved | Management + counsel | BLOCKED |
| Purposes and lawful basis | Account identifiers, hashed credentials, conversations, extracted knowledge, sources, tool records and trips persist in PostgreSQL | Controller + counsel | BLOCKED |
| Privacy notice | Explain purposes, access, inference flows, retention, providers, rights and complaint contacts before collecting public users | Counsel + product | BLOCKED |
| Conversation/document retention | User conversation/document deletion exists; persisted source excerpts in other conversations remain; account-wide erasure/export and automated content-retention policy are absent | Controller + engineering | BLOCKED |
| Access/export/deletion requests | Design authenticated request handling, identity verification, response ownership, deadlines and complete deletion scope | Privacy lead + engineering | BLOCKED |
| Backup retention and erasure | Local test uses seven days; snapshots are immutable history until expiry; no immediate per-user erasure of old encrypted snapshots | Controller + operations + counsel | BLOCKED |
| Processors and storage location | Current test is local Mac/Docker/native Ollama; target provider, region, support access, contracts, subprocessors and transfers remain unselected | Management + procurement + counsel | BLOCKED |
| Model/embedding/provider flows | Mock/native local inference tested; configurable semantic embedding endpoint and future travel providers are unqualified; no external provider data claim | Engineering + privacy lead | BLOCKED deployment decision |
| Training consent/provenance | No automatic training use/export of private conversations. Optional dataset approval framework exists; no training done | Data owner + counsel | BLOCKED any future experiment approval |
| GDPR review | Determine applicable roles, bases, security, rights, retention, transfers, records and risk assessment for actual processing | Qualified counsel + controller | BLOCKED |
| AI Act review | Assess actual provider/deployer roles, intended uses, model/application obligations, transparency, oversight and current applicability; no blanket classification from self-hosting | Qualified counsel + product owner | BLOCKED |
| Incident handling | Technical containment/rotation/recovery runbooks exist; notification responsibilities, contacts and operational coverage are not approved | Security/privacy lead + counsel | BLOCKED |
| Public launch | No public deployment authorization, server, DNS or approved mandatory notices supplied | Management / authorized release owner | BLOCKED |

Use current official material during qualified review: the Commission's
[EU data protection framework](https://commission.europa.eu/law/law-topic/data-protection/legal-framework-eu-data-protection_en),
[individual data protection rights](https://commission.europa.eu/law/law-topic/data-protection/information-individuals_en),
and [AI Act framework](https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai).
This checklist intentionally does not decide legal applicability or repeat regulatory dates
that may change. Local safeguards, European positioning, open weights and owner-scoped APIs
are technical facts, not exemptions, legal approval or certification.
