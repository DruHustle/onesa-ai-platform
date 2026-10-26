# API reference

All business routes use `/api/v1`. Session-cookie authentication is declared in OpenAPI;
mutations also require exact Origin and X-CSRF-Token. Register/login are unauthenticated
but Origin checked and throttled. Probes are public; metrics use an independent private bearer token.

Every response carries a server-generated X-Request-ID. Errors use
`{"error":{"code":"...","message":"...","request_id":"UUID"}}`; validation omits
submitted values/passwords. Common statuses: 401 auth, 403 Origin/CSRF/permissions,
404 missing/other-user resource, 409 duplicate/busy/revision conflict, 413 bound,
415 format, 422 validation/model selection, 429 auth throttle, 503 dependency/generation failure.

[openapi.json](openapi.json) is the implemented machine-readable contract. Regenerate with
`make openapi`; inspect `/docs` on the internal/local API for schema details.

## Optional Digital Twins v1

`/api/v1/twins` is default-off and independently owned. Its OpenAPI schemas define
template/asset creation, private file preview and import commit, explicit model mappings,
revision-fenced activation, source bindings, time-window history, documents, annotations,
viewpoints, scoped evidence tools and saved inspection snapshots. Owner sessions and
existing grants authorize every indirect resource. Mutations retain Origin/CSRF.
`POST /sources/{id}/readings` instead requires a hashed, revocable ingestion-only
`X-Onesa-Source-Token`; it grants no read access or tenant choice.

The locally owned v1 observation body is `{mode, samples}`. Samples identify message,
tag, finite value, unit, timezone timestamp and quality. The source's reviewed mapping
selects the installed asset/component. Duplicate identities are idempotent; conflicting
content fails. Replay cannot overwrite live state. No shared executable schema SDK or
peer service is required. The [Digital Twins guide](../engineering/DIGITAL_TWINS.md)
documents supported formats, bounds, optional MQTT translation and field ownership.

## Implemented endpoints

| Method/route | Purpose | Authentication | Request schema | Success |
| --- | --- | --- | --- | --- |
| POST `/api/v1/auth/register` | Register | public | Register | 201 |
| POST `/api/v1/auth/login` | Login | public | Credentials | 200 |
| GET `/api/v1/auth/me` | Me | session | none | 200 |
| POST `/api/v1/auth/refresh` | Refresh | session + CSRF/Origin | none | 200 |
| POST `/api/v1/auth/logout` | Logout | session + CSRF/Origin | none | 204 |
| PATCH `/api/v1/auth/profile` | Display name | session + CSRF/Origin | ProfileUpdate | 200 |
| GET `/api/v1/auth/sessions` | Active sessions | session | none | 200 |
| POST `/api/v1/auth/sessions/revoke-others` | Revoke other tokens | session + CSRF/Origin | PasswordProof | 204 |
| POST `/api/v1/auth/password` | Change password, rotate cookies | session + CSRF/Origin | PasswordChange | 200 |
| POST `/api/v1/account/export` | Bounded private JSON snapshot | session + CSRF/Origin | PasswordProof | 200 |
| POST `/api/v1/account/delete` | Atomic live account deletion | session + CSRF/Origin | DeleteAccount | 204 |
| POST `/api/v1/conversations` | Create | session + CSRF/Origin | ConversationCreate | 201 |
| GET `/api/v1/conversations` | Listing | session | path/query; see OpenAPI | 200 |
| GET `/api/v1/conversations/{identifier}` | Detail | session | path/query; see OpenAPI | 200 |
| PATCH `/api/v1/conversations/{identifier}` | Rename | session + CSRF/Origin | Rename | 200 |
| DELETE `/api/v1/conversations/{identifier}` | Remove | session + CSRF/Origin | path/query; see OpenAPI | 204 |
| GET `/api/v1/models` | Models | session | none | 200 |
| GET `/api/v1/models/{identifier}` | Model | session | path/query; see OpenAPI | 200 |
| POST `/api/v1/chat/completions` | Complete | session + CSRF/Origin | ChatRequest | 200 |
| POST `/api/v1/knowledge/documents` | Upload | session + CSRF/Origin | Body_upload_api_v1_knowledge_documents_post | 201 |
| GET `/api/v1/knowledge/documents` | Documents | session | path/query; see OpenAPI | 200 |
| GET `/api/v1/knowledge/documents/{identifier}` | Document | session | path/query; see OpenAPI | 200 |
| DELETE `/api/v1/knowledge/documents/{identifier}` | Remove | session + CSRF/Origin | path/query; see OpenAPI | 204 |
| POST `/api/v1/knowledge/documents/{identifier}/reindex` | Reindex | session + CSRF/Origin | path/query; see OpenAPI | 200 |
| POST `/api/v1/knowledge/search` | Search | session + CSRF/Origin | Search | 200 |
| GET `/api/v1/agents/tools` | Tools | session | none | 200 |
| GET `/api/v1/agents/runs` | Listing | session | none | 200 |
| POST `/api/v1/agents/runs` | Execute | session + CSRF/Origin | RunRequest | 201 |
| GET `/api/v1/agents/runs/{identifier}` | Detail | session | path/query; see OpenAPI | 200 |
| POST `/api/v1/agents/runs/{identifier}/cancel` | Cancel | session + CSRF/Origin | path/query; see OpenAPI | 200 |
| GET `/api/v1/travel/trips` | Listing | session | none | 200 |
| POST `/api/v1/travel/trips` | Create | session + CSRF/Origin | Preferences | 201 |
| GET `/api/v1/travel/trips/{identifier}` | Detail | session | path/query; see OpenAPI | 200 |
| PUT `/api/v1/travel/trips/{identifier}` | Revise | session + CSRF/Origin | Revision | 200 |
| DELETE `/api/v1/travel/trips/{identifier}` | Remove | session + CSRF/Origin | path/query; see OpenAPI | 204 |
| GET `/health` | Health | public | none | 200 |
| GET `/ready` | Ready | public | none | 200 |

