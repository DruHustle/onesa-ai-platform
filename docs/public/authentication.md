# Authentication and access

Applications use opaque HttpOnly session cookies, hashed server-side; password hashing uses Argon2id. On hosted Onesa AI Platform, choose **Continue with Onesa**. Sign in or create an account at Company Portal. After any required approval, return through the original sign-in request to the AI workspace. Protected endpoints require the cookie. Mutations require the configured Origin and session-bound X-CSRF-Token from the readable CSRF cookie. Refresh rotates sessions; logout revokes them. Do not put session tokens in URLs or localStorage.

Authentication throttling is implemented. This is not a claim of comprehensive production abuse protection. Cross-origin integration needs an explicitly approved same-origin gateway or deployment policy; do not bypass Origin/CSRF checks. Protected Engineering Docs uses Portal registration, email verification and owner-approved individual Engineering membership, then its independent access boundary. A Portal account needs separate owner-approved Engineering membership to open protected Docs. Portal administration and Onesa Robot use their own access grants.

See [examples](examples.md) and the [API explorer](/api-explorer).
