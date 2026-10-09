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

## Implemented endpoints

| Method/route | Purpose | Authentication | Request schema | Success |
| --- | --- | --- | --- | --- |
| POST `/api/v1/auth/register` | Register | public | Register | 201 |
| POST `/api/v1/auth/login` | Login | public | Credentials | 200 |
| GET `/api/v1/auth/me` | Me | session | none | 200 |
| POST `/api/v1/auth/refresh` | Refresh | session + CSRF/Origin | none | 200 |
| POST `/api/v1/auth/logout` | Logout | session + CSRF/Origin | none | 204 |
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
- Models: public `id,name,backend`; list wraps `items`. Internal names/URLs/keys are excluded.
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
