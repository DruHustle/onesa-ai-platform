"""Scoped AI staging diagnostics; never print credentials or provider response bodies."""

import argparse
import json
import os

from configuration_inventory import REPOSITORY, public_origin, values
from inspect_hosting import get_json
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

SERVICE_ID = "srv-db56mju7bikc73950f60"
DATABASE_HOST = "ep-falling-thunder-b9x4ka3b-pooler.c-7.eu-central-1.aws.neon.tech"


def target():
    if (
        os.environ.get("GITHUB_REPOSITORY") != "DruHustle/onesa-ai-platform"
        or os.environ.get("GITHUB_REF") != "refs/heads/staging"
    ):
        raise SystemExit("Only the authorized AI staging branch may run this operation")
    token = os.environ.get("RENDER_API_KEY", "")
    service, status = get_json(
        "https://api.render.com/v1/", "services/" + SERVICE_ID, token
    )
    if (
        status != 200
        or service.get("repo", "").removesuffix(".git").rstrip("/") != REPOSITORY
        or service.get("name") != "onesa-ai-platform-backend_staging"
        or service.get("type") != "web_service"
    ):
        raise SystemExit("Authorized staging service identity could not be verified")
    entries, status = get_json(
        "https://api.render.com/v1/",
        "services/" + SERVICE_ID + "/env-vars?limit=100",
        token,
    )
    if status != 200 or not isinstance(entries, list) or len(entries) >= 100:
        raise SystemExit("Staging environment could not be read completely")
    return service, values(entries, "envVar")


def database_probe(environment):
    raw = environment.get("ONESA_DATABASE_URL", "")
    try:
        url = make_url(raw)
        if (
            url.host != DATABASE_HOST
            or url.database != "neondb"
            or url.drivername not in {"postgresql", "postgres", "postgresql+psycopg"}
            or url.query.get("sslmode") not in {"require", "verify-full"}
            or url.query.get("channel_binding") != "require"
        ):
            raise ValueError(
                "Unexpected staging database identity or TLS configuration"
            )
        url = url.set(drivername="postgresql+psycopg")
        engine = create_engine(
            url,
            connect_args={"connect_timeout": 10, "prepare_threshold": None},
            pool_size=1,
            max_overflow=0,
        )
        with engine.connect() as connection, connection.begin():
            connection.execute(text("SET TRANSACTION READ ONLY"))
            connection.execute(text("SET LOCAL statement_timeout = '10s'"))
            role = connection.execute(
                text(
                    "SELECT rolsuper, rolcreaterole, rolcreatedb, rolbypassrls, (SELECT count(*) FROM pg_auth_members WHERE member=pg_roles.oid) FROM pg_roles WHERE rolname=current_user"
                )
            ).one()
            schema_exists = connection.scalar(
                text("SELECT to_regclass('public.alembic_version') IS NOT NULL")
            )
            revision = (
                connection.scalar(
                    text("SELECT version_num FROM public.alembic_version")
                )
                if schema_exists
                else None
            )
            vector = connection.scalar(
                text("SELECT extversion FROM pg_extension WHERE extname='vector'")
            )
            table_count = connection.scalar(
                text(
                    "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'"
                )
            )
            tls = connection.scalar(
                text("SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()")
            )
            report = {
                "connection": "PASS",
                "read_only": True,
                "driver": "psycopg3",
                "database_identity_matches": True,
                "tls_enabled_on_server_connection": bool(tls),
                "schema_revision": revision
                if revision == "20261010_capacity"
                else "missing_or_not_current",
                "vector_extension_present": bool(vector),
                "public_table_count": table_count,
                "runtime_role_privileged": any(role[:4]) or role[4] > 0,
                "owner_role_used": url.username == "neondb_owner",
                "server_version": str(
                    connection.scalar(text("SHOW server_version"))
                ).split()[0],
            }
        engine.dispose()
        return report
    except (SQLAlchemyError, ValueError, TypeError):
        # DBAPI/SQLAlchemy errors can contain full connection strings and bound credentials.
        return {
            "connection": "FAILED",
            "read_only": True,
            "details": "Inspect target, URL syntax, rotated credentials, TLS and provider access privately",
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["inspect", "database-probe"])
    action = parser.parse_args().action
    service, environment = target()
    report = {
        "staging_service_id": SERVICE_ID,
        "staging_backend_origin": public_origin(
            service.get("serviceDetails", {}).get("url")
        ),
        "production_modified": False,
    }
    if action == "database-probe":
        report["database"] = database_probe(environment)
    else:
        report["configured_keys"] = sorted(environment)
    print(json.dumps(report, indent=2))
    if action == "database-probe" and report["database"]["connection"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
