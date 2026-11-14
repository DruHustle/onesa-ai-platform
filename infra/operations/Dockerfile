FROM pgvector/pgvector:pg16@sha256:7b822b0aac60967beb1ea5e576b8602c94c300a157d187f385ae3e0da199b90a
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-venv && rm -rf /var/lib/apt/lists/*
COPY requirements.lock /tmp/requirements.lock
RUN python3 -m venv /opt/operations && /opt/operations/bin/pip install --no-cache-dir -r /tmp/requirements.lock && rm /tmp/requirements.lock
ENV PATH=/opt/operations/bin:$PATH PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY worker.py test_worker.py /app/
RUN useradd --uid 10001 --create-home operations && mkdir /backups /state && chown operations:operations /backups /state
USER operations
ENTRYPOINT []
CMD ["python", "/app/worker.py"]
HEALTHCHECK --interval=15s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:9000/health',timeout=2)"
