#!/bin/sh
set -eu

# Expand the provider port here, without a quoted shell command in Render settings.
# exec preserves cancellation and graceful shutdown by replacing the shell.
exec python -m uvicorn app.main:create_app --factory --host 0.0.0.0 \
    --port "${PORT:-8000}" --no-proxy-headers --no-access-log \
    --limit-concurrency 128 --timeout-keep-alive 5 --timeout-graceful-shutdown 130
