# Onesa frontend

Chat, Knowledge, Agents and Travel remain one Next.js application in `apps/chat`.
The public/internal Docusaurus application remains in `apps/docs`; its source and
export policy, private gateways and generation tools stay at the parent project.
Reusable browser API transport and generated OpenAPI types live in `packages/api-client`.

Use Node 24 and `npm run ci`, `npm run typecheck`, `npm run lint`, `npm run build`.
`ONESA_API_URL=http://127.0.0.1:8000 npm run dev` starts chat on port 3100.
`docker build -t onesa-chat:local .` builds this directory independently.
The runtime image uses `ONESA_API_URL=http://api:8000`; configure that private server
origin when deploying independently. API/inference credentials are never browser config.
The BFF forwards cookie/CSRF/origin headers and streaming bodies without buffering.
Production ingress can route `/api/v1/*` directly to the backend on the same origin.
Changing the private backend origin does not require rebuilding browser JavaScript.

Public documentation URL variables are build-time navigation links. See the parent
Makefile for classified generation, asset/PDF builds and protected delivery.
Existing security backports remain at `../packages/security`, with portable archives
inside the docs app. No redundant travel/admin application is created.
