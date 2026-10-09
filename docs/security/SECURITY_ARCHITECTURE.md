# Security architecture

Public entry is one same-origin web service. Production uses TLS/Secure cookies and
private database/API/inference networks. Production uses a separate restricted CRUD
application database URL and readiness rejects superuser connections. Sessions are opaque and hashed, passwords
Argon2id, and mutation requests Origin/CSRF protected. UUID resource queries also filter
owner; knowing an identifier grants no access. Session expiry/revocation and disabled
accounts are enforced. Authentication rate buckets persist across API processes.

ReactMarkdown renders no raw HTML. Uploads and total bodies are bounded; parsers accept
only known text/PDF structures. Retrieval/model outputs are evidence/proposals, not
instructions granting tool rights. The tool registry has only safe local computations;
there are no arbitrary shell/network/booking tools. Structured plans are schema validated.

Metrics require an independent bearer credential and are not web-proxied. Logs use route
templates and generated correlation IDs, not content, passwords, cookies or upstream errors.
Application containers are non-root; production adds read-only/tmpfs/capability restrictions.
Dependency audits are recorded in testing/status; they are not security certification.

Remaining qualification: trusted edge capacity/rate limiting, hostile PDF process isolation,
CSP, broader abuse/load tests, secrets/backup encryption and access policy, independent
security review, actual TLS and GPU/embedding deployment. No OAuth/reset/email verification.

## Split hardening

Independent Docker contexts exclude private configuration, weights and test tooling.
The BFF accepts only versioned API and health paths, removes untrusted forwarding
headers and never takes upstream hostnames from users. Cookies remain opaque,
HttpOnly/Secure in production, host-only/SameSite=Lax with exact Origin and CSRF
checks. Existing owner/tool/isolation tests are retained. No token is stored in
localStorage and no public inference port is introduced.

PDF extraction now runs with an empty environment, isolated interpreter, temporary
working directory, CPU/file-descriptor/output limits and a wall deadline; Linux
adds a 512 MiB address-space cap. This limits resource exhaustion and keeps database
credentials out of the parser process. It remains under the API's container UID and
network namespace: stronger dedicated worker/seccomp/network confinement and hostile
PDF penetration qualification remain release blockers. No claim of a full sandbox
or security audit is made. Tracked-source secret patterns and lockfile audits supplement
existing tests; deployment secret injection and independent review remain required.
