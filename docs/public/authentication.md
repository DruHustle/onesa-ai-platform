# Authentication and access

Applications use opaque HttpOnly session cookies, hashed server-side; password hashing uses Argon2id. Register/login through the configured application origin. Protected endpoints require the cookie. Mutations require the configured Origin and session-bound X-CSRF-Token from the readable CSRF cookie. Refresh rotates sessions; logout revokes them. Do not put session tokens in URLs or localStorage.

Authentication throttling is implemented. This is not a claim of comprehensive production abuse protection. Cross-origin integration needs an explicitly approved same-origin gateway or deployment policy; do not bypass Origin/CSRF checks. Protected Engineering Docs uses Portal registration, email verification and owner-approved individual Engineering membership, then its independent access boundary. Ordinary AI registration grants no Engineering, Portal administrator or Robot access.

See [examples](examples.md) and the [API explorer](/api-explorer).