## Response shapes

- Auth: safe `id`, `email`, `display_name`; login/register/refresh issue cookies, logout is 204.
- Conversations: `id`, `title`, `selected_model_id`, `created_at`, `updated_at`. List returns
  `items,total,limit,offset`; detail returns `conversation,messages`. Messages contain
  `id,role,content,status,sequence`; content has `text` and optional source records.
- Models: safe configured metadata (`id,name,backend,model_identifier,context_tokens,modalities,quantization,revision,real_inference`); list wraps `items`. URLs/keys are excluded.
- Chat: nonstream `message_id,content,model_id,sources`; streaming lifecycle in STREAMING.md.
- Documents: `id,title,media_type,embedding_version,created_at`; detail adds `text`; listing
  `items,limit,offset`. Search returns `sources,backend`; sources have document_id/title/chunk/
  text/distance/embedding_version. Reindex updates vectors/version transactionally.
- Agents: tools `name,schema,effect`; runs `id,goal,status,steps,created_at`; list wraps items.
  Steps contain safe result/status or sanitized failure. Caller can supply a run UUID for cancellation.
- Trips: `id,destination,duration,budget,currency,preferences,revision,itinerary,created_at,
  updated_at,live_data_verified=false,notice`. Itinerary contains typed days/activities,
  assumptions, provider availability and backend label. List wraps items. PUT requires expected_revision.
- Probes: health `status=ok`; ready `status=ready,backend` or sanitized 503.

## Representative requests

Use a private cookie jar; browser JS reads the separate CSRF cookie after login.
These are dummy example credentials/IDs, not created accounts:

```sh
curl -c /tmp/onesa-cookies -H 'Origin: http://localhost:3000' \
  -H 'Content-Type: application/json' \
  -d '{"email":"example@example.com","password":"example-password-123!","display_name":"Example"}' \
  http://localhost:3000/api/v1/auth/register
# After reading the onesa_csrf value into a private shell variable:
curl -b /tmp/onesa-cookies -H 'Origin: http://localhost:3000' \
  -H "X-CSRF-Token: $ONESA_CSRF" -H 'Content-Type: application/json' \
  -d '{"title":"My conversation"}' http://localhost:3000/api/v1/conversations
```

A successful conversation response has UUID id/title/public model alias and timestamps.
GET detail returns ordered user/assistant content. Send content/conversation_id/stream to
chat; select document_ids for RAG. Upload documents as multipart `file`, not JSON. Search
body is query/document_ids/limit. Tool run body is goal/steps/allowed_tools (permissions
must be explicit). Trip POST is destination/duration/budget/currency/preferences; PUT adds
expected_revision. Full field bounds/defaults are in the exported schema.

GET `/metrics` is intentionally excluded from public OpenAPI, requires an independent
bearer credential, and returns Prometheus text. It is not exposed through the web proxy.

Amendment 001 leaves all public API contracts unchanged. There is no geographic/language routing
or country validation in shared endpoints. Serving still exposes only the default alias. Future
model-family metadata lives in the local candidate artifact registry, not this API. Existing
owned document_ids select independent knowledge sets; named collections/metadata APIs are proposed.

Milestone 2 adds safe model metadata (backend/model_identifier/context/modalities/quantization/
revision/real_inference), plus model/metrics in completed chat results. Existing IDs/routes and
fields remain. Errors can use model_not_available, inference_timeout, inference_unavailable or
generation_failed; messages remain generic and correlation IDs allow troubleshooting. Images
remain unsupported by the typed text input API. Successful history content includes inference
provenance; reported run token counts are populated, unknown counts remain null.

## Documentation identity and assistance

GET `/api/v1/documentation/access` requires the existing session and returns `engineering` from the private engineering-user-ID allowlist. POST `/api/v1/documentation/answer` requires session, matching Origin and CSRF; body is `{query, scope}` with query length 1–4000 and scope public/internal. Internal retrieval is rejected before reading its collection unless the caller is an authorized engineer. Responses include answer, assigned source links/classifications and actual backend; unavailable retrieval/inference returns a controlled 503. Public documentation OpenAPI excludes these portal-internal routes and all operational/private inference routes.


