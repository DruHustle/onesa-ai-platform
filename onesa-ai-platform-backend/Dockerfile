FROM python:3.11.17-alpine3.24@sha256:d9368b3a5ac59afea7b5d4f2e2aea0941dbf9fdee9c369c5bec00b98244bc929 AS build
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_PYTHON_DOWNLOADS=never
COPY --from=ghcr.io/astral-sh/uv:0.13.0@sha256:cdc6093146eb3ff6a40107b38f008b789e050e77ad87865e381d9917da55a168 /uv /usr/local/bin/uv
WORKDIR /build
COPY requirements.lock requirements-build.lock ./
RUN apk upgrade --no-cache && apk add --no-cache 'musl>=1.2.6-r3' 'musl-utils>=1.2.6-r3' && apk add --no-cache --virtual .build-deps build-base libffi-dev
RUN rm -rf /usr/local/lib/python3.11/ensurepip /usr/local/lib/python3.11/site-packages/pip* /usr/local/bin/pip* \
    && uv pip install --system --no-cache -r requirements-build.lock \
    && uv pip install --no-cache --prefix=/install -r requirements.lock
COPY pyproject.toml ./
COPY app ./app
RUN uv build --no-build-isolation --wheel --out-dir /wheelhouse . \
    && uv pip install --no-cache --no-deps --prefix=/install /wheelhouse/*.whl

FROM python:3.11.17-alpine3.24@sha256:d9368b3a5ac59afea7b5d4f2e2aea0941dbf9fdee9c369c5bec00b98244bc929 AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
# The PDF worker installs its BPF filter through libc.prctl on both Linux ABIs.
# Compilation tools stay in the build stage; retain only runtime shared libraries.
RUN apk upgrade --no-cache && apk add --no-cache 'musl>=1.2.6-r3' 'musl-utils>=1.2.6-r3' && apk add --no-cache libffi libstdc++ libseccomp
COPY --from=build /install /usr/local
COPY app ./app
COPY alembic.ini ./
COPY start.sh ./
COPY migrations ./migrations
# Build tooling is not part of the runtime; remove vulnerable vendored copies too.
RUN rm -rf /usr/local/lib/python3.11/ensurepip /usr/local/bin/pip* && adduser -D -u 10001 onesa
RUN mkdir -p /var/lib/onesa/twins && chown 10001:10001 /var/lib/onesa/twins && chmod 700 /var/lib/onesa/twins
RUN rm -rf /usr/local/lib/python3.11/site-packages/setuptools* /usr/local/lib/python3.11/site-packages/pkg_resources* /usr/local/lib/python3.11/site-packages/_distutils_hack* /usr/local/lib/python3.11/site-packages/distutils-precedence.pth /usr/local/lib/python3.11/site-packages/wheel* /usr/local/lib/python3.11/site-packages/pip* \
    && python -c "import importlib.util; assert all(importlib.util.find_spec(n) is None for n in ('pip','setuptools','wheel'))"
USER onesa
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=6s --start-period=20s --retries=5 CMD python -c "import os, urllib.request; urllib.request.urlopen('http://localhost:' + os.environ.get('PORT', '8000') + '/core-ready', timeout=5)"
CMD ["sh", "/app/start.sh"]
