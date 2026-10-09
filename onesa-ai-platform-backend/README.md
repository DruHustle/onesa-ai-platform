# Onesa backend

The existing modular FastAPI `app` package, migrations and tests are preserved here.
Run `make install check test` with Python 3.11; `make run` binds port 8000 to loopback.
An explicitly isolated `ONESA_TEST_DATABASE_URL` ending `_test` enables DB tests.
`docker build -t onesa-api:local .` builds an independent non-root runtime image.
Set private `ONESA_DATABASE_URL`, model and embedding settings at runtime. Expose the
API through a same-origin TLS ingress; publish no database or inference service ports.
Alembic is a separate owner-role job; production API uses a restricted CRUD role.

Training and evaluation remain separate optional workloads in `training` and
`evaluation`; their packages/requirements are preserved and excluded from the API
runtime image. From the parent project use `PYTHONPATH=onesa-ai-platform-backend`
for their module commands, preserving root `data` artifact locations. No training or
model download happens at application startup. PDF parsing uses a secret-free
resource-limited subprocess; stricter dedicated worker confinement still requires
host security qualification. All user content and embeddings remain in PostgreSQL.
