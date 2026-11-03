"""Source-bound shared-identity fixtures for the existing owner-run AI suites.

The two existing synthetic users retain their credentials, grants, mappings and
data. Only session hashes observed by this operation may be retired. Native
scenario results still come from their original API and rendered browser suites.
"""

import hashlib
import http.cookiejar
import json
import os
import re
import subprocess
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID

ACTORS = ("primary", "foreign")
PROFILE = "shared-identity-v1"
ROOT = Path(__file__).resolve().parents[2]


def require(value, code):
    if not value:
        raise ValueError(code)


def unique(pairs):
    out = {}
    for key, value in pairs:
        require(key not in out, "AI_IDENTITY_DUPLICATE_FIELD")
        out[key] = value
    return out


def private_bytes(path, bound=65536):
    path = Path(path)
    info = path.lstat()
    require(
        path.is_file()
        and not path.is_symlink()
        and info.st_nlink == 1
        and info.st_uid == os.getuid()
        and not info.st_mode & 0o077
        and info.st_size <= bound,
        "AI_IDENTITY_PRIVATE_CUSTODY_REQUIRED",
    )
    return path.read_bytes()


def current(identity):
    instant = datetime.fromisoformat(identity["expires_at"])
    require(
        instant.tzinfo is not None and datetime.now(timezone.utc) < instant,
        "AI_IDENTITY_CREDENTIAL_EXPIRED",
    )


def validate_identity(identity):
    require(
        identity["profile"] == PROFILE
        and identity["environment"] in {"staging", "production"}
        and re.fullmatch(r"[a-f0-9]{40}", identity["candidate_commit"])
        and str(UUID(identity["operation_id"])) == identity["operation_id"],
        "AI_PRIVATE_IDENTITY_CONTEXT",
    )
    origin, issuer = urlsplit(identity["origin"]), urlsplit(identity["issuer"])
    require(
        origin.scheme == issuer.scheme == "https"
        and origin.netloc == origin.hostname
        and issuer.netloc == issuer.hostname
        and not origin.path
        and not origin.query
        and not origin.fragment
        and issuer.path == "/api/v1/identity"
        and not issuer.query
        and not issuer.fragment,
        "AI_PRIVATE_IDENTITY_ORIGIN",
    )
    if identity["environment"] == "production":
        require(
            origin.hostname == "platform.onesa.eu"
            and issuer.hostname == "portal.onesa.eu",
            "AI_IDENTITY_PRODUCTION_ORIGIN",
        )
    else:
        require(
            re.fullmatch(
                r"onesa-ai-platform-git-staging-[a-z0-9-]+\.vercel\.app",
                origin.hostname or "",
            )
            and (
                issuer.hostname == "portal-staging.onesa.eu"
                or re.fullmatch(
                    r"onesa-company-portal-[a-z0-9-]+\.vercel\.app",
                    issuer.hostname or "",
                )
            ),
            "AI_IDENTITY_STAGING_ORIGIN",
        )
    require(
        re.fullmatch(r"[A-Za-z0-9_-]{16,128}", identity["client_id"])
        and set(identity["accounts"]) == set(ACTORS),
        "AI_PRIVATE_IDENTITY_CLIENT",
    )
    current(identity)
    require(
        (
            datetime.fromisoformat(identity["expires_at"]) - datetime.now(timezone.utc)
        ).total_seconds()
        <= 3600,
        "AI_IDENTITY_CREDENTIAL_LIFETIME",
    )
    for account in identity["accounts"].values():
        require(
            set(account)
            == {
                "subject",
                "email",
                "local_user_id",
                "password",
                "local_password",
                "totp_secret",
            }
            and all(
                str(UUID(account[key])) == account[key]
                for key in ["subject", "local_user_id"]
            )
            and re.fullmatch(r"[^\s@]{1,64}@[^\s@]{1,189}", account["email"])
            and account["email"] == account["email"].casefold()
            and isinstance(account["password"], str)
            and 12 <= len(account["password"]) <= 256
            and isinstance(account["local_password"], str)
            and 12 <= len(account["local_password"]) <= 128
            and re.fullmatch(r"[A-Z2-7]{16,128}", account["totp_secret"]),
            "AI_PRIVATE_IDENTITY_ACCOUNT",
        )
    require(
        all(
            len({account[key] for account in identity["accounts"].values()}) == 2
            for key in ["subject", "email", "local_user_id"]
        ),
        "AI_SEPARATE_IDENTITY_FIXTURES_REQUIRED",
    )


