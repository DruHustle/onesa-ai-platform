# Platform split migration plan

2026-10-09, Europe/Berlin. Implement the supplied split directive ahead of M3.2.

The actual repository root is `onesa-ug/onesa-ai-platform`, on master at
`1ea8d54`, initially clean, with no other branches. The enclosing workspace resolves
to an unrelated ancestor Git repository; all migration Git commands run here.
The reversible baseline branch is `baseline/platform-split-20261009`.
An ignored SHA-256 inventory is in `data/migration-baseline/tracked-sha256.json`.

Preserve the shared Next.js chat/knowledge/agents/travel application by moving
`apps/chat` to `onesa-ai-platform-frontend/apps/chat`; move the scoped Docusaurus
portal alongside it at `onesa-ai-platform-frontend/apps/docs`. Move `services/api`
to `onesa-ai-platform-backend`, retaining its modular `app`, migrations and tests.
Move training and evaluation tools into the backend, retaining package names.
Keep documentation sources/exports, scripts, security backports, infrastructure,
private data, native Ollama runtime/models and the virtual environment at the root.
Use Git moves and carry ignored dependency/build directories with their applications.
Do not create another repository or duplicate the functioning applications.

Update runtime/import/source-generator paths, package scripts, Make, CI and build
contexts. Make frontend and backend image contexts independent. Preserve `/api/v1`
and the same-origin session/CSRF model; add generated typed client contracts.
Next.js proxies API/health/readiness; Caddy supplies TLS and direct unbuffered API
routing in production. Keep Compose name `onesa-platform`, DB service/volume names,
backend port 8000 and chat port 3100. Retain private DB/inference endpoints.
No schema migration or database reset is needed. Uploaded extracted content lives
in PostgreSQL; model weights, evaluation artifacts and exported documents stay put.

Before moving: run CPU/lint/types/build, real PostgreSQL and browser baselines.
A private custom-format snapshot was restored into the new
`onesa_split_20261009_restore` database. Both have revision `608f3f79f76e` and
22 users, 26 conversations, 67 messages, 7 documents, 7 trips and 7 agent runs.
Keep this snapshot and the baseline branch until acceptance. Never use `down -v`.

After moving: repeat regression/build/contracts, scoped docs and security checks;
build/start images in an isolated mock Compose namespace; test proxy streaming,
disconnects, restart recovery, health and restore integrity. Rebuild the existing
local application only after isolated verification. No remote release is authorized.
Record unavailable hardware and external staging/security/privacy acceptance as
pending; distinguish verified software from a verified production release.

Rollback uses the baseline in an isolated checkout and previous images with the
unchanged Compose namespace/volume and compatible schema. Do not use hard reset,
force checkout or destructive DB downgrade on the working migration. Restore into
a new database for deliberate recovery, never overwrite the live database.
