# Authentication

Register/login require exact Origin equal to ONESA_PUBLIC_ORIGIN. Passwords are 12–128
characters and hashed with Argon2id; normalized email is unique. Login gives generic
credential errors, including absent accounts. Authentication is throttled with an atomic
PostgreSQL minute bucket keyed by the socket peer; forwarding headers are not trusted.
Behind the shared web proxy this is a conservative shared ingress limit, which must be
capacity-tuned and/or replaced with trusted edge throttling for production traffic.

Sessions use 32-byte random URL-safe tokens. Only SHA-256 token and CSRF representations
are stored, with expiry and revocation. Session cookie is HttpOnly, SameSite=Lax, path `/`;
Secure is required in production. A separate same-site readable CSRF cookie supplies the
X-CSRF-Token header; mutations check its hash against the authenticated session and Origin.
Refresh rotates under a row lock; logout revokes and clears cookies. Disabled/expired/
revoked users/sessions are rejected. No OAuth, SSO, email verification or reset flow exists.

OpenAPI exposes the session cookie security scheme. GET me returns id/email/display_name,
never password or token hashes. All content APIs apply current user ownership predicates;
other-user resource IDs are returned as 404. Do not deploy development HTTP-cookie settings
publicly. CSP hardening and comprehensive independent security review remain pending.
