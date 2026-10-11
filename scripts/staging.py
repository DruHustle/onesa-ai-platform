"""Scoped AI staging diagnostics; never print credentials or provider response bodies."""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlencode

from configuration_inventory import REPOSITORY, public_origin, values
from inspect_hosting import get_json, safe_commit, startup_override
from repair_hosting import write_json
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


def database_probe(environment, *, direct=False):
    raw = environment.get("ONESA_DATABASE_URL", "")
    validation = {"secret_configured": bool(raw), "url_parsed": False}
    try:
        url = make_url(raw)
        validation.update(
            {
                "url_parsed": True,
                "expected_host_matches": url.host
                == (DATABASE_HOST.replace("-pooler", "") if direct else DATABASE_HOST),
                "pooled_host_supplied": url.host == DATABASE_HOST,
                "database_name_matches": url.database == "neondb",
                "driver_supported": url.drivername
                in {"postgresql", "postgres", "postgresql+psycopg"},
                "tls_required": url.query.get("sslmode") in {"require", "verify-full"},
                "channel_binding_required": url.query.get("channel_binding")
                == "require",
            }
        )
        if (
            url.host
            != (DATABASE_HOST.replace("-pooler", "") if direct else DATABASE_HOST)
            or url.database != "neondb"
            or url.drivername not in {"postgresql", "postgres", "postgresql+psycopg"}
            or url.query.get("sslmode") not in {"require", "verify-full"}
            or url.query.get("channel_binding") != "require"
        ):
            raise ValueError(
                "Unexpected staging database identity or TLS configuration"
            )
        url = url.set(drivername="postgresql+psycopg")
        if direct:
            engine = create_engine(
                url,
                connect_args={"connect_timeout": 10, "prepare_threshold": None},
                pool_size=1,
                max_overflow=0,
            )
        else:
            sys.path.insert(
                0,
                str(Path(__file__).resolve().parents[1] / "onesa-ai-platform-backend"),
            )
            from app.database import make_engine

            engine = make_engine(url.render_as_string(hide_password=False))
        with engine.connect() as connection, connection.begin():
            connection.execute(text("SET TRANSACTION READ ONLY"))
            if direct:
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
                "application_pool_configuration_tested": not direct,
                "statement_timeout": connection.scalar(text("SHOW statement_timeout")),
                "database_identity_matches": True,
                "tls_enabled_on_server_connection": bool(tls),
                "client_tls_enabled": bool(
                    connection.connection.driver_connection.pgconn.ssl_in_use
                ),
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
            "configuration_checks": validation,
            "details": "Inspect target, URL syntax, rotated credentials, TLS and provider access privately",
        }


def configure_preview(service):
    """Add only a staging-branch Preview variable, preserving all other scopes."""
    origin = public_origin(service.get("serviceDetails", {}).get("url"))
    if origin != "https://onesa-ai-platform-backend-staging.onrender.com":
        raise SystemExit("Staging backend origin could not be verified")
    project = os.environ.get("VERCEL_PROJECT_ID", "")
    team = os.environ.get("VERCEL_ORG_ID", "")
    token = os.environ.get("VERCEL_TOKEN", "")
    if not token or not re.fullmatch(r"prj_[A-Za-z0-9]+", project):
        raise SystemExit("Vercel project credentials are unavailable")
    query = "?" + urlencode({"teamId": team}) if team.startswith("team_") else ""
    path = "projects/" + project
    base = "https://api.vercel.com/v9/"
    metadata, status = get_json(base, path + query, token)
    link = metadata.get("link", {})
    if (
        status != 200
        or link.get("org") != "DruHustle"
        or link.get("repo") != "onesa-ai-platform"
        or link.get("productionBranch") != "main"
        or metadata.get("rootDirectory") != "onesa-ai-platform-frontend/apps/chat"
        or (metadata.get("ssoProtection") or {}).get("deploymentType")
        not in {
            "all",
            "all_except_custom_domains",
            "preview",
            "prod_deployment_urls_and_all_previews",
        }
    ):
        raise SystemExit("Protected staging Preview project identity is unverified")
    response, status = get_json(base, path + "/env" + query, token)
    if status != 200 or not isinstance(response.get("envs"), list):
        raise SystemExit("Vercel environment inventory unavailable")
    desired = {
        "ONESA_API_URL": origin,
        "NEXT_PUBLIC_ONESA_DOCUMENTATION_URL": "https://docs.onesa.eu",
    }
    missing = []
    for key, value in desired.items():
        scoped = [
            entry
            for entry in response["envs"]
            if entry.get("key") == key
            and entry.get("gitBranch") == "staging"
            and "preview" in entry.get("target", [])
        ]
        if scoped:
            if (
                len(scoped) != 1
                or scoped[0].get("value") != value
                or scoped[0].get("target") != ["preview"]
            ):
                raise SystemExit(
                    "Existing staging variable conflicts; preserved for review"
                )
        else:
            missing.append((key, value))
    for key, value in missing:
        status = write_json(
            "https://api.vercel.com/v10/",
            path + "/env" + query,
            token,
            {
                "key": key,
                "value": value,
                "type": "plain",
                "target": ["preview"],
                "gitBranch": "staging",
            },
            "POST",
        )
        if status not in {200, 201}:
            raise SystemExit(
                "Staging Preview variable update failed; HTTP " + str(status)
            )
    response, status = get_json(base, path + "/env" + query, token)
    verified = status == 200 and all(
        any(
            entry.get("key") == key
            and entry.get("gitBranch") == "staging"
            and entry.get("target") == ["preview"]
            and entry.get("value") == value
            for entry in response.get("envs", [])
        )
        for key, value in desired.items()
    )
    if not verified:
        raise SystemExit("Staging Preview variable readback failed")
    return {
        "branch": "staging",
        "scope": "preview",
        "readback_verified": True,
        "deployment_requested": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action",
        choices=["inspect", "database-probe", "migration-probe", "configure-preview"],
    )
    action = parser.parse_args().action
    service, environment = target()
    report = {
        "staging_service_id": SERVICE_ID,
        "staging_backend_origin": public_origin(
            service.get("serviceDetails", {}).get("url")
        ),
        "production_modified": False,
    }
    if action in {"database-probe", "migration-probe"}:
        if action == "migration-probe":
            environment = {
                "ONESA_DATABASE_URL": os.environ.get(
                    "STAGING_MIGRATION_DATABASE_URL", ""
                )
            }
        report["database"] = database_probe(
            environment, direct=action == "migration-probe"
        )
        report["database_role_scope"] = (
            "migration" if action == "migration-probe" else "runtime"
        )
    elif action == "configure-preview":
        report["frontend"] = configure_preview(service)
    else:
        report["configured_keys"] = sorted(environment)
        details = service.get("serviceDetails", {})
        runtime = details.get("envSpecificDetails", {})
        report["runtime"] = details.get("runtime", details.get("env"))
        report["docker_command_mode"] = startup_override(runtime.get("dockerCommand"))
        report["health_check_path"] = details.get("healthCheckPath")
        deploys, status = get_json(
            "https://api.render.com/v1/",
            "services/" + SERVICE_ID + "/deploys?limit=1",
            os.environ.get("RENDER_API_KEY", ""),
        )
        if status == 200 and isinstance(deploys, list) and deploys:
            deploy = deploys[0].get("deploy", deploys[0])
            report["latest_deployment_commit"] = safe_commit(
                deploy.get("commit", {}).get("id")
            )
    print(json.dumps(report, indent=2))
    if (
        action in {"database-probe", "migration-probe"}
        and report["database"]["connection"] != "PASS"
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
