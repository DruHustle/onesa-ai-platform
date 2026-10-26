"""Genuine owner-run AI hosted observations, launched only by the pinned runner.

The private probe context configures observations; it is never release authority.
No Actions variables are manufactured. Credentials and fixture cookies remain in
private pipes/files. Existing accounts are fingerprinted, never modified here.
"""

import argparse
import base64
import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = Path("/private/output")


class Refused(ValueError):
    pass


def require(value, code):
    if not value:
        raise Refused(code)


def private_json(path):
    p = Path(path)
    s = p.lstat()
    require(
        p.is_file()
        and not p.is_symlink()
        and s.st_uid == os.getuid()
        and s.st_mode & 0o077 == 0
        and s.st_size < 128 * 1024,
        "PRIVATE_PROBE_FILE",
    )
    return json.loads(p.read_bytes())


def write(path, value):
    with os.fdopen(
        os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "w"
    ) as f:
        json.dump(value, f)
        f.flush()
        os.fsync(f.fileno())


def runtime(path):
    p = Path(path)
    require(
        p.is_file() and not p.is_symlink() and p.stat().st_mode & 0o077 == 0,
        "PRIVATE_FIXTURE_CONFIGURATION",
    )
    rows = [r for r in p.read_text().splitlines() if r]
    out = dict(r.split("=", 1) for r in rows)
    require(len(out) == len(rows), "CONFIGURATION_SHAPE")
    return out


def provider(config, environment, binding, plan, request):
    # This metadata is produced live by the separately pinned host observer after
    # it verifies the signed ledger. It is observation/configuration, never
    # authorization; oracle_owner cannot import caller PASS files.
    raw = Path("/private/vercel.json").read_bytes()
    require(
        hashlib.sha256(raw).hexdigest() == request["provider_observation_sha256"]
        and config["schema_version"] == 1
        and config["binding"] == binding
        and config["operation_id"] == request["operation_id"]
        and config["environment"] == environment
        and config["provider_token_included"] is False,
        "PINNED_HOST_OBSERVATION_BINDING",
    )
    require(
        timedelta(0)
        <= datetime.now(timezone.utc) - datetime.fromisoformat(config["observed_at"])
        < timedelta(minutes=5),
        "PROVIDER_OBSERVATION_EXPIRED",
    )
    origin = config["origin"]
    require(
        origin == "https://platform.onesa.eu"
        if environment == "production"
        else re.fullmatch(
            r"https://onesa-ai-platform-git-staging-[a-z0-9-]+\.vercel\.app", origin
        ),
        "APPROVED_PROVIDER_ORIGIN",
    )
    return origin, config["bypass"], config["provider"]


def served_backend_identity(origin, bypass, expected):
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *_a, **_kw):
            return None

    headers = {"User-Agent": "OnesaOwnerOracleRelease/1.0"}
    if bypass:
        headers["x-vercel-protection-bypass"] = bypass
    with urllib.request.build_opener(NoRedirect()).open(
        urllib.request.Request(origin + "/health", headers=headers), timeout=20
    ) as response:
        data = response.read(4097)
        require(len(data) <= 4096, "SERVED_IDENTITY_BOUND")
        actual = json.loads(data)
    require(actual == expected, "FRONTEND_DOES_NOT_REACH_INTENDED_API_INSTANCE")
    return actual


