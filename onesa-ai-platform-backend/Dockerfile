FROM python:3.11.14-slim@sha256:c8271b1f627d0068857dce5b53e14a9558603b527e46f1f901722f935b786a39 AS build
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /build
COPY requirements.lock ./
RUN pip install --no-cache-dir --prefix=/install -r requirements.lock setuptools==80.10.2 wheel==0.48.0
COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir setuptools==80.10.2 wheel==0.48.0 && pip install --no-deps --no-build-isolation --prefix=/install .

FROM python:3.11.14-slim@sha256:c8271b1f627d0068857dce5b53e14a9558603b527e46f1f901722f935b786a39 AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY --from=build /install /usr/local
COPY app ./app
COPY alembic.ini ./
COPY migrations ./migrations
RUN useradd --uid 10001 --create-home onesa
USER onesa
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=6s --start-period=20s --retries=5 CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/ready', timeout=5)"
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers", "--no-access-log", "--limit-concurrency", "128", "--timeout-keep-alive", "5", "--timeout-graceful-shutdown", "130"]
