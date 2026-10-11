# Security and authorization overview

## Identity boundaries

Company Portal, AI Platform and Robot authenticate independently. A link between products does not transfer identity or permissions. HttpOnly session cookies, configured origins and CSRF tokens protect mutation paths. Backend authorization checks apply to every object and file access; UI restrictions alone are insufficient.

Portal implements password/MFA and fresh proof for sensitive account changes. AI enforces invitations where enabled, expiring recovery and user-owned conversations/documents/trips. Robot confirms operator authority separately from motion validation. Sessions and execution authority can be revoked.

## Data and tool boundaries

Public content must be approved and published. Drafts, HR documents, private uploads, restricted database details and corporate records must not enter public APIs, search, diagrams or PDF artifacts. File validation and malware scanning fail safely. API schema validation and body/time bounds protect resource usage. Secret-bearing URLs must not enter documentation provenance or browser bundles.

Models cannot override registered tool permissions or independent robot safety checks. Prompt injection must not grant access to another user's documents or authorize external actions. Hosted generation needs authenticated TLS with administrative and operational routes protected, not merely a chat-completions API key.

## Documentation boundary

The public site is an allowlisted static build. Internal pages, indexes, schema metadata, operational manuals and assets require the server-side engineering access gate for every request. Identity failure denies access; hidden links and client-side login screens are not an access boundary. The internal host is not claimed deployed until its authentication, session revocation, asset access and cache isolation have been tested.

Security tests and dependency scans do not establish a certification, legal compliance or completed independent penetration test. Report vulnerabilities using the repository's private reporting policy, without posting credentials or personal data.