def fixture_engine(settings, environment, expected_revision):
    sys.path.insert(0, str(ROOT / "onesa-ai-platform-backend"))
    from fixture_lifecycle import database_tls_query
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url

    uri = make_url(settings["ONESA_DATABASE_URL"]).set(drivername="postgresql+psycopg")
    require(settings["ONESA_ENVIRONMENT"] == environment, "FIXTURE_ENVIRONMENT")
    engine = create_engine(
        uri.set(query=database_tls_query(dict(uri.query))),
        pool_size=1,
        max_overflow=0,
        connect_args={"connect_timeout": 10, "prepare_threshold": None},
    )
    with engine.connect() as db, db.begin():
        db.execute(text("SET TRANSACTION READ ONLY"))
        db.execute(text("SET LOCAL statement_timeout='5s'"))
        name, user = db.execute(text("SELECT current_database(),current_user")).one()
        require(name == "neondb" and user == uri.username, "FIXTURE_DATABASE_IDENTITY")
        unsafe = db.scalar(
            text(
                "SELECT rolsuper OR rolcreaterole OR rolcreatedb OR rolreplication OR rolbypassrls OR has_schema_privilege(current_user,'public','CREATE') OR has_table_privilege(current_user,'public.alembic_version','INSERT,UPDATE,DELETE,TRUNCATE,TRIGGER') OR EXISTS(SELECT 1 FROM pg_auth_members WHERE member=pg_roles.oid) FROM pg_roles WHERE rolname=current_user"
            )
        )
        require(unsafe is False, "RUNTIME_ROLE_MUST_REMAIN_RESTRICTED")
        require(
            db.scalar(text("SELECT version_num FROM alembic_version"))
            == expected_revision,
            "EXACT_RELEASE_SCHEMA_REQUIRED",
        )
    return engine


def fingerprints(engine, exclude=()):
    from app.models import AccessGrant, User
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    result = {}
    with Session(engine) as db:
        for user in db.scalars(select(User).order_by(User.id).limit(1001)):
            require(len(result) < 1000, "PRESERVATION_ACCOUNT_BOUND")
            if str(user.id) in exclude:
                continue
            grant = db.get(AccessGrant, user.id)
            value = [
                str(user.id),
                user.email,
                user.password_hash,
                user.display_name,
                user.status,
                grant.expires_at.isoformat() if grant else None,
            ]
            result[str(user.id)] = hashlib.sha256(
                json.dumps(value).encode()
            ).hexdigest()
    result["__persistent_tables__"] = persistent_fingerprints(engine, exclude)
    return result


def persistent_fingerprints(engine, exclude):
    # Hash in PostgreSQL; customer document/message text never leaves the DB.
    # Only this operation's two owners are excluded. Existing sessions, MFA,
    # content and grants remain in the preservation baseline. Capacity/rate
    # counters are transient controls, not persisted user work.
    from app.models import Base
    from sqlalchemy import text

    def ownership(table, seen=()):
        if table.name == "users":
            return []
        if table.name in seen:
            return None
        for fk in sorted(
            table.foreign_keys, key=lambda f: 0 if f.column.table.name == "users" else 1
        ):
            path = ownership(fk.column.table, (*seen, table.name))
            if path is not None:
                return [(fk.parent.name, fk.column.table.name, fk.column.name), *path]
        return None

    result = {}
    owners = list(exclude)
    with engine.connect() as db, db.begin():
        db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
        db.execute(text("SET LOCAL statement_timeout='10s'"))
        names = (
            db.execute(
                text(
                    "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
                )
            )
            .scalars()
            .all()
        )
        require(len(names) <= 100, "PRESERVATION_TABLE_BOUND")
        for name in names:
            if name in ["alembic_version", "rate_buckets", "model_leases"]:
                continue
            table = Base.metadata.tables.get(name)
            require(table is not None, "UNKNOWN_PERSISTENT_TABLE")
            path = ownership(table)
            require(path is not None, "UNKNOWN_PERSISTENT_OWNERSHIP")
            joins = ""
            last = "t0"
            for n, (child, parent, column) in enumerate(path):
                following = "t" + str(n + 1)
                joins += (
                    ' JOIN public."'
                    + parent
                    + '" '
                    + following
                    + " ON "
                    + last
                    + '."'
                    + child
                    + '"='
                    + following
                    + '."'
                    + column
                    + '"'
                )
                last = following
            where = " WHERE NOT (" + last + ".id=ANY(CAST(:owners AS uuid[])))"
            source = ' FROM public."' + name + '" t0' + joins + where
            count, size = db.execute(
                text("SELECT count(*),coalesce(sum(pg_column_size(t0)),0)" + source),
                {"owners": owners},
            ).one()
            require(
                count <= 10000 and size <= 64 * 1024 * 1024,
                "PRESERVATION_ROW_OR_BYTE_BOUND",
            )
            digest = db.scalar(
                text(
                    "SELECT encode(sha256(convert_to(coalesce(string_agg(to_jsonb(t0)::text,E'\\n' ORDER BY to_jsonb(t0)::text),''),'UTF8')),'hex')"
                    + source
                ),
                {"owners": owners},
            )
            result[name] = {"count": count, "sha256": digest}
    return result


