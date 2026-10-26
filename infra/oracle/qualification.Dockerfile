# Credential-free owner tool. System Chromium is identified in hosted receipts.
FROM node:24.22.1-alpine@sha256:06d7adf3e0ef61a13f1d28682726366f97a15aa1888c934d3ecec86c33918b53 AS node
FROM python:3.11.17-alpine3.24@sha256:d9368b3a5ac59afea7b5d4f2e2aea0941dbf9fdee9c369c5bec00b98244bc929 AS dependencies
COPY --from=ghcr.io/astral-sh/uv:0.13.0@sha256:cdc6093146eb3ff6a40107b38f008b789e050e77ad87865e381d9917da55a168 /uv /usr/local/bin/uv
COPY onesa-ai-platform-backend/requirements.lock /tmp/requirements.lock
RUN apk upgrade --no-cache && apk add --no-cache build-base libffi-dev && uv pip install --prefix=/install --no-cache -r /tmp/requirements.lock
FROM python:3.11.17-alpine3.24@sha256:d9368b3a5ac59afea7b5d4f2e2aea0941dbf9fdee9c369c5bec00b98244bc929 AS complete
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN apk upgrade --no-cache && apk add --no-cache 'musl>=1.2.6-r3' 'musl-utils>=1.2.6-r3' ca-certificates openssl libffi libstdc++ libseccomp chromium mesa-dri-gallium mesa-vulkan-swrast mesa-egl mesa-gles vulkan-loader tar && rm -rf /usr/local/lib/python3.11/ensurepip /usr/local/lib/python3.11/site-packages/pip* /usr/local/bin/pip*
COPY --from=dependencies /install /usr/local
RUN rm -rf /usr/local/lib/python3.11/site-packages/setuptools* /usr/local/lib/python3.11/site-packages/pkg_resources* /usr/local/lib/python3.11/site-packages/_distutils_hack* /usr/local/lib/python3.11/site-packages/distutils-precedence.pth /usr/local/lib/python3.11/site-packages/wheel*
COPY --from=node /usr/local/bin/node /usr/local/bin/node
WORKDIR /opt/onesa-ai-platform
COPY onesa-ai-platform-frontend/apps/chat/package.json onesa-ai-platform-frontend/apps/chat/package-lock.json ./onesa-ai-platform-frontend/apps/chat/
# npm is a build-only tool. No base npm/yarn code remains in this runtime.
COPY --from=node /usr/local/lib/node_modules/npm /tmp/npm
RUN node /tmp/npm/bin/npm-cli.js ci --ignore-scripts --prefix onesa-ai-platform-frontend/apps/chat && rm -rf /tmp/npm /root/.npm
COPY infra/oracle/system_chromium.cjs /tmp/system_chromium.cjs
RUN node /tmp/system_chromium.cjs && rm /tmp/system_chromium.cjs
COPY scripts ./scripts
COPY onesa-ai-platform-backend/app ./onesa-ai-platform-backend/app
COPY onesa-ai-platform-backend/migrations ./onesa-ai-platform-backend/migrations
COPY onesa-ai-platform-backend/alembic.ini ./onesa-ai-platform-backend/alembic.ini
FROM scratch
COPY --from=complete / /
WORKDIR /opt/onesa-ai-platform
ENV PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
ARG SOURCE_COMMIT
ARG SOURCE_ARCHIVE_SHA256
LABEL org.opencontainers.image.revision=$SOURCE_COMMIT org.onesa.source-archive-sha256=$SOURCE_ARCHIVE_SHA256 org.onesa.browser="Alpine system Chromium"
ENTRYPOINT ["python3","/opt/onesa-ai-platform/scripts/release/oracle_ai_probe.py"]
