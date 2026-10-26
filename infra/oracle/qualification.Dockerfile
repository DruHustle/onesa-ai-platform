# Credential-free owner tool build. Not an application image or an Actions runner.
FROM node:24.22.1-trixie-slim@sha256:43b9ba1142b8dcf33fa8f922ca1be85714adc444e0586c7cf7726daaeabc1bea
COPY --from=ghcr.io/astral-sh/uv:0.13.0@sha256:cdc6093146eb3ff6a40107b38f008b789e050e77ad87865e381d9917da55a168 /uv /usr/local/bin/uv
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_PYTHON_DOWNLOADS=never PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends python3 python3-venv ca-certificates openssl libseccomp2 && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/onesa-ai-platform
COPY onesa-ai-platform-backend/requirements.lock /tmp/requirements.lock
RUN uv pip install --system --break-system-packages --no-cache -r /tmp/requirements.lock
COPY onesa-ai-platform-frontend/apps/chat/package.json onesa-ai-platform-frontend/apps/chat/package-lock.json ./onesa-ai-platform-frontend/apps/chat/
RUN npm ci --ignore-scripts --prefix onesa-ai-platform-frontend/apps/chat && ./onesa-ai-platform-frontend/apps/chat/node_modules/.bin/playwright install --with-deps chromium && rm -rf /usr/local/lib/node_modules/npm /usr/local/bin/npm /usr/local/bin/npx /opt/yarn* /usr/local/bin/yarn* /root/.npm
COPY scripts ./scripts
COPY onesa-ai-platform-backend/app ./onesa-ai-platform-backend/app
COPY onesa-ai-platform-backend/migrations ./onesa-ai-platform-backend/migrations
COPY onesa-ai-platform-backend/alembic.ini ./onesa-ai-platform-backend/alembic.ini
ARG SOURCE_COMMIT
ARG SOURCE_ARCHIVE_SHA256
LABEL org.opencontainers.image.revision=$SOURCE_COMMIT org.onesa.source-archive-sha256=$SOURCE_ARCHIVE_SHA256
ENTRYPOINT ["python3","/opt/onesa-ai-platform/scripts/release/oracle_ai_probe.py"]
