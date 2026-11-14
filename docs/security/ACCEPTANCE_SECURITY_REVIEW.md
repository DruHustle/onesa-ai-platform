# Acceptance 005 security review

This is a source review plus automated local negative testing, not a penetration test or
certification. The selected controls use the pinned
[OWASP ASVS 5.0.0 chapters](https://github.com/OWASP/ASVS/tree/v5.0.0/5.0/en).
A complete ASVS level and deployment threat profile have not been approved; controls below
are scoped to implemented routes, not a claim of full ASVS conformance.

| ASVS area/control | Implementation and negative evidence | Result / limitation |
| --- | --- | --- |
| V6.1.1, V6.3.1 authentication attack protection | Argon2id; hashed account and real socket-peer limits; shared-proxy independence and forged forwarding tests; bounded hash concurrency | PASS selected tests; production ingress tuning pending |
| V6.2 password controls | 12–128-character accepted passwords, no silent truncation; UI password fields/paste; strict request schemas | BLOCKED broader profile: password change, compromised-password list, MFA/reset policies are absent |
| V7.2.1–V7.2.4 session issue/verification | Cryptographically random opaque tokens, hashes at rest, server expiry, authenticated rotation; reauthentication revokes presented same-user session | PASS replay/rotation tests; concurrent other-user sessions are not implicitly revoked |
| V7.3 lifetime policy | Absolute 24-hour default; expired sessions rejected | BLOCKED deployment policy: no risk-approved idle timeout or documented reauthentication schedule |
| V7.4 invalidation | Logout and refresh invalidate old tokens; expiry tests | PASS selected tests; user disable/account-wide revocation product workflow absent |
| V8 authorization | Owner filters on conversation/document/RAG/search/reindex/agent/trip read and mutations; internal docs allowlist fails closed | PASS foreign identifiers produce 404/denied; no enterprise role system claimed |
| V3 web frontend / CSRF | Same-origin mutation validation plus cookie-bound CSRF; Secure/HttpOnly/host-only session cookies; SameSite=Lax; no wildcard CORS | PASS TLS/prohibited-origin/CSRF tests |
| V5 file handling | 5 MiB upload limit, strict TXT/PDF type/signature/UTF-8 validation; no client-selected disk path; private disposable PDF worker | PASS invalid uploads; stored originals are absent |
| V5 parser confinement | Empty environment, isolated Python, bounded input/output/pages, CPU/FD/address-space/wall limits; Linux seccomp denies new files, sockets, fork/exec, tracing and io_uring; ingestion concurrency bound | PASS valid-text and real Linux denied-operation probe on arm64; x86_64 execution awaits Linux CI/host |
| V2 validation / API security | Strict schemas reject extra privilege fields; sanitized validation/model failures; request/body/step/time/response bounds | PASS malformed/oversized/tool misuse tests |
| Prompt injection and agent permissions | Retrieval restricted before model input; source injection cannot cross owners; model plans checked against registry AND explicit granted tools | PASS registered-but-ungranted proposal denied; model instructions cannot expand grants |
| Transport and headers | Verified local CA/hostname; HTTPS canonical redirects; HSTS/nosniff/frame/referrer headers; private API/metrics routes | PASS local TLS; public TLS and strict nonce-based CSP are pending |
| Secrets / operational access | Isolated env/key files; separate owner, CRUD app, SELECT backup roles; protected scrapes/webhook/admin endpoints; non-root hardened application containers | PASS local least-privilege startup, source/generated/image scans; deployment secret manager/rotation execution pending |
| Dependencies | Locked backend/frontend and backup crypto dependencies; application audit results in acceptance evidence | PASS known application advisories at test time; OS image vulnerability scan and independent review pending |
| Logging / data protection | JSON event/correlation/method/route/status/timing only; locally generated IDs; no raw access logs, passwords, cookies, full prompts or document bodies; aggregate metrics labels | PASS source review and live scrape/log checks; no distributed audit/tracing certification |

The Linux filter is a syscall reduction control, not a complete sandbox. Supported ABIs are
explicit and unknown Linux architectures fail closed. macOS keeps resource limits without
seccomp; production file qualification uses the Linux container. See the
[Linux seccomp documentation](https://www.kernel.org/doc/html/latest/userspace-api/seccomp_filter.html)
for the scope of this mechanism. Parser exploits and adversarial model outputs remain reasons
for independent testing; automated negative examples do not exhaust the attack space.

## Findings and remediation

| Finding | Change | Verification |
| --- | --- | --- |
| Reauthentication issued a new token while the presented old same-user token remained valid | Revoke that token in the same transaction before issue | Stale token 401; new session works; ownership regression passes |
| One peer bucket could throttle every user behind ingress; forwarded headers are untrusted | Separate casefolded hashed-account and socket-peer budgets | Different account unaffected; spoofed forwarding cannot bypass peer budget |
| HTTPS ingress caused a canonical API redirect to HTTP | Set request scheme from validated staging/production transport configuration; BFF emits safe relative redirects for same host | TLS probe and browser redirect check pass |
| Unbounded parallel password hashes/parsers could exhaust a small API container | Bound hashing and ingestion separately from request limit | Eight-user application run and resource samples; parser regression |
| PDF worker could open files/create sockets despite stripped environment | Preload trusted codecs, apply Linux seccomp before parsing untrusted input | Valid PDF text preserved; files/network/fork/exec return EPERM |
| Empty optional native inference key created an illegal empty Bearer header | Omit Authorization when key is empty; preserve keyed vLLM behavior | New adapter regression and repeated actual native acceptance |

Earlier failed diagnostic runs remain in ignored local evidence; final measurements are
separate. Known residual release blockers are explicit password/session profile decisions,
account privacy workflows, strict CSP qualification, target-host/OS vulnerability review,
independent security review and operational/legal gates. No unresolved finding is hidden by
calling the whole application production-ready.
