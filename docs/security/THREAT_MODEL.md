# Threat model

Assets: private conversations/documents/trips, credentials/session hashes, model keys,
GPU capacity, artifact provenance and operational backups. Actors: unauthenticated attackers,
other users, malicious documents/model responses, and privileged misconfiguration.

| Threat | Implemented control | Remaining check |
| --- | --- | --- |
| Cross-user reads/writes | Owner-filtered queries and 404 isolation tests | Independent authorization review |
| Cookie theft/CSRF | HttpOnly/SameSite, Origin+CSRF, production Secure | Actual TLS/CSP/XSS assessment |
| Credential guessing | Argon2, generic login errors, DB auth buckets | Production ingress capacity tuning |
| Model/tool injection | Allowlisted validated local tools; proposals grant no rights | Any future effectful tools need approvals |
| Upload/parser exhaustion | 6 MiB total/5 MiB file, type/page/text/chunk limits | Isolated workers and hostile PDF tests |
| Concurrent/incomplete chat | Row lock + bounded lease; no completed partial output | Target-host model/failure load |
| Serving address/key disclosure | Public alias, sanitized errors, private ports | Network/firewall verification |
| Dataset leakage | Provenance/consent/review, checksums/splits, no automatic chat export | Human PII/language/legal review |
| Backup theft/destruction | Private files, new-target-only restore, no routine volume deletion | Encryption/off-host retention and RPO/RTO |

Known limits are not hidden by passing mocks. The current software is a verified local
baseline, not an audited public production service.