def load_identity(
    plan, binding, request, environment, origin, settings, path="/private/identity.json"
):
    require(
        plan["mode"] == "identity"
        and binding["component"] in {"identity-api", "identity-frontend"},
        "AI_EXPLICIT_IDENTITY_PROFILE_REQUIRED",
    )
    source = plan["identity"]
    require(
        source["profile"] == PROFILE
        and all(
            source[key] == binding[field]
            for key, field in [
                ("source_commit", "candidate_commit"),
                ("source_tree", "source_tree"),
                ("source_sha256", "source_sha256"),
            ]
        ),
        "AI_IDENTITY_SOURCE_BINDING",
    )
    raw = private_bytes(path)
    require(
        hashlib.sha256(raw).hexdigest() == request["identity_custody_sha256"],
        "AI_NARROWED_IDENTITY_CUSTODY_CHANGED",
    )
    held = json.loads(raw, object_pairs_hook=unique)
    require(
        set(held)
        == {
            "schema_version",
            "candidate_commit",
            "created_at",
            "expires_at",
            "scope",
            "environments",
            "source_custody_sha256",
        }
        and type(held["schema_version"]) is int
        and held["schema_version"] == 1
        and held["candidate_commit"] == binding["candidate_commit"]
        and held["scope"] == "existing-owned-synthetic-identities"
        and held["source_custody_sha256"] == source["credentials_sha256"]
        and set(held["environments"]) == {environment},
        "AI_ENVIRONMENT_CUSTODY_MUST_BE_NARROWED",
    )
    created, expires = (
        datetime.fromisoformat(held[key]) for key in ["created_at", "expires_at"]
    )
    require(
        created.tzinfo is not None
        and expires.tzinfo is not None
        and 0 < (expires - created).total_seconds() <= 3600
        and created <= datetime.now(timezone.utc) < expires,
        "AI_IDENTITY_CREDENTIAL_EXPIRED",
    )
    expected, custody = (
        source["environments"][environment],
        held["environments"][environment],
    )
    require(
        set(custody) == {"accounts", "portal_bypass"}
        and set(custody["accounts"]) == set(ACTORS),
        "AI_IDENTITY_ACCOUNT_CUSTODY",
    )
    require(
        settings.get("ONESA_IDENTITY_ENABLED") == "true"
        and settings.get("ONESA_IDENTITY_ISSUER") == expected["issuer"]
        and settings.get("ONESA_IDENTITY_CLIENT_ID") == expected["client_id"]
        and settings.get("ONESA_IDENTITY_CALLBACK_URL")
        == expected["callback_url"]
        == origin + "/api/v1/auth/onesa/callback",
        "AI_IDENTITY_RUNTIME_CONFIGURATION_CHANGED",
    )
    for actor, account in custody["accounts"].items():
        require(
            set(account)
            == {
                "subject",
                "email",
                "local_user_id",
                "password",
                "local_password",
                "totp_secret",
            }
            and all(
                account[key] == expected["accounts"][actor][key]
                for key in ["subject", "email", "local_user_id"]
            )
            and all(
                str(UUID(account[key])) == account[key]
                for key in ["subject", "local_user_id"]
            )
            and re.fullmatch(r"[^\s@]{1,64}@[^\s@]{1,189}", account["email"])
            and account["email"] == account["email"].casefold()
            and isinstance(account["password"], str)
            and 12 <= len(account["password"]) <= 256
            and isinstance(account["local_password"], str)
            and 12 <= len(account["local_password"]) <= 128
            and re.fullmatch(r"[A-Z2-7]{16,128}", account["totp_secret"]),
            "AI_IDENTITY_ACCOUNT_BINDING",
        )
    require(
        all(
            len({account[key] for account in custody["accounts"].values()}) == 2
            for key in ["subject", "email", "local_user_id"]
        ),
        "AI_SEPARATE_IDENTITY_FIXTURES_REQUIRED",
    )
    bypass = custody["portal_bypass"]
    require(
        isinstance(bypass, str)
        and len(bypass) <= 2048
        and not re.search(r"[\x00-\x20\x7f]", bypass)
        and hashlib.sha256(bypass.encode()).hexdigest()
        == expected["portal_bypass_sha256"]
        and (environment != "production" or bypass == ""),
        "AI_PORTAL_BYPASS_CUSTODY",
    )
    return {
        "profile": PROFILE,
        "environment": environment,
        "origin": origin,
        "issuer": expected["issuer"],
        "client_id": expected["client_id"],
        "candidate_commit": binding["candidate_commit"],
        "operation_id": request["operation_id"],
        "expires_at": held["expires_at"],
        "accounts": custody["accounts"],
        "portal_bypass": bypass,
        "session_journal": "/private/output/identity-sessions.jsonl",
    }


