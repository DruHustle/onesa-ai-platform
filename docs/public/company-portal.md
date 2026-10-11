# Company Portal product and integration

## Website and administration

The company frontend is Next.js. The same repository retains the independently deployable Fastify backend. The public company origin serves published company information; the portal origin provides authenticated administration. The company-facing proxy permits public API paths only. Editor drafts, private documents, HR records, account management and audit history are not public site content.

Content workflows implement draft creation, review, publication, unpublication, revision history and localization. Business workflows implement enquiry persistence, assignments and follow-up, applications and CV storage, controlled documents, approvals and PDF exports. Available source code and passing isolated tests do not establish that hosted mail or business operations have been qualified.

## Authentication and authorization

Portal accounts are administrator-created. Password and MFA enrollment/login, recovery and session revocation are implemented. Mutations require same-origin validation and a session-bound CSRF token. Sensitive account changes require fresh password and authenticator/recovery proof. Backend roles constrain editorial, business, HR and owner operations. Hiding a navigation item does not authorize an operation.

## Public API reference

The Portal explorer is generated from the actual Fastify/Zod specification. Only `/api/v1/public/*` contracts are included in the public documentation. Administrative contracts remain in the internal experience. Examples are schemas rather than permission to submit real personal information. Public enquiries, applications and uploads can remain publication-gated until their prerequisites are qualified.

## Files and background operations

Private S3-compatible object storage holds uploaded files. Malware scanning fails closed for missing, ambiguous, infected or timed-out responses. Bounded transfers validate size, ownership, expiry and checksums; authorized download chunks are rechecked. Email and deletion outboxes use bounded attempts and terminal failures. Persisted business work is not equated with email delivery.

## Hosting status and limitations

The reviewed backend startup is Node executing the compiled server. Readiness verifies schema and restricted database privileges. A process responding to liveness is insufficient if readiness fails. The production database-role failure is not declared resolved by a local correction. The separate staging API layout has been inspected, but credentials, persistent storage, a real worker and end-to-end operational tests remain required. A web service named worker does not prove the worker process is running.

[Open the company site](https://onesa.eu/) · [Open the portal](https://portal.onesa.eu/) · [API explorer](/api-explorer) · [Ecosystem](ecosystem.md).
