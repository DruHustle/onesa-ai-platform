# Owner tool only. Never mount credentials during source builds.
FROM node:24.22.1-trixie-slim@sha256:43b9ba1142b8dcf33fa8f922ca1be85714adc444e0586c7cf7726daaeabc1bea AS node
FROM ubuntu:24.04@sha256:68ee22004a9109b44973313b02ff7b1de250f1de0f5ecb628d73f579aaff33ac AS tool
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends ca-certificates libstdc++6 && rm -rf /var/lib/apt/lists/*
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/npm
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx
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
