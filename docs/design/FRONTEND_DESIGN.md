# Frontend design

One Next.js App Router application provides `/`, `/knowledge`, `/agents`, `/travel`
and the protected, feature-flagged synthetic `/industrial` workspace.
The Chat page owns session discovery, auth form, conversation selection/history,
streaming state, abort controller, document selection, and error/retry UI. FeatureShell
shares navigation for document/tool/trip screens. lib/api reads the CSRF cookie and uses
same-origin requests; credentials are never stored in localStorage.

SSE parsing incrementally decodes UTF-8, buffers complete event frames and requires
message_end for success. Interrupted output is labelled, and persisted history is
reloaded to reconcile state. Responses use ReactMarkdown/GFM, highlighted code blocks
and no raw HTML plugin. Copy uses the browser clipboard with a visible failure path.

Global design tokens control color/type/spacing. Responsive navigation supports a
close button, backdrop, Escape, focus containment and inert background. Message entry
supports Enter to send, Shift+Enter for a newline, and IME composition handling. Loading,
empty, disabled and alert states are explicit. Three Chromium flows verify core desktop,
feature and mobile behavior; comprehensive assistive-technology auditing is still pending.

## Interface internationalization

English remains default. Shared auth/navigation copy is externalized in lib/i18n.tsx with
English/German catalogs and typed keys; language selection persists in a non-sensitive cookie.
Server layout validates cookie and ONESA_UI_LOCALE against installed catalogs, renders html.lang
and initializes context. Invalid preferences fall back to the configured catalog; invalid
operator configuration fails explicitly. Other chat/knowledge/agent/travel workspace text and
API error messages remain English. Complete reviewed translations are separate work, not claimed.
Add French/Spanish/other catalogs and migrate remaining strings incrementally; retain model output
verbatim and never infer language performance from interface availability. No official tagline
or geographic identity is embedded in model routing. Draft translation needs linguistic review.

## Independent deployment boundary

Sources live in `onesa-ai-platform-frontend/apps/chat`; documentation lives alongside
in `apps/docs`. `packages/api-client` holds shared browser transport and types derived
from unchanged OpenAPI via `make api-client`, with drift enforcement in CI. Responses
that previously exposed arbitrary dictionaries remain `Record<string, unknown>`;
fully typed backend response envelopes remain incremental contract work. Authentication
uses the generated typed client. The raw Response path preserves SSE and upload support.

App Router server routes read private `ONESA_API_URL` at runtime, forwarding streaming
request/response bodies, cookies and Origin/CSRF. They restrict destinations to the
configured operator origin and allow only `/api/v1/*`, health and readiness. Metrics
and inference addresses have no browser route. Server fetch handles disconnect signals;
real browser stop/reload acceptance is recorded in PLATFORM_SPLIT_REPORT.md. Production
Caddy may proxy API routes directly to FastAPI using the same public origin.


## Shared interface contract

Read [Onesa Design System](../architecture/ONESA_DESIGN_SYSTEM.md) and the pinned consumer manifest before frontend changes. AI and Docs retain distinct product shells over shared semantic tokens. Browser/OS preference controls appearance without selectors, clock timers or stored overrides. Verify drafts, focus, streams, forced colors, reduced motion and affected routes in both modes; local verification does not prove deployed acceptance.


## Industrial Investigation V1

The existing session-renewal wrapper and in-memory draft guard protect the synthetic
workspace. Users inspect coverage, calculated facts and cited hypotheses before explicitly
creating an internal draft. Pending mutations lock selection; failed saves keep text.
Same-account renewal preserves mounted work; another account remounts it. No draft browser
storage is used. Named timeline scroll regions support keyboard focus. Critical controls
and errors have EN/DE labels; original references and generated narrative remain English.

### V1.1 feedback and evidence

Asset catalog and saved-list loading are independent. A failed catalog cannot hide
available saved records. A late initial list merges missing IDs while retaining
records already accepted during the request; it does not replace the editor.
Initial list loading, failed loading, confirmed empty and populated results are
separate states. Only `industrial_demo_disabled` identifies a disabled demo;
a resource 404 says missing or unavailable to this account, without revealing
ownership. Errors preserve entries and never claim that an unavailable list is empty.

A source-received, owned investigation can be downloaded using the existing Blob/
download pattern. The export allowlists the synthetic label, selection and snapshot/
source versions, computed facts, coverage, explanation/citations, model/outcome,
draft, review and limitations. It excludes account/session identities, secrets,
provider request IDs and raw logs. Pending mutation/generation disables export.
A qualified engineer still reviews factual support and each hypothesis; a recorded
owner self-review is not independent industrial acceptance or equipment authority.