def create_fixtures(engine, ci_id):
    from app.models import AccessGrant, User, now
    from argon2 import PasswordHasher
    from sqlalchemy.orm import Session

    users = []
    with Session(engine) as db:
        for _ in range(2):
            password = secrets.token_urlsafe(32)
            user = User(
                email=f"release-audit-{ci_id}-{secrets.token_hex(12)}@example.com",
                display_name="Owned synthetic release verification",
                password_hash=PasswordHasher().hash(password),
            )
            db.add(user)
            db.flush()
            db.add(AccessGrant(user_id=user.id, expires_at=now() + timedelta(hours=2)))
            users.append(
                {"id": str(user.id), "email": user.email, "password": password}
            )
        db.commit()
    return users


def disable_fixtures(engine, users, before, ci_id):
    from app.models import AccessGrant, AuthSession, User, now
    from sqlalchemy import select, update
    from sqlalchemy.orm import Session

    require(len(users) == 2, "OWNED_FIXTURE_COUNT")
    with Session(engine) as db:
        for user in users:
            require(
                user["id"] not in before
                and re.fullmatch(
                    f"release-audit-{ci_id}-[a-f0-9]{{24}}@example.com", user["email"]
                ),
                "OWNED_FIXTURE_IDENTITY",
            )
            row = db.scalar(
                select(User)
                .where(User.id == UUID(user["id"]), User.email == user["email"])
                .with_for_update()
            )
            require(row is not None, "FIXTURE_IDENTITY_CHANGED")
            row.status = "disabled"
            db.execute(
                update(AuthSession)
                .where(AuthSession.user_id == row.id)
                .values(revoked_at=now())
            )
            db.execute(
                update(AccessGrant)
                .where(AccessGrant.user_id == row.id)
                .values(expires_at=now())
            )
        db.commit()