def fixture_users(identity):
    validate_identity(identity)
    return [
        {
            "id": identity["accounts"][actor]["local_user_id"],
            "email": identity["accounts"][actor]["email"],
            "password": identity["accounts"][actor]["password"],
        }
        for actor in ACTORS
    ]


def validate_fixture(config, identity):
    require(
        identity["profile"] == PROFILE
        and config.get("scope") == "approved-synthetic-" + identity["environment"]
        and config.get("users") == fixture_users(identity),
        "AI_IDENTITY_FIXTURE_BINDING",
    )
    if "candidate_commit" in config:
        require(
            config["candidate_commit"] == identity["candidate_commit"],
            "AI_IDENTITY_FIXTURE_SOURCE",
        )
    return config


def local_accounts(engine, identity, *, linked=False):
    from app.models import SharedIdentity, User
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    with Session(engine) as db:
        for account in identity["accounts"].values():
            user = db.get(User, UUID(account["local_user_id"]))
            require(
                user is not None
                and user.email == account["email"]
                and user.status == "active",
                "AI_EXISTING_SYNTHETIC_USER_CHANGED",
            )
            mapping = db.scalar(
                select(SharedIdentity).where(SharedIdentity.user_id == user.id)
            )
            require(
                mapping is None
                and not linked
                or mapping is not None
                and mapping.issuer == identity["issuer"]
                and mapping.subject == account["subject"],
                "AI_IMMUTABLE_LOCAL_IDENTITY_MAPPING_CHANGED",
            )


def ownership(table, seen=()):
    if table.name == "users":
        return []
    if table.name in seen:
        return None
    for fk in sorted(
        table.foreign_keys, key=lambda key: 0 if key.column.table.name == "users" else 1
    ):
        tail = ownership(fk.column.table, (*seen, table.name))
        if tail is not None:
            return [(fk.parent.name, fk.column.table.name, fk.column.name), *tail]
    return None


def owned_fingerprints(engine, users):
    """Only row hashes leave PostgreSQL; old owned rows must survive byte-for-byte."""
    from app import cyber_models, twin_models  # noqa: F401
    from app.models import Base
    from sqlalchemy import text

    result, owners = {}, [user["id"] for user in users]
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
        require(len(names) <= 100, "AI_OWNED_PRESERVATION_TABLE_BOUND")
        for name in names:
            if name in {
                "alembic_version",
                "rate_buckets",
                "model_leases",
                "identity_transactions",
            }:
                continue
            table = Base.metadata.tables.get(name)
            require(table is not None, "AI_UNKNOWN_OWNED_PERSISTENT_TABLE")
            path = ownership(table)
            require(path is not None, "AI_UNKNOWN_OWNED_PERSISTENT_OWNERSHIP")
            joins, last = "", "t0"
            for index, (child, parent, column) in enumerate(path):
                following = "t" + str(index + 1)
                joins += f' JOIN public."{parent}" {following} ON {last}."{child}"={following}."{column}"'
                last = following
            source = f' FROM public."{name}" t0{joins} WHERE {last}.id=ANY(CAST(:owners AS uuid[]))'
            count, size = db.execute(
                text("SELECT count(*),coalesce(sum(pg_column_size(t0)),0)" + source),
                {"owners": owners},
            ).one()
            require(
                count <= 10000 and size <= 64 * 1024**2, "AI_OWNED_PRESERVATION_BOUND"
            )
            hashes = (
                db.execute(
                    text(
                        "SELECT encode(sha256(convert_to(to_jsonb(t0)::text,'UTF8')),'hex')"
                        + source
                    ),
                    {"owners": owners},
                )
                .scalars()
                .all()
            )
            result[name] = hashes
    return result


