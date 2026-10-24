# Company Portal product and integration

## Website and administration

The company frontend is Next.js. The same repository retains the independently deployable Fastify backend. The public company origin serves published company information; the portal origin provides authenticated administration. The company-facing proxy permits public API paths only. Editor drafts, private documents, HR records, account management and audit history are not public site content.

Content workflows implement draft creation, review, publication, unpublication, revision history and localization. Business workflows implement enquiry persistence, assignments and follow-up, applications and CV storage, controlled documents, approvals and PDF exports. Available source code and passing isolated tests do not establish that hosted mail or business operations have been qualified.

## Authentication and authorization

First-time users register, verify their email and wait for owner approval. Existing explicit approvals remain valid. Email sign-in links or email/password are supported; Portal administrators retain MFA. Factor requirements are disclosed only after credential proof. Recovery and session revocation are implemented. Mutations require same-origin validation and a session-bound CSRF token. Sensitive account changes require fresh password and authenticator/recovery proof. Backend roles constrain editorial, business, HR and owner operations. Hiding a navigation item does not authorize an operation.

Engineering Docs uses separate individually enabled membership through Portal sign-in and the protected Docs access boundary. An ordinary AI account grants no Engineering, Portal or Robot permission. The protected Docs deployment is established; current owner sign-in and publication acceptance remain tied to their dated evidence.

The Company Portal is Onesa’s corporate website and business system; it is not a separately marketed enterprise product.

## Public API reference

The Portal explorer is generated from the actual Fastify/Zod specification. Only `/api/v1/public/*` contracts are included in the public documentation. Administrative contracts remain in the internal experience. Examples are schemas rather than permission to submit real personal information. Public enquiries, applications and uploads can remain publication-gated until their prerequisites are qualified.

## Files and background operations

Private S3-compatible object storage holds uploaded files. Malware scanning fails closed for missing, ambiguous, infected or timed-out responses. Bounded transfers validate size, ownership, expiry and checksums; authorized download chunks are rechecked. Email and deletion outboxes use bounded attempts and terminal failures. Persisted business work is not equated with email delivery.

## Hosting status and limitations

The backend runs on Oracle Cloud Infrastructure independently of its Vercel frontend.
Readiness checks schema and restricted database privileges. Separate workers process
queued work and use a private malware scanner; a healthy public page alone does not
prove a job finished or a document is safe. Release checks and owner acceptance apply
to the actual changed component and workflow. Do not infer applicant-processing,
governance approval or deletion authority from a successful deployment.

[Open the company site](https://onesa.eu/) · [Open the portal](https://portal.onesa.eu/) · [API explorer](/api-explorer) · [Ecosystem](ecosystem.md).