def run_node(script, env, *, args=(), timeout=1200):
    r = subprocess.run(
        ["/usr/local/bin/node", str(ROOT / script), *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    require(r.returncode == 0, "PINNED_BROWSER_PROBE_FAILED")


def export_owned_restore(engine, users, binding, operation, profile="twins"):
    from oracle_twin_restore import CYBER_TABLES, TABLES
    from sqlalchemy import text

    owners = [u["id"] for u in users]
    tables = {}
    with engine.connect() as db, db.begin():
        db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
        require(profile in ["twins", "cybersecurity"], "RESTORE_EXPORT_PROFILE")
        for table in CYBER_TABLES if profile == "cybersecurity" else TABLES:
            if table == "users":
                where = "id = ANY(CAST(:owners AS uuid[]))"
            elif table in ["twin_readings", "twin_events"]:
                where = "asset_id IN (SELECT id FROM twin_assets WHERE user_id = ANY(CAST(:owners AS uuid[])))"
            else:
                where = "user_id = ANY(CAST(:owners AS uuid[]))"
            rows = (
                db.execute(
                    text(
                        "SELECT to_jsonb(t) FROM "
                        + table
                        + " t WHERE "
                        + where
                        + " ORDER BY id"
                    ),
                    {"owners": owners},
                )
                .scalars()
                .all()
            )
            require(len(rows) <= 1000, "RESTORE_FIXTURE_ROW_BOUND")
            tables[table] = rows
    bundle = {
        "binding": binding,
        "operation_id": operation,
        "scope": "new-owned-release-fixtures-only",
        "tables": tables,
        "profile": profile,
    }
    from oracle_twin_restore import validate

    validate(bundle, binding, operation)
    # Export only these two fixtures' rows. The pinned host copies their exact
    # referenced blobs; this browser container never mounts other owners' files.
    require(len(json.dumps(bundle)) <= 16 * 1024 * 1024, "RESTORE_FIXTURE_BOUND")
    write(OUTPUT / "restore-fixtures.json", bundle)


def ordinary_production(origin, users, project, hosted_suite):
    clients = [hosted_suite.Session(origin), hosted_suite.Session(origin)]
    for client, user in zip(clients, users, strict=True):
        client.login(user)
    text = b"Owned isolated release qualification document. Synthetic fixture only."
    upload = clients[0].call(
        "POST",
        "/api/v1/knowledge/uploads",
        {
            "filename": "qualification.txt",
            "media_type": "text/plain",
            "size": len(text),
            "sha256": hashlib.sha256(text).hexdigest(),
        },
        expected=201,
    )
    clients[0].call(
        "POST",
        "/api/v1/knowledge/uploads/" + upload["id"] + "/chunks",
        {"sequence": 0, "base64": base64.b64encode(text).decode()},
    )
    doc = clients[0].call(
        "POST", "/api/v1/knowledge/uploads/" + upload["id"] + "/complete"
    )["id"]
    conversation = clients[0].call(
        "POST",
        "/api/v1/conversations",
        {"title": "Owned synthetic production verification"},
        expected=201,
    )["id"]
    os.environ["PRODUCTION_FIXTURES_JSON"] = json.dumps(
        {
            "scope": "approved-synthetic-production",
            "project_id": project,
            "users": users,
            "document_id": doc,
            "conversation_id": conversation,
        }
    )
    os.environ["VERCEL_PROJECT_ID"] = project
    checks = hosted_suite.production_probes(origin)
    require(
        checks and all(v == "PASS" for v in checks.values()),
        "ORDINARY_PRODUCTION_CRITICAL_WORKFLOWS_FAILED",
    )
    return checks


def execute(environment, request):
    require(
        environment in ["staging", "production"] and not os.getenv("GITHUB_ACTIONS"),
        "OWNER_PROBE_ENVIRONMENT",
    )
    plan = private_json("/private/plan.json")
    binding = request["binding"]
    operation = request["operation_id"]
    require(
        binding == plan["binding"]
        and str(UUID(operation)) == operation
        and request["plan_sha256"]
        == hashlib.sha256(Path("/private/plan.json").read_bytes()).hexdigest(),
        "PROBE_BINDING",
    )
    require(
        binding["repository"] == "DruHustle/onesa-ai-platform"
        and binding["component"] in ["api", "frontend"],
        "PROBE_COMPONENT",
    )
    settings = runtime("/private/runtime.env")
    config = private_json("/private/vercel.json")
    origin, bypass, deployment = provider(config, environment, binding, plan, request)
    initial_identity = served_backend_identity(
        origin, bypass, config["backend_identity"]
    )
    require(settings["ONESA_PUBLIC_ORIGIN"] == origin, "EXACT_ALLOWED_BROWSER_ORIGIN")
    ci = request["ci_run_id"]
    require(type(ci) is int and ci > 0, "GENUINE_CI_REFERENCE_REQUIRED")
    engine = fixture_engine(settings, environment, plan["expected_schema_revision"])
    before = fingerprints(engine)
    users = []
    clean = False
    preserved = False
    record = {
        "binding": binding,
        "operation_id": operation,
        "environment": environment,
        "workflow_run_id": 0,
        "execution_context": "owner-operated-oracle-" + environment,
        "mode": plan["mode"],
        "schema_revision": plan["expected_schema_revision"],
        "backend_identity": initial_identity,
        "ci_run_id": ci,
        "provider": deployment,
        "checks": {},
        "fixture_identities_disabled": False,
        "existing_records_preserved": False,
        "status": "FAIL",
    }
    try:
        users = create_fixtures(engine, ci)
        fixture = {
            "scope": "approved-synthetic-staging"
            if environment == "staging"
            else "approved-synthetic-production",
            "project_id": config["project_id"],
            "candidate_commit": binding["candidate_commit"],
            "run_id": str(ci),
            "users": users,
        }
        fixture_path = OUTPUT / "private-fixtures.json"
        write(fixture_path, fixture)
        import hosted
        import hosted_suite

        original = hosted_suite.Session

        class Identified(original):
            def __init__(self, *a, **kw):
                super().__init__(*a, **kw)
                self.opener.addheaders = [("User-Agent", "OnesaOwnerOracleRelease/1.0")]

        hosted_suite.Session = Identified
        if bypass:
            os.environ["VERCEL_AUTOMATION_BYPASS_SECRET"] = bypass
        env = {
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "LANG": "C.UTF-8",
            "HOME": "/tmp",
            "PLAYWRIGHT_BROWSERS_PATH": "/ms-playwright",
        }
        if bypass:
            env["VERCEL_AUTOMATION_BYPASS_SECRET"] = bypass
        if environment == "staging":
            context = {
                "execution_context": "owner-operated-oracle-staging",
                "repository": binding["repository"],
                "candidate_commit": binding["candidate_commit"],
                "ci_run_id": ci,
                "qualification_id": operation,
                "project_id": config["project_id"],
                "frontend_origin": origin,
                "fixture_file": str(fixture_path),
                "output_dir": str(OUTPUT),
            }
            context_path = OUTPUT / "oracle-context.json"
            write(context_path, context)
            suite = hosted_suite.run_suite(origin, oracle_context=context_path)
            write(OUTPUT / "ordinary-hosted-api.json", suite)
            require(
                suite["workflow_run_id"] == 0
                and suite["ci_run_id"] == ci
                and suite["candidate_commit"] == binding["candidate_commit"]
                and suite["status"] == "PASS"
                and set(suite["workflow_checks"]) == hosted.PLATFORM_API_WORKFLOWS
                and all(v == "PASS" for v in suite["workflow_checks"].values()),
                "MANDATORY_EXISTING_API_QUALIFICATION_FAILED",
            )
            env["ONESA_ORACLE_QUALIFICATION_CONTEXT"] = str(context_path)
            run_node("scripts/staging_ui.cjs", env)
            ui = private_json(OUTPUT / "hosted-ui.json")
            require(
                ui["workflow_run_id"] == 0
                and ui["candidate_commit"] == binding["candidate_commit"]
                and ui["status"] == "PASS"
                and set(ui["workflow_checks"]) == hosted.PLATFORM_UI_WORKFLOWS
                and all(v == "PASS" for v in ui["workflow_checks"].values())
                and len(ui["views"]) == 42,
                "MANDATORY_EXISTING_UI_QUALIFICATION_FAILED",
            )
            record["ordinary_workflows"] = {
                **suite["checks"],
                **suite["workflow_checks"],
                **ui["workflow_checks"],
            }
        else:
            record["ordinary_workflows"] = ordinary_production(
                origin, users, config["project_id"], hosted_suite
            )
        if plan["mode"] == "foundation":
            clients = [hosted_suite.Session(origin), hosted_suite.Session(origin)]
            for client, user in zip(clients, users, strict=True):
                client.login(user)
            saved = clients[0].call(
                "POST",
                "/api/v1/conversations",
                {"title": "Owned foundation persistence check"},
                expected=201,
            )["id"]
            clients[0].call("GET", "/api/v1/twins/readiness", expected=404)
            clients[0].call("GET", "/api/v1/twins/catalog", expected=404)
            clients[0].call("GET", "/api/v1/cybersecurity/readiness", expected=404)
            clients[0].call("GET", "/api/v1/cybersecurity/workspace", expected=404)
            write(
                OUTPUT / "prepared-for-replacement.json",
                {
                    "binding": binding,
                    "operation_id": operation,
                    "environment": environment,
                    "mode": "foundation",
                },
            )
            if environment == "staging":
                deadline = time.monotonic() + 240
                while not (OUTPUT / "replacement-ok.json").exists():
                    require(
                        time.monotonic() < deadline,
                        "FOUNDATION_REPLACEMENT_NOT_OBSERVED",
                    )
                    time.sleep(0.2)
                replacement = private_json(OUTPUT / "replacement-ok.json")
                require(
                    replacement["binding"] == binding
                    and replacement["operation_id"] == operation
                    and replacement["old_container"] != replacement["new_container"]
                    and replacement["image_digest"] == binding["artifact_digest"],
                    "FOUNDATION_REPLACEMENT_BINDING",
                )
                record["controlled_replacement"] = replacement
                record["backend_identity"] = served_backend_identity(
                    origin, bypass, replacement["backend_identity"]
                )
            clients[0].call("GET", "/api/v1/auth/me")
            clients[0].call("GET", "/api/v1/conversations/" + saved)
            clients[1].call("GET", "/api/v1/conversations/" + saved, expected=404)
            record["checks"] = {
                key: "PASS"
                for key in [
                    "authentication",
                    "owner_isolation",
                    "tls",
                    "ordinary_workflows",
                    "database_persistence",
                    "session_persistence",
                    "twins_disabled",
                    "cybersecurity_disabled",
                    "chat_knowledge_retained",
                ]
            }
            record["status"] = "PASS"
        elif plan["mode"] == "cybersecurity":
            context_path = OUTPUT / "private-cybersecurity-context.json"
            write(
                context_path,
                {
                    "binding": binding,
                    "operation_id": operation,
                    "environment": environment,
                    "origin": origin,
                    "users": users,
                    "output_dir": str(OUTPUT),
                    "bypass": bypass,
                },
            )
            env["ONESA_ORACLE_CYBERSECURITY_CONTEXT"] = str(context_path)
            flags = (
                ["--api-only"]
                if environment == "production" and binding["component"] == "api"
                else []
            )
            script = "scripts/release/oracle_cybersecurity_ui.cjs"
            run_node(script, env, args=flags)
            prepared = private_json(OUTPUT / "cybersecurity-prepare-ui.json")
            require(prepared["status"] == "PASS", "CYBERSECURITY_PREPARE_FAILED")
            if environment == "staging" and binding["component"] == "api":
                export_owned_restore(engine, users, binding, operation, "cybersecurity")
                write(
                    OUTPUT / "prepared-for-replacement.json",
                    {
                        "binding": binding,
                        "operation_id": operation,
                        "environment": environment,
                        "mode": "cybersecurity",
                    },
                )
                deadline = time.monotonic() + 240
                while not (OUTPUT / "replacement-ok.json").exists():
                    require(
                        time.monotonic() < deadline,
                        "CYBERSECURITY_REPLACEMENT_NOT_OBSERVED",
                    )
                    time.sleep(0.2)
                replacement = private_json(OUTPUT / "replacement-ok.json")
                require(
                    replacement["binding"] == binding
                    and replacement["operation_id"] == operation
                    and replacement["old_container"] != replacement["new_container"]
                    and replacement["image_digest"] == binding["artifact_digest"],
                    "CYBERSECURITY_REPLACEMENT_BINDING",
                )
                record["controlled_replacement"] = replacement
                record["backend_identity"] = served_backend_identity(
                    origin, bypass, replacement["backend_identity"]
                )
            run_node(script, env, args=[*flags, "--verify"])
            verified = private_json(OUTPUT / "cybersecurity-verify-ui.json")
            require(verified["status"] == "PASS", "CYBERSECURITY_PERSISTENCE_FAILED")
            record["checks"] = {
                **prepared["checks"],
                **verified["checks"],
                "chat_knowledge_retained": "PASS",
            }
            require(
                all(v == "PASS" for v in record["checks"].values()),
                "CYBERSECURITY_CHECK_FAILED",
            )
            record["browser_observations"] = [prepared["scope"], verified["scope"]]
            record["status"] = "PASS"
        else:
            require(plan["mode"] == "twins", "UNKNOWN_FEATURE_PROBE_MODE")
            twin_context = {
                "binding": binding,
                "operation_id": operation,
                "environment": environment,
                "origin": origin,
                "users": users,
                "output_dir": str(OUTPUT),
                "bypass": bypass,
            }
            twin_path = OUTPUT / "private-twin-context.json"
            write(twin_path, twin_context)
            env["ONESA_ORACLE_TWIN_CONTEXT"] = str(twin_path)
            api_only = environment == "production" and binding["component"] == "api"
            flags = ["--api-only"] if api_only else []
            run_node("scripts/release/oracle_twin_ui.cjs", env, args=flags)
            prepare = private_json(OUTPUT / "twins-prepare-ui.json")
            require(prepare["status"] == "PASS", "TWINS_PREPARE_FAILED")
            if environment == "staging" and binding["component"] == "api":
                export_owned_restore(engine, users, binding, operation)
            write(
                OUTPUT / "prepared-for-replacement.json",
                {
                    "binding": binding,
                    "operation_id": operation,
                    "model_sha256": prepare["model_sha256"],
                    "environment": environment,
                },
            )
            if environment == "staging" and binding["component"] == "api":
                deadline = time.monotonic() + 150
                while not (OUTPUT / "replacement-ok.json").exists():
                    require(
                        time.monotonic() < deadline,
                        "CONTROLLED_REPLACEMENT_NOT_OBSERVED",
                    )
                    time.sleep(0.2)
                replacement = private_json(OUTPUT / "replacement-ok.json")
                require(
                    replacement["binding"] == binding
                    and replacement["operation_id"] == operation
                    and replacement["old_container"] != replacement["new_container"]
                    and replacement["image_digest"] == binding["artifact_digest"],
                    "ACTUAL_REPLACEMENT_IDENTITY",
                )
                record["controlled_replacement"] = replacement
                record["backend_identity"] = served_backend_identity(
                    origin, bypass, replacement["backend_identity"]
                )
            run_node(
                "scripts/release/oracle_twin_ui.cjs", env, args=[*flags, "--verify"]
            )
            verify = private_json(OUTPUT / "twins-verify-ui.json")
            require(verify["status"] == "PASS", "TWINS_RELOAD_OR_PERSISTENCE_FAILED")
            record["browser_observations"] = [
                {
                    "phase": phase,
                    "browser_version": result.get("browser_version"),
                    "graphics": result.get("graphics"),
                    "scope": result.get("scope"),
                }
                for phase, result in [("prepare", prepare), ("verify", verify)]
            ]
            record["checks"] = {**prepare["checks"], **verify["checks"]}
            record["checks"]["chat_knowledge_retained"] = "PASS"
            require(
                all(v == "PASS" for v in record["checks"].values()),
                "MANDATORY_PROBE_CHECK_FAILED_OR_SKIPPED",
            )
            record["status"] = "PASS"
    except Exception as error:
        record["failure_category"] = type(error).__name__
        raise
    finally:
        try:
            if users:
                disable_fixtures(engine, users, before, ci)
                clean = True
            preserved = fingerprints(engine, exclude={u["id"] for u in users}) == before
            require(preserved, "EXISTING_ACCOUNT_OR_GRANT_CHANGED")
        finally:
            engine.dispose()
            record["fixture_identities_disabled"] = clean
            record["existing_records_preserved"] = preserved
            record["observed_at"] = datetime.now(timezone.utc).isoformat()
            if not clean or not preserved:
                record["status"] = "FAIL"
            for name in [
                "private-fixtures.json",
                "private-twin-context.json",
                "twins-browser-state.json",
                "private-cybersecurity-context.json",
                "cybersecurity-browser-state.json",
                "oracle-context.json",
            ]:
                (OUTPUT / name).unlink(missing_ok=True)
            write(OUTPUT / "receipt.json", record)
    require(
        record["status"] == "PASS" and clean and preserved,
        "COMPLETE_HOSTED_OBSERVATION_REQUIRED",
    )
    return record


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("environment", choices=["staging", "production"])
    p.add_argument("--stdin-request", action="store_true", required=True)
    args = p.parse_args()
    raw = sys.stdin.buffer.read(131073)
    require(len(raw) <= 131072, "PRIVATE_PROBE_REQUEST_BOUND")
    print(json.dumps(execute(args.environment, json.loads(raw))))


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001 -- CLI boundary redacts private input and provider diagnostics.
        raise SystemExit(
            "Owned Oracle hosted probe failed; inspect private receipts; no credentials logged"
        ) from None