def preserved_owned(before, after):
    return all(
        not (Counter(hashes) - Counter(after.get(name, [])))
        for name, hashes in before.items()
    )


def session_baseline(engine, users):
    from app.models import AuthSession
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    with Session(engine) as db:
        rows = list(
            db.scalars(
                select(AuthSession.id)
                .where(AuthSession.user_id.in_([UUID(user["id"]) for user in users]))
                .limit(1001)
            )
        )
    require(len(rows) <= 1000, "AI_EXISTING_SESSION_BOUND")
    return {str(value) for value in rows}


def observed_sessions(identity):
    raw = private_bytes(identity["session_journal"])
    rows = [json.loads(line, object_pairs_hook=unique) for line in raw.splitlines()]
    require(len(rows) <= 256, "AI_OBSERVED_SESSION_BOUND")
    out = {}
    for row in rows:
        require(
            set(row) == {"operation_id", "token_sha256", "csrf_sha256"}
            and row["operation_id"] == identity["operation_id"]
            and all(
                re.fullmatch(r"[a-f0-9]{64}", row[key])
                for key in ["token_sha256", "csrf_sha256"]
            )
            and (
                row["token_sha256"] not in out
                or out[row["token_sha256"]] == row["csrf_sha256"]
            ),
            "AI_OBSERVED_SESSION_BINDING",
        )
        out[row["token_sha256"]] = row["csrf_sha256"]
    return out


def retire_sessions(engine, identity, before):
    from app.models import AuthSession, IdentitySession, now
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    observed, tracked = observed_sessions(identity), set()
    accounts = {
        value["local_user_id"]: value for value in identity["accounts"].values()
    }
    with Session(engine) as db:
        for token, csrf in observed.items():
            session = db.scalar(
                select(AuthSession)
                .where(AuthSession.token_hash == token)
                .with_for_update()
            )
            require(
                session is not None
                and str(session.id) not in before
                and str(session.user_id) in accounts
                and session.csrf_hash == csrf,
                "AI_OBSERVED_SESSION_CANNOT_TOUCH_EXISTING_OR_FOREIGN_SESSION",
            )
            linked = db.get(IdentitySession, session.id)
            require(
                linked is not None
                and linked.issuer == identity["issuer"]
                and linked.subject == accounts[str(session.user_id)]["subject"],
                "AI_OBSERVED_SESSION_MAPPING",
            )
            tracked.add(str(session.id))
            if session.revoked_at is None:
                session.revoked_at = now()
        db.commit()
        # An interrupted callback can create a session before its browser can
        # journal the token. It remains an explicit uncertainty; never infer
        # ownership from a user ID and revoke an unobserved concurrent session.
        current_ids = {
            str(value)
            for value in db.scalars(
                select(AuthSession.id).where(
                    AuthSession.user_id.in_([UUID(key) for key in accounts])
                )
            )
        }
        require(current_ids - before == tracked, "AI_UNOBSERVED_SESSION_UNCERTAINTY")
        require(
            not any(
                db.get(AuthSession, UUID(key)).revoked_at is None for key in tracked
            ),
            "AI_OBSERVED_SESSION_STILL_ACTIVE",
        )
    return True


