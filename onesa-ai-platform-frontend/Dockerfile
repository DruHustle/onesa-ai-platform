FROM node:24.21.0-alpine@sha256:ebfe2f90462722a7a4de65e91990e97fe0d401c70e0e762c5b53302f905ec1c1 AS build
WORKDIR /frontend/apps/chat
COPY apps/chat/package*.json ./
RUN --mount=type=cache,id=onesa-ai-platform-npm,target=/root/.npm \
    npm ci --prefer-offline --no-audit --no-fund --fetch-retries=2 \
    --fetch-retry-mintimeout=2000 --fetch-retry-maxtimeout=10000 --fetch-timeout=60000
COPY apps/chat ./
COPY packages /frontend/packages
ENV NEXT_TELEMETRY_DISABLED=1
ARG NEXT_PUBLIC_ONESA_DOCUMENTATION_URL=http://localhost:3200
ARG NEXT_PUBLIC_ONESA_ENGINEERING_DOCUMENTATION_URL=http://localhost:3201
ENV NEXT_PUBLIC_ONESA_DOCUMENTATION_URL=$NEXT_PUBLIC_ONESA_DOCUMENTATION_URL NEXT_PUBLIC_ONESA_ENGINEERING_DOCUMENTATION_URL=$NEXT_PUBLIC_ONESA_ENGINEERING_DOCUMENTATION_URL
RUN npm run build

FROM node:24.21.0-alpine@sha256:ebfe2f90462722a7a4de65e91990e97fe0d401c70e0e762c5b53302f905ec1c1 AS runtime
RUN apk upgrade --no-cache zlib
WORKDIR /app
RUN rm -rf /usr/local/lib/node_modules/npm /opt/yarn-* && rm -f /usr/local/bin/npm /usr/local/bin/npx /usr/local/bin/yarn /usr/local/bin/yarnpkg
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 HOSTNAME=0.0.0.0 PORT=3000 ONESA_API_URL=http://api:8000
COPY --from=build --chown=node:node /frontend/apps/chat/.next/standalone ./
COPY --from=build --chown=node:node /frontend/apps/chat/.next/static ./apps/chat/.next/static
USER node
EXPOSE 3000
HEALTHCHECK --interval=15s --timeout=6s --start-period=20s --retries=5 CMD node -e "fetch('http://127.0.0.1:3000/health').then(r=>{if(!r.ok)process.exit(1)}).catch(()=>process.exit(1))"
CMD ["node", "apps/chat/server.js"]