Knowledge, agents, travel and model discovery now use Pydantic response models and
standard generated TypeScript request/response types. Extensible tool result objects
remain typed JSON values. Malformed persisted results fail with a sanitized 503;
unknown debug fields do not escape a strict response contract. Generated-file drift
checks are separate from the conservative pre-audit compatibility review, which remains
a release gate. See [authentication](AUTHENTICATION.md) for account data scopes/limits.


The private upstream embedding request now explicitly includes `dimensions:256`.
The configured optional query instruction applies only to search text; uploaded passages
remain unprefixed. This is an internal provider protocol change, with no public route/
request/response change. Production HTTP embedding endpoints require authenticated HTTPS.


## Synthetic Industrial Investigation V1

All routes below require the existing session; every mutation also requires Origin/CSRF.
The feature defaults disabled. Shared demo assets are synthetic, not organization tenancy.
Investigation resources and drafts are user-owned. Foreign identifiers return no data.
The generated OpenAPI/client are authoritative for current schemas.

| Method and relative route | Behavior |
| --- | --- |
| GET `/industrial/assets` | Allowlisted synthetic asset metadata |
| GET `/industrial/evidence` | Asset/scenario and aware start/end queries; read-only facts/coverage |
| POST `/industrial/investigations` | Explicit ID, asset/scenario/window; persist immutable input snapshot and calculated facts |
| GET `/industrial/investigations` | Current user's saved investigations |
| GET `/industrial/investigations/{id}` | Owned result; expired interrupted generation is marked failed |
| POST `/industrial/investigations/{id}/generate` | Expected revision; bounded existing model/retrieval adapters or explicit abstention |
| POST `/industrial/investigations/{id}/cancel` | Expected revision; stop application operation; upstream computation may continue |
| PUT `/industrial/investigations/{id}/draft` | Expected revision and explicit internal draft text; never external dispatch |
| POST `/industrial/investigations/{id}/review` | Expected revision, accepted/needs_changes and note; records owner self-review, not independent approval |

Creation IDs are idempotent only for the same owner and identical selection. A mutation
response with an uncertain network outcome must be reconciled by reading the owned ID,
not blindly submitted again. A failed generation retains facts and never becomes a
completed result. Sparse/missing/conflicting inputs are explicit. No OEE or certified
diagnosis is produced. A review binds the saved revision/draft hash and editing invalidates
its current approval without erasing earlier decisions. Retention and real industrial
processing decisions remain separate; this API authorizes synthetic development only.

## Bounded record navigation and account data

Conversation, document, run and trip lists support `limit` (1–100; default 50)
and an opaque `cursor`, returning `next_cursor` or null. Immutable creation time
descending and UUID descending break ties deterministically; updates do not move
records between pages. Conversation/document offset requests remain compatible.
Each query and cursor stays owner scoped; a cursor never grants access. Use the
detail endpoint for an explicitly selected document, even when it is absent from
the current page. Travel keeps a saved trip ID in the URL and restores it through
the owner-checked detail endpoint on reload; failed restoration blocks saving until
retried or another trip is selected. Draft text stays in the current window only.
Account export includes saved Industrial evidence, drafts and
review decisions when that schema exists, including when Industrial is disabled.
Row and byte ceilings include those records before materialization. Pre-Industrial
normal AI schemas return an empty Industrial collection without querying an absent
table. Export remains password/session/Origin/CSRF protected.

## Synthetic Industrial JSON adapter

`POST /industrial/imports/preview` validates `EvidenceBundle` v1 without storing it.
`POST /industrial/investigations` accepts the same bundle as `source`, with its
exact asset/window and a client UUID. Both existing Industrial and import flags
must be explicitly enabled; defaults remain false. Customer data is not approved.
The preview JSON body and validated bundle are bounded to 512 KiB. Saving uses
a 516 KiB pre-parsing ceiling to accommodate the bounded UUID/selection envelope. Up to 500 events, 500 sparse
signal samples and 20 references are supported. Explicit UTC timestamps, IANA source
timezone, compatible pressure/bar or temperature/degC units, bounded finite numbers,
asset/metadata identity, reference text hashes and immutable source IDs are required.
Import quality/provenance, event kind/end, reference rights/superseded state and
evidence metadata version must be explicitly supplied; bundled-fixture defaults
never fill missing imported facts. Superseded is a JSON boolean.
Conflicting source IDs fail transactionally; idempotent same-content retries cannot
overwrite a saved investigation. No URLs, files, SQL or instructions are executed.
See the generated OpenAPI schema and synthetic `tests/fixtures/industrial-import-v1.json`.
`industrial_facts` is registered only in the enabled isolated scope, requires an
explicit tool grant and owner-checked investigation ID/hash, and reads saved facts
without model inference or equipment actions. Original local tools remain available.