def validate_session(value, identity, actor):
    current(identity)
    account = identity["accounts"][actor]
    require(
        set(value)
        == {
            "schema_version",
            "origin",
            "issuer",
            "subject",
            "local_user_id",
            "csrf",
            "cookies",
        }
        and value["schema_version"] == 1
        and value["origin"] == identity["origin"]
        and value["issuer"] == identity["issuer"]
        and value["subject"] == account["subject"]
        and value["local_user_id"] == account["local_user_id"]
        and re.fullmatch(r"[A-Za-z0-9_-]{43}", value["csrf"])
        and isinstance(value["cookies"], list)
        and len(value["cookies"]) == 2,
        "AI_IDENTITY_SESSION_BINDING",
    )
    cookies = {cookie["name"]: cookie for cookie in value["cookies"]}
    require(set(cookies) == {"onesa_session", "onesa_csrf"}, "AI_IDENTITY_COOKIE_NAMES")
    for name, cookie in cookies.items():
        require(
            set(cookie)
            == {
                "name",
                "value",
                "domain",
                "path",
                "expires",
                "httpOnly",
                "secure",
                "sameSite",
            }
            and re.fullmatch(r"[A-Za-z0-9_-]{43}", cookie["value"])
            and cookie["domain"] == urlsplit(identity["origin"]).hostname
            and cookie["path"] == "/"
            and cookie["secure"] is True
            and cookie["httpOnly"] is (name == "onesa_session")
            and cookie["sameSite"] == "Lax"
            and type(cookie["expires"]) in {int, float}
            and time.time() < cookie["expires"] <= time.time() + 86400,
            "AI_HOST_ONLY_IDENTITY_COOKIE_REQUIRED",
        )
    require(
        cookies["onesa_csrf"]["value"] == value["csrf"],
        "AI_SESSION_BOUND_CSRF_REQUIRED",
    )


def login(client, user, identity, bypass):
    require(
        client.origin == identity["origin"],
        "AI_IDENTITY_COOKIE_ORIGIN_MUST_NOT_BE_REWRITTEN",
    )
    actor = next(
        (
            actor
            for actor in ACTORS
            if identity["accounts"][actor]["local_user_id"] == user["id"]
        ),
        None,
    )
    require(
        actor is not None and user in fixture_users(identity), "AI_BOUND_FIXTURE_ONLY"
    )
    response = subprocess.run(
        [
            "/usr/local/bin/node",
            str(ROOT / "scripts/release/oracle_ai_identity_browser.mjs"),
        ],
        input=json.dumps(
            {"identity": identity, "actor": actor, "app_bypass": bypass or None}
        ).encode(),
        cwd=ROOT,
        env={
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "HOME": "/tmp",
            "LANG": "C.UTF-8",
            "PLAYWRIGHT_BROWSERS_PATH": "/ms-playwright",
        },
        capture_output=True,
        timeout=180,
        check=False,
    )
    require(
        response.returncode == 0 and 0 < len(response.stdout) <= 65536,
        "AI_SHARED_IDENTITY_LOGIN_FAILED",
    )
    value = json.loads(response.stdout, object_pairs_hook=unique)
    validate_session(value, identity, actor)
    client.cookies.clear()
    for cookie in value["cookies"]:
        client.cookies.set_cookie(
            http.cookiejar.Cookie(
                version=0,
                name=cookie["name"],
                value=cookie["value"],
                port=None,
                port_specified=False,
                domain=cookie["domain"],
                domain_specified=False,
                domain_initial_dot=False,
                path="/",
                path_specified=True,
                secure=True,
                expires=int(cookie["expires"]),
                discard=False,
                comment=None,
                comment_url=None,
                rest={
                    "SameSite": "Lax",
                    **({"HttpOnly": None} if cookie["httpOnly"] else {}),
                },
                rfc2109=False,
            )
        )
    client.csrf = value["csrf"]
    me = client.call("GET", "/api/v1/auth/me")
    require(
        me["id"] == user["id"]
        and me["email"] == user["email"]
        and me["identity_mode"] == "onesa"
        and me["global_admin"] is False
        and me["administrator"] is False,
        "AI_LIVE_IDENTITY_SESSION_CHANGED",
    )
    return me
