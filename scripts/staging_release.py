"""Controlled empty-database initialization and configuration of the existing staging API."""

import json
import os
import secrets
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

from alembic import command
from alembic.config import Config
from alembic.util.exc import CommandError
from inspect_hosting import get_json
from psycopg import Error as PsycopgError
from psycopg import sql
from repair_hosting import configuration, write_json
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from staging import DATABASE_HOST, SERVICE_ID, target

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "onesa-ai-platform-backend"
ROLE = "onesa_ai_staging_app"
REVISION = "20261010_capacity"


def save_environment(base, path, token, settings, existing):
    """Preserve unrelated keys, omit absent optional values and bound transient retries."""
    for key, value in settings.items():
        if existing.get(key, "") == value:
            continue
        method = "PUT" if value else "DELETE"
        for attempt in range(4):
            status = write_json(
                base,
                path + "/env-vars/" + key,
                token,
                {"value": value} if value else {},
                method,
            )
            if status in ({200, 201} if value else {204}):
                break
            if status not in {0, 429, 500, 503} or attempt == 3:
                print(
                    json.dumps({"setting_key": key, "save_http_status": status}),
                    flush=True,
                )
                raise ValueError(f"Staging setting {key} save failed (HTTP {status})")
            time.sleep(2 ** (attempt + 1))


def migration_url(raw):
    url = make_url(raw)
    if (
        url.host != DATABASE_HOST.replace("-pooler", "")
        or url.database != "neondb"
        or url.drivername not in {"postgresql", "postgres", "postgresql+psycopg"}
        or url.username != "neondb_owner"
        or url.query.get("sslmode") not in {"require", "verify-full"}
        or url.query.get("channel_binding") != "require"
    ):
        raise ValueError("Unverified direct staging migration connection")
    return url.set(drivername="postgresql+psycopg")


def verified_preview():
    origin = Path("/tmp/vercel-staging-url.txt").read_text().strip()
    parsed = urlsplit(origin)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or not parsed.hostname.endswith(".vercel.app")
        or parsed.username
        or parsed.password
        or parsed.port
        or parsed.path
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Invalid actual Preview origin")
    token = os.environ["VERCEL_TOKEN"]
    from urllib.parse import urlencode

    query = "?" + urlencode({"teamId": os.environ["VERCEL_ORG_ID"]})
    deployment, status = get_json(
        "https://api.vercel.com/v13/", "deployments/" + parsed.hostname + query, token
    )
    metadata = deployment.get("meta", {})
    if (
        status != 200
        or deployment.get("readyState") != "READY"
        or deployment.get("projectId") != os.environ["VERCEL_PROJECT_ID"]
        or deployment.get("target") == "production"
        or metadata.get("githubCommitRef") != "staging"
        or metadata.get("githubCommitSha") != os.environ["GITHUB_SHA"]
    ):
        raise ValueError("Preview identity or revision is unverified")
    return origin


def initialize(url, environment):
    """Preserve existing data; bootstrap only an empty, identified staging database."""
    engine = create_engine(
        url,
        pool_size=1,
        max_overflow=0,
        connect_args={"connect_timeout": 10, "prepare_threshold": None},
    )
    sys.path.insert(0, str(BACKEND))
    os.environ["ONESA_DATABASE_URL"] = url.render_as_string(hide_password=False)
    with engine.begin() as connection:
        if not connection.connection.driver_connection.pgconn.ssl_in_use:
            raise ValueError("Migration client TLS is required")
        if connection.scalar(text("SELECT current_database()")) != "neondb":
            raise ValueError("Unexpected migration database")
        connection.execute(text("SET LOCAL statement_timeout = '60s'"))
        connection.execute(text("SET LOCAL lock_timeout = '5s'"))
        count = connection.scalar(
            text(
                "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'"
            )
        )
        exists = connection.scalar(
            text("SELECT EXISTS(SELECT 1 FROM pg_roles WHERE rolname=:role)"),
            {"role": ROLE},
        )
        if count:
            # A retry may reuse only our already-completed bootstrap and saved role.
            revision = connection.scalar(
                text("SELECT version_num FROM public.alembic_version")
            )
            if revision != REVISION or not exists:
                raise ValueError(
                    "Existing staging data preserved; bootstrap requires review"
                )
            runtime = make_url(environment.get("ONESA_DATABASE_URL", ""))
            if (
                revision != REVISION
                or not exists
                or runtime.username != ROLE
                or runtime.host != DATABASE_HOST
            ):
                raise ValueError(
                    "Existing staging data preserved; bootstrap requires review"
                )
            return runtime.set(drivername="postgresql+psycopg")
        if exists:
            raise ValueError("Existing runtime role preserved; owner review required")
        if not connection.scalar(
            text("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname='vector')")
        ):
            raise ValueError("Required vector extension is not installed")
        cfg = Config(str(BACKEND / "alembic.ini"))
        cfg.attributes["connection"] = connection
        command.upgrade(cfg, "head")
        if (
            connection.scalar(text("SELECT version_num FROM public.alembic_version"))
            != REVISION
        ):
            raise ValueError("Unexpected migrated schema")
        password = secrets.token_urlsafe(48)
        driver = connection.connection.driver_connection
        driver.execute(
            sql.SQL(
                "CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS PASSWORD {}"
            ).format(sql.Identifier(ROLE), sql.Literal(password))
        )
        for statement in [
            "GRANT CONNECT ON DATABASE neondb TO {}",
            "GRANT USAGE ON SCHEMA public TO {}",
            "REVOKE CREATE ON SCHEMA public FROM {}",
            "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {}",
            "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {}",
            "REVOKE INSERT, UPDATE, DELETE, TRUNCATE, TRIGGER ON public.alembic_version FROM {}",
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {}",
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO {}",
        ]:
            driver.execute(sql.SQL(statement).format(sql.Identifier(ROLE)))
    engine.dispose()
    return url.set(host=DATABASE_HOST, username=ROLE, password=password)


