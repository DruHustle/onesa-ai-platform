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
revoked users/sessions are rejected. No OAuth, SSO, email verification, MFA or email password-reset flow exists.
Signed-in users can change their password after confirming the current password.

OpenAPI exposes the session cookie security scheme. GET me returns id/email/display_name,
never password or token hashes. All content APIs apply current user ownership predicates;
other-user resource IDs are returned as 404. Do not deploy development HTTP-cookie settings
publicly. Nonce CSP is implemented locally; hosted CSP acceptance and comprehensive independent
security review remain pending.


## Account controls (2026-10-10)

`PATCH /auth/profile` changes only the signed-in display name (1–80 characters,
trimmed; whitespace-only values rejected). Email and roles are not writable.
`GET /auth/sessions` returns up to 100 recent active session IDs, creation/expiry
and a current-browser flag, with an explicit total. Tokens and CSRF values are excluded.
`POST /auth/sessions/revoke-others` requires `current_password`; it preserves this
session and revokes every other session. `POST /auth/password` requires
`current_password` and a different `new_password` (12–128 characters), revokes all
prior tokens and issues new session/CSRF cookies to this browser. Login, rotation
and sensitive account changes lock the user first and recheck the session under
lock, so a token revoked after initial authentication cannot commit an update.
All mutations require exact Origin and session-bound CSRF. Password proof attempts
use the existing database-backed authentication throttle. Password fields are cleared
after form submission; they are not persisted in client preferences.

`POST /account/export` requires `current_password` and returns a downloadable JSON
snapshot of the live profile, owned conversations/messages (including saved sources),
extracted document text/metadata, agent runs and trips. A repeatable-read snapshot
prevents mixed versions. Limits are 10,000 content rows and 2 MiB of compact JSON;
oversized exports fail with 413 and require an operator-assisted secure full export.
There is no silent truncation. Password/session credentials, derived vectors and
internal inference telemetry are excluded. Original uploaded binaries are not retained.
Do not add a private-content export to analytics, logs or publicly served artifacts.

`POST /account/delete` requires `current_password` and the exact confirmation
`DELETE MY ACCOUNT`. Active chat/tool runs produce 409. Under the locked user row,
FK cascades atomically remove the live user, sessions, conversations/messages,
documents/chunks/vectors, inference records, agent runs and trips. Cookies are cleared.
Other users remain intact. Backups and external infrastructure retention need separate
operator processing; this endpoint does not claim to purge backup copies or establish
legal retention compliance. Expiring rate-limit buckets are not linked by user FK.
