# Developer quickstart

Use the approved public checkout and supported `main` ref. From the parent directory
where you keep projects:

```bash
git clone --branch main --single-branch https://github.com/DruHustle/onesa-ai-platform.git
cd onesa-ai-platform
```

All commands below run from this repository root. For a reproducible review, record
`git rev-parse HEAD`; a moving branch name alone is not a release identity.

## Docker-only application startup

Install Docker Engine/Desktop with the Compose v2 plugin, Python 3.11 (for bootstrap)
and Make. Docker builds contain the application runtimes; a host Node installation
is not needed for this path. Start Docker before running:

```bash
python3 scripts/bootstrap_env.py
make up
docker compose ps
curl --fail "${ONESA_PUBLIC_ORIGIN:-http://localhost:3100}/health"
```

Bootstrap creates a mode-600 local `.env` and refuses to overwrite an existing file.
On an existing checkout, keep that file and skip bootstrap. Never replace working
configuration or reuse production credentials. Wait for `api` and `chat` to become
healthy; inspect `docker compose logs --tail=80 migrate api chat` if readiness fails.

Open **http://localhost:3100**. This is the host default in `bootstrap_env.py` and
Compose's `127.0.0.1:${ONESA_CHAT_PORT:-3100}:3000` mapping; container port 3000 is not
the host URL. If changing the port, update both `ONESA_CHAT_PORT` and
`ONESA_PUBLIC_ORIGIN` in your private local configuration.

If the default port is already occupied, leave that environment running and select
an unused loopback port before `make up`, for example:

```bash
export ONESA_CHAT_PORT=18197
export ONESA_PUBLIC_ORIGIN=http://localhost:18197
make up
curl --fail "${ONESA_PUBLIC_ORIGIN:-http://localhost:3100}/health"
```

Use synthetic development details to register a local account. Fresh development
settings permit registration, clearly label mock inference and use lexical retrieval.
Open Chat and send a synthetic message. No provider account, paid service or model
download is required. This does not prove real hosted inference or grant protected
engineering membership. If registration has been disabled in an existing environment,
follow its approved invitation process rather than changing production settings.

```bash
make down
```

This stops the stack and preserves volumes. Do not add `--volumes` or prune shared data.

## Optional host contributor checks

Install **Node 24**, **Python 3.11** with `venv`, **Make**, and Docker/Compose for
container and PostgreSQL integration checks. Use lockfiles, then run in this order:

```bash
make install
make check
npm --prefix onesa-ai-platform-frontend run ci
make frontend-check
npm ci --ignore-scripts --prefix scripts/contract-tools
make openapi api-client contract-check
```

`make check` depends on the installed Python development environment;
`make frontend-check` depends on the locked frontend install. Neither is a Docker-only
startup command. Default unit checks do not establish PostgreSQL integration success.

Database integration resets synthetic fixtures. Use a **dedicated disposable local
PostgreSQL/pgvector database whose name ends in `_test`**, configured only for testing,
then run `make integration` following the contributor test guide in your approved
checkout. Never point tests at the development application's persistent database,
staging or production. Do not assume a skipped database test passed.

See [troubleshooting](troubleshooting.md) and [tutorials](tutorials.md).
