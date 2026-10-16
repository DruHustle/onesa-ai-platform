# Prefer the optional repository-local supported Node runtime without changing system tools.
ifneq ($(wildcard data/runtime/node24/bin/node),)
export PATH := $(CURDIR)/data/runtime/node24/bin:$(PATH)
endif

PYTHON := .venv/bin/python
API := onesa-ai-platform-backend

.PHONY: install check test run openapi up down frontend-check training-check
install:
	python3 -m venv .venv
	$(PYTHON) -m pip install --require-hashes -r $(API)/requirements-dev.lock
	$(PYTHON) -m pip install --no-deps --no-build-isolation -e $(API)

check:
	$(PYTHON) -m ruff check scripts infra/operations
	$(PYTHON) -m ruff format --check scripts infra/operations
	cd $(API) && ../.venv/bin/python -m ruff check .
	cd $(API) && ../.venv/bin/python -m ruff format --check .
	cd $(API) && ../.venv/bin/python -m mypy app
	$(MAKE) test

test:
	cd $(API) && ../.venv/bin/python -m pytest -q

run:
	cd $(API) && ../.venv/bin/python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000 --reload

openapi:
	PYTHONPATH=$(API) $(PYTHON) scripts/export_openapi.py

up:
	docker compose up --build -d

down:
	docker compose down

frontend-check:
	npm --prefix onesa-ai-platform-frontend/apps/chat run lint
	npm --prefix onesa-ai-platform-frontend/apps/chat run typecheck
	npm --prefix onesa-ai-platform-frontend/apps/chat run build

training-check:
	cd $(API) && ../.venv/bin/python -m pytest -q tests/test_training.py

.PHONY: integration
integration:
	$(PYTHON) scripts/run_tests.py --postgres

.PHONY: docs-api docs-diagrams docs-pdf docs-assets docs-public docs-internal docs-validate docs-check docs-serve docs-stop docs-screenshots up-docs
docs-api:
	$(MAKE) openapi
	$(PYTHON) scripts/docs/generate.py

docs-diagrams: docs-api
	node scripts/docs/render.mjs

docs-pdf: docs-diagrams
	$(PYTHON) scripts/docs/validate.py --assets

docs-assets: docs-pdf

docs-public: docs-api
	$(PYTHON) scripts/docs/validate.py --staged
	npm --prefix onesa-ai-platform-frontend/apps/docs run build:public

docs-internal: docs-api
	npm --prefix onesa-ai-platform-frontend/apps/docs run build:internal

docs-validate:
	$(PYTHON) scripts/docs/validate.py
	node scripts/docs/visual-acceptance.mjs

docs-check:
	$(PYTHON) -m unittest discover -s scripts/docs -p test_source_policy.py
	$(PYTHON) -m unittest discover -s scripts/docs -p test_visual_policy.py
	$(PYTHON) -m unittest discover -s scripts/docs -p test_pdf_source_links.py
	$(PYTHON) -m unittest discover -s scripts/docs -p test_prepare_cloudflare.py
	npm --prefix onesa-ai-platform-frontend/apps/docs run test:security
	node --test scripts/docs/cloudflare-access.test.mjs
	npm --prefix onesa-ai-platform-frontend/apps/docs run typecheck
	$(PYTHON) -m ruff check scripts/docs
	$(PYTHON) scripts/docs/validate.py

docs-serve:
	$(PYTHON) scripts/docs/service.py start

docs-stop:
	$(PYTHON) scripts/docs/service.py stop

docs-screenshots:
	node scripts/docs/capture.mjs

up-docs:
	docker compose -f compose.yaml -f compose.docs.yaml up --build -d

.PHONY: docs-release-check docs-browser
docs-release-check: docs-check
	npm --prefix onesa-ai-platform-frontend/apps/docs audit --audit-level=low

docs-browser:
	node scripts/docs/verify.mjs

.PHONY: docs-security-pack docs-security-test
docs-security-pack:
	node scripts/docs/pack-security.mjs

docs-security-test:
	npm --prefix onesa-ai-platform-frontend/apps/docs run test:security

.PHONY: api-client contract-check
api-client: openapi
	$(PYTHON) scripts/generate_api_client.py

contract-check:
	$(PYTHON) scripts/generate_api_client.py --check

.PHONY: docs-static-acceptance
docs-static-acceptance:
	node scripts/docs/acceptance.mjs

.PHONY: docs-cloudflare-placeholder docs-cloudflare-package
docs-cloudflare-placeholder:
	python3 scripts/docs/prepare_cloudflare.py --placeholder --output build/cloudflare-docs

# Build/validate the reviewed internal docs first; this target never deploys them.
docs-cloudflare-package:
	$(PYTHON) scripts/docs/prepare_cloudflare.py --output build/cloudflare-docs
