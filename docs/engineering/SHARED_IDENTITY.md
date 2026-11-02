# Shared Onesa account — source candidate, 2026-11-02

This source adds one Company Portal identity for AI Platform, Drone and Robot.
It is disabled by default. A source merge is not a hosted activation record: the
existing owner-controlled dev → staging → main release, current deployment
receipts and exact-source acceptance remain required. Oracle hosting stays in
place; this change provisions no paid identity service or extra application.

## Account and administration experience

When enabled, the AI entry point offers **Continue with Onesa**, account creation
at the Portal's `/account/register`, and account/access management at `/account`.
The Portal determines which applications an ordinary account may open. A central
global administrator can administer the products after MFA. The AI interface links
administrators to `/account?tab=access`; AI content remains owned by its existing
native user UUID. Administrator status does not expose another user's private
conversations, documents, exports or activity.

The first server render resolves the public sign-in method through the configured
API proxy, without forwarding browser credentials, and with a bounded timeout.
The browser rechecks that method before accepting credential submissions. Native
email/password drafts remain editable during this check. Only an explicit missing
configuration route selects the older native flow; an unavailable or malformed
response keeps sign-in unavailable instead of guessing an authentication mode.

Profile, password, recovery, MFA and product access are managed at the central
account. AI's separate native registration/login/profile/password/recovery paths
refuse credential changes while shared identity is enabled. The settings page
keeps AI export, session controls and AI workspace deletion, with explicit fresh
central confirmation instead of a second application password. Deleting AI
workspace data does not delete the central account or the other products.

An expired workspace opens ordinary sign-in in a separate window and keeps an
unfinished draft in the original window's memory. It polls the local authenticated
identity, without sharing cookies or tokens with window messaging. A different
account clears the old private workspace. Sensitive reauthentication is distinct:
it binds the pending flow to the existing local session and immutable central
subject, requires fresh password/MFA, and rejects account switching or a local
session revoked while confirmation was open.

## Identity and permission boundary

The configured issuer is the existing Company Portal at
`https://<portal-origin>/api/v1/identity`. The independently maintained product
client uses these fixed endpoints:

| Endpoint | Purpose |
| --- | --- |
| `/auth` | Authorization code request with browser state and S256 PKCE |
| `/token` | Confidential code exchange with `client_secret_basic` |
| `/session` | Authenticated current account, entitlement, role and revocation assertion |
| `/revoke` | Token revocation or explicit same-account global sign-out |

The scope is `openid email profile onesa`. Basic client ID and secret are form
encoded before the HTTP Basic envelope, including reserved characters. No discovery
URL or provider redirect is followed. Server calls have a five-second timeout and
64-KiB response limit. Responses are schema checked, including exact issuer/client,
canonical immutable subject UUID, verified email, expiry and actual authentication
time. Unvalidated ID tokens are discarded and never confer identity or roles.

The central opaque token stays on the server. Every authenticated AI request asks
`/session` for current account and application access, with no role cache. Central
account disable, grant/session revocation and entitlement removal therefore deny
subsequent requests. Local session/user state is reread after the provider call, so
an in-flight check does not overlook a concurrent local logout or disable. Existing
origin, session-bound CSRF, disabled-account and object-ownership checks remain.

An active generation also rechecks local user/session authority with its lease.
A bounded server check revalidates the central identity every five seconds,
including while the upstream stream is quiet. Provider generation stays in one
task, with a single-item queue and cancellation-safe cleanup. A final central
check and local user/session locks precede assistant persistence. Revoked,
expired or disabled sessions cannot save a partial assistant response. The
existing output-capacity checks remain in addition to these generation checks.

An MFA-authenticated central `global_admin`, or central AI `admin`, can use AI
administrative capabilities. Existing explicit native user-ID engineering and
cybersecurity grants remain recognized only for a live linked identity with AI
access. These grants never arise from an email match. Privileged engineering and
cybersecurity access additionally requires MFA and actual authentication within
five minutes. Central revocation still denies all application access, including
an otherwise allowlisted local user. Existing central and product rights do not
remove per-record ownership filters.

Personal sensitive controls require actual central authentication within five
minutes. The explicit confirmation flow requests `prompt=login`, `max_age=0` and
`acr_values=urn:onesa:mfa`, and the callback verifies the returned fresh MFA state.
A successful token refresh or assertion does not reset `auth_time`.

## Existing account migration

The `shared_identities` mapping is unique on `(issuer, subject)` and on native user
ID. A first central sign-in with no existing native account creates an AI-owned
user with no usable local password. If verified central email matches an existing
native account, sign-in pauses at **Connect your existing AI account**. The user
must prove that account's existing AI password in a browser-bound, five-minute,
encrypted pending flow. Matching email by itself never links records.

Successful linking preserves the native UUID, password hash, conversations, files,
explicit user-ID grants and ownership. The subject mapping then identifies the
account on later sign-ins independently of an email change. Authenticated UI,
refresh and export metadata use the live central name/email, while existing native
credential records remain intact. Conflicting links,
concurrent code redemption, replay and expired transactions fail closed. There is
no bulk email-based migration and no automatic administrative account creation.
An owner-assisted exceptional recovery policy must be agreed before enabling the
feature for users who cannot prove their old account; do not fabricate an email
ownership shortcut.