def main():
    phase = "identity-and-preview-validation"
    try:
        service, environment = target()
        if (
            service.get("serviceDetails", {}).get(
                "runtime", service.get("serviceDetails", {}).get("env")
            )
            != "docker"
            or service.get("serviceDetails", {}).get("plan") != "free"
        ):
            raise ValueError("Existing free staging Docker service required")
        origin = verified_preview()
        url = migration_url(os.environ.get("STAGING_MIGRATION_DATABASE_URL", ""))
        if (
            environment.get("ONESA_MODEL_API_KEY")
            or environment.get("ONESA_EMBEDDING_API_KEY")
            or environment.get("ONESA_MAIL_PROVIDER", "disabled") != "disabled"
        ):
            raise ValueError("Existing dependency configuration preserved for review")
        token = os.environ["RENDER_API_KEY"]
        base, path = "https://api.render.com/v1/", "services/" + SERVICE_ID
        if write_json(base, path, token, {"autoDeployTrigger": "off"}, "PATCH") != 200:
            raise ValueError("Could not pause staging auto-deploy")
        paused, status = get_json(base, path, token)
        if status != 200 or not (
            paused.get("autoDeployTrigger") == "off" or paused.get("autoDeploy") == "no"
        ):
            raise ValueError("Staging auto-deploy pause not verified")
        phase = "transactional-database-initialization"
        runtime = initialize(url, environment)
        settings = {
            "ONESA_ENVIRONMENT": "staging",
            "ONESA_DATABASE_URL": runtime.render_as_string(hide_password=False),
            "ONESA_PUBLIC_ORIGIN": origin,
            "ONESA_SECURE_COOKIES": "true",
            "ONESA_METRICS_TOKEN": environment.get("ONESA_METRICS_TOKEN")
            or secrets.token_urlsafe(48),
            "ONESA_REGISTRATION_MODE": "invitation",
            "ONESA_ACCESS_OPERATOR_USER_IDS": environment.get(
                "ONESA_ACCESS_OPERATOR_USER_IDS", "[]"
            ),
            "ONESA_AUTH_HASH_CONCURRENCY": "1",
            "ONESA_KNOWLEDGE_UPLOAD_CONCURRENCY": "1",
            "ONESA_MODEL_GLOBAL_CONCURRENCY": "1",
            "ONESA_MODEL_USER_CONCURRENCY": "1",
            "ONESA_MODEL_BACKEND": "ollama",
            "ONESA_MODEL_NAME": "qwen3:4b-instruct-2507-q4_K_M",
            "ONESA_MODEL_BASE_URL": "",
            "ONESA_MODEL_API_KEY": "",
            "ONESA_EMBEDDING_BACKEND": "http",
            "ONESA_EMBEDDING_NAME": "Qwen/Qwen3-Embedding-0.6B",
            "ONESA_EMBEDDING_REVISION": "97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3:qwen-retrieval-v1",
            "ONESA_EMBEDDING_QUERY_INSTRUCTION": "Given a user question, retrieve relevant document passages that answer the question",
            "ONESA_EMBEDDING_BASE_URL": "",
            "ONESA_EMBEDDING_API_KEY": "",
            "ONESA_MAIL_PROVIDER": "disabled",
        }
        phase = "private-staging-environment-save"
        save_environment(base, path, token, settings, environment)
        phase = "staging-runtime-permissions"
        from app.database import make_engine

        runtime_engine = make_engine(runtime.render_as_string(hide_password=False))
        with runtime_engine.connect() as connection:
            if not connection.connection.driver_connection.pgconn.ssl_in_use:
                raise ValueError("Runtime client TLS required")
            privileged = connection.scalar(
                text(
                    "SELECT rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls OR has_schema_privilege(current_user, 'public', 'CREATE') OR has_table_privilege(current_user, 'public.alembic_version', 'INSERT,UPDATE,DELETE,TRUNCATE,TRIGGER') OR EXISTS(SELECT 1 FROM pg_auth_members WHERE member=pg_roles.oid) FROM pg_roles WHERE rolname=current_user"
                )
            )
            if (
                privileged is not False
                or connection.scalar(
                    text("SELECT version_num FROM public.alembic_version")
                )
                != REVISION
            ):
                raise ValueError("Runtime permissions or schema failed validation")
        runtime_engine.dispose()
        phase = "staging-service-layout"
        desired = configuration(False, False)
        desired["branch"] = "staging"
        desired["serviceDetails"]["envSpecificDetails"]["dockerCommand"] = ""
        if write_json(base, path, token, desired, "PATCH") != 200:
            raise ValueError("Staging service layout update failed")
        updated, current = target()
        if (
            any(current.get(key, "") != value for key, value in settings.items())
            or updated.get("branch") != "staging"
        ):
            raise ValueError("Staging configuration readback failed")
        print(
            json.dumps(
                {
                    "service_id": SERVICE_ID,
                    "frontend_origin": origin,
                    "schema_revision": REVISION,
                    "runtime_role": ROLE,
                    "staging_configuration_verified": True,
                    "production_modified": False,
                }
            )
        )
    except (
        SQLAlchemyError,
        PsycopgError,
        CommandError,
        ValueError,
        KeyError,
        OSError,
        RuntimeError,
        TypeError,
    ) as error:
        # No DBAPI errors, SQL parameters, credentials or provider bodies enter logs.
        raise SystemExit(
            f"Staging initialization/configuration failed during {phase} ({type(error).__name__}); inspect scoped provider settings privately; existing data is preserved"
        ) from None


if __name__ == "__main__":
    main()
