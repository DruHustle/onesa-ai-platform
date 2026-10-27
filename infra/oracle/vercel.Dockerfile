# Owner tool only. Never mount credentials during source builds.
FROM node:24.22.1-alpine@sha256:06d7adf3e0ef61a13f1d28682726366f97a15aa1888c934d3ecec86c33918b53 AS tool
# Retry transient upstream fetch failures; each attempt retains signed HTTPS repositories.
RUN for attempt in 1 2 3; do \
      if apk upgrade --no-cache && apk add --no-cache ca-certificates; then break; fi; \
      if [ "$attempt" -eq 3 ]; then exit 1; fi; \
      sleep 2; \
    done
WORKDIR /opt/onesa-vercel-tool
COPY infra/oracle/vercel-tools/package.json infra/oracle/vercel-tools/package-lock.json ./
RUN npm ci --ignore-scripts && npm cache clean --force
COPY infra/oracle/npm-runtime/package.json infra/oracle/npm-runtime/package-lock.json infra/oracle/npm-runtime/upstream.json /opt/npm-runtime/
RUN npm ci --ignore-scripts --prefix /opt/npm-runtime && npm cache clean --force
COPY infra/oracle/prepare_npm.cjs /opt/prepare_npm.cjs
RUN node /opt/prepare_npm.cjs && rm -rf /usr/local/lib/node_modules/npm /opt/yarn* /usr/local/bin/yarn* /root/.npm && ln -s /opt/onesa-npm-code /usr/local/lib/node_modules/npm
FROM scratch
COPY --from=tool / /
ENV PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
LABEL org.onesa.vercel-cli="65.2.0" org.onesa.node="24.22.1"
ENTRYPOINT ["node","/opt/onesa-vercel-tool/node_modules/vercel/dist/index.js"]
