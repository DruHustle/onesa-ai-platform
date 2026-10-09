# Independent backend developer entrypoints; use a local venv or the preserved root venv.
PYTHON := $(if $(wildcard .venv/bin/python),.venv/bin/python,../.venv/bin/python)
.PHONY: install check test run image
install:
	python3 -m venv .venv
	.venv/bin/python -m pip install -r requirements-dev.lock
	.venv/bin/python -m pip install --no-deps --no-build-isolation -e .
check:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .
	$(PYTHON) -m mypy app
test:
	$(PYTHON) -m pytest -q
run:
	$(PYTHON) -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000 --reload
image:
	docker build -t onesa-api:local .