## Private configuration and storage

All keys below are server-only. Public browser configuration contains only
`enabled` and the central account URL.

| Key | Default / requirement |
| --- | --- |
| `ONESA_IDENTITY_ENABLED` | `false`; activation requires all remaining values |
| `ONESA_IDENTITY_ISSUER` | Empty; exact HTTPS Portal issuer, no trailing slash |
| `ONESA_IDENTITY_CLIENT_ID` | Empty; dedicated registered AI confidential client |
| `ONESA_IDENTITY_CLIENT_SECRET` | Empty; private client secret, never browser configuration |
| `ONESA_IDENTITY_CALLBACK_URL` | Empty; exact `ONESA_PUBLIC_ORIGIN` plus `/api/v1/auth/onesa/callback` |
| `ONESA_IDENTITY_ENCRYPTION_KEY` | Empty; private Fernet key generated and retained by the owner |

HTTP issuer/callback URLs are accepted only for explicitly configured loopback
local development/test. Hosted secure-cookie requirements remain unchanged.
Client secrets and encryption keys are excluded from settings representations.

`identity_transactions` stores hashed state/browser proof and encrypted PKCE/link
payloads with expiry. A callback consumes its state before exchanging a code; an
ambiguous network failure cannot retry that code. `identity_sessions` stores the
opaque central token encrypted with Fernet and attaches it to the existing local
session. Cookies hold only native opaque session/CSRF values and a separate
HttpOnly flow binding, with host-only scope. No access token enters browser
storage, redirects, application responses or logs.

Keep the encryption key in the existing approved private secret store and preserve
it with an access-controlled recovery plan. Losing or replacing it invalidates
existing encrypted sessions and pending flows; it does not prove central logout.
Do not print/decrypt tokens while diagnosing a failed session. Local sign-out
remains available if central validation is unavailable: it verifies local Origin
and CSRF, revokes the local row first and clears browser cookies. **Sign out of
Onesa** is confirmed only when the issuer explicitly returns
`all_sessions_revoked: true`. Provider outage, stale token or missing confirmation
shows that local sign-out completed but central sign-out could not be confirmed.

## Additive migration and controlled activation

Revision `20261102_shared_identity` follows `20261026_cybersecurity` and adds only
`shared_identities`, `identity_sessions` and `identity_transactions`. Existing
users and `auth_sessions` columns are unchanged. Readiness requires the new head
when the feature is enabled. The flag-off source accepts preceding supported
schema heads, permitting a separate additive migration before activation.

The embedded owner migration program understands this exact forward revision and
its three DML grants (24 optional-table grants in total). The standalone observer
includes identity mappings/sessions through their owner foreign keys and hashes
all pending transaction rows without fixture exclusions. Backup inspection knows
the new head. Existing outer release profiles and their commissioned target
restrictions are unchanged: an identity activation requires a separately reviewed,
source-bound owner migration/configuration plan, not an old capability-profile
workaround.

Before activation, qualify the Portal issuer and dedicated callback/client, secure
key custody, migration and narrow runtime DML permissions, cross-product account
and entitlement journeys, MFA/reauthentication, explicit linking, central/global
logout and unavailable-provider behavior on staging. Keep the existing source CI,
private hosted checks and production release receipts. Do not access a denied
staging origin by changing request identity or bypassing its access policy.

The migration refuses destructive downgrade. A rollback must be a reviewed forward
plan retaining subject mappings and owned data. Disabling the feature restores
native flows and genuine legacy sessions for accounts that still have native
credentials. Centrally bound sessions return 401 while shared sign-in is disabled,
including when an account has a valid native invitation; a flag rollback never
converts those sessions into unchecked native authority. Newly created
shared-only accounts have no native password. Their access and recovery must be
addressed explicitly before a flag rollback. Do not delete mappings or downgrade
the database as an automatic recovery step.

## Dependency and verification provenance

The only new direct backend dependency is `cryptography==50.0.2`, for authenticated
encryption of server-side token/PKCE material. Its Apache-2.0 OR BSD-3-Clause license
and distribution provenance are published by the [project on PyPI](https://pypi.org/project/cryptography/50.0.2/)
and the [upstream documentation](https://cryptography.io/en/stable/). Existing
`cffi==2.1.1` and `pycparser==3.1` are reused. The hash-locked runtime/development
files preserve all earlier version pins; only cryptography is added. They were
regenerated for Python 3.11 with `uv pip compile` after this environment's Python
3.11 pip-compile network requests failed. Installation and backend validation use
Python 3.11.17; the normal Python/Node native CI remains mandatory.

`tests/test_onesa_identity.py` tests the protocol using an isolated HTTP transport.
`tests/test_shared_identity.py` uses a disposable real PostgreSQL database for
browser binding, linking/ownership, one-use races, central/local revocation,
same-account reauthentication, explicit grants, CSRF and partial sign-out. The
usual migration and standalone observer tests cover the additive revision.
`tests/shared-identity.spec.ts` covers localized mobile/keyboard entry, code-flow
start, failure retry, explicit account linking, administration/settings and
in-memory draft recovery. Synthetic local browser results and native hosted
qualification are recorded separately in the build/test guide.
