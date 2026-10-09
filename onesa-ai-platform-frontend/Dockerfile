FROM node:24.21.0-slim@sha256:d6aa754f16b3197301076f047b5def2f02ea1dbbc2ca920407d46d7ec7f87b20 AS build
WORKDIR /frontend/apps/chat
COPY apps/chat/package*.json ./
RUN npm ci
COPY apps/chat ./
COPY packages /frontend/packages
ENV NEXT_TELEMETRY_DISABLED=1
ARG NEXT_PUBLIC_ONESA_DOCUMENTATION_URL=http://localhost:3200
ARG NEXT_PUBLIC_ONESA_ENGINEERING_DOCUMENTATION_URL=http://localhost:3201
ENV NEXT_PUBLIC_ONESA_DOCUMENTATION_URL=$NEXT_PUBLIC_ONESA_DOCUMENTATION_URL NEXT_PUBLIC_ONESA_ENGINEERING_DOCUMENTATION_URL=$NEXT_PUBLIC_ONESA_ENGINEERING_DOCUMENTATION_URL
RUN npm run build

FROM node:24.21.0-slim@sha256:d6aa754f16b3197301076f047b5def2f02ea1dbbc2ca920407d46d7ec7f87b20 AS runtime
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 HOSTNAME=0.0.0.0 PORT=3000 ONESA_API_URL=http://api:8000
COPY --from=build --chown=node:node /frontend/apps/chat/.next/standalone ./
COPY --from=build --chown=node:node /frontend/apps/chat/.next/static ./apps/chat/.next/static
USER node
EXPOSE 3000
HEALTHCHECK --interval=15s --timeout=6s --start-period=20s --retries=5 CMD node -e "fetch('http://127.0.0.1:3000/health').then(r=>{if(!r.ok)process.exit(1)}).catch(()=>process.exit(1))"
CMD ["node", "apps/chat/server.js"]
