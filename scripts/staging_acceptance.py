"""Real hosted staging acceptance using synthetic identities; never mock inference."""

import json
import os
import secrets
import sys
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from argon2 import PasswordHasher
from psycopg import Error as PsycopgError
from sqlalchemy import create_engine, select, text, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from staging import target
from staging_release import BACKEND, ROLE, SERVICE_ID, migration_url, verified_preview


def preview_is_protected(response):
    if response.status_code in {401, 403}:
        return True
    # Vercel Authentication may deny access through its documented login redirect.
    # Never follow it or accept an arbitrary redirect as protection evidence.
    location = urlsplit(response.headers.get("location", ""))
    return (
        response.status_code in {302, 303, 307}
        and location.scheme == "https"
        and location.hostname == "vercel.com"
        and location.path == "/sso-api"
        and not location.username
        and not location.password
        and location.port in {None, 443}
    )


def main():
    phase = "target-validation"
    checks = []
    try:
        service, settings = target()
        origin = verified_preview()
        if (
            settings.get("ONESA_PUBLIC_ORIGIN") != origin
            or settings.get("ONESA_ENVIRONMENT") != "staging"
        ):
            raise ValueError("Staging origin or environment differs")
        bypass = os.environ.get("VERCEL_AUTOMATION_BYPASS_SECRET", "")
        if not bypass:
            raise ValueError("Protected Preview test credential missing")
        api_origin = service["serviceDetails"]["url"].rstrip("/")

        def require(response, expected, name):
            print(
                json.dumps({"check": name, "http_status": response.status_code}),
                flush=True,
            )
            if response.status_code != expected:
                raise ValueError(name + " returned HTTP " + str(response.status_code))
            checks.append(name)
            return response

        phase = "process-core-and-model-readiness"
        with httpx.Client(
            base_url=api_origin, timeout=30, follow_redirects=False
        ) as direct:
            require(direct.get("/health"), 200, "process_liveness")
            require(direct.get("/core-ready"), 200, "database_core_readiness")
            require(direct.get("/ready"), 503, "unavailable_inference_is_honest")
            for path in [
                "/api/v1/auth/me",
                "/api/v1/conversations",
                "/api/v1/agents/runs",
                "/api/v1/travel/trips",
                "/api/v1/knowledge/documents",
            ]:
                require(
                    direct.get(path),
                    401,
                    "backend_authentication_" + path.rsplit("/", 1)[-1],
                )
        phase = "preview-protection"
        response = httpx.get(origin, timeout=30, follow_redirects=False)
        if not preview_is_protected(response):
            raise ValueError("Unauthenticated Preview is not access restricted")
        checks.append("unauthorized_preview_denied")
        headers = {"x-vercel-protection-bypass": bypass, "Origin": origin}
        clients = [
            httpx.Client(
                base_url=origin, headers=headers, timeout=45, follow_redirects=False
            )
            for _ in range(3)
        ]
        html = require(clients[0].get("/"), 200, "authorized_preview_html")
        if "Onesa" not in html.text:
            raise ValueError("Expected application HTML is absent")
        phase = "synthetic-identity-fixtures"
        sys.path.insert(0, str(BACKEND))
        from app.models import AccessGrant, AuthSession, User, now

        url = migration_url(os.environ.get("STAGING_MIGRATION_DATABASE_URL", ""))
        engine = create_engine(
            url,
            pool_size=1,
            max_overflow=0,
            connect_args={"connect_timeout": 10, "prepare_threshold": None},
        )
        accounts = []
        with Session(engine) as db:
            for index in range(3):
                password = secrets.token_urlsafe(32)
                email = "staging-" + secrets.token_hex(10) + "@example.com"
                user = User(
                    email=email,
                    display_name="Synthetic staging verification",
                    password_hash=PasswordHasher().hash(password),
                )
                db.add(user)
                db.flush()
                if index < 2:
                    db.add(
                        AccessGrant(
                            user_id=user.id, expires_at=now() + timedelta(hours=2)
                        )
                    )
                accounts.append(
                    {"email": email, "password": password, "id": str(user.id)}
                )
            db.commit()
        # Private, ephemeral runner file for browser login only; never upload it.
        private = Path("/tmp/onesa-staging-acceptance-users.json")
        descriptor = os.open(private, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w") as handle:
            json.dump({"origin": origin, "accounts": accounts}, handle)
        os.chmod(private, 0o600)
        phase = "authentication-cookies-and-csrf"
        for index in range(2):
            response = require(
                clients[index].post(
                    "/api/v1/auth/login",
                    json={key: accounts[index][key] for key in ["email", "password"]},
                ),
                200,
                "authorized_login_" + str(index),
            )
            cookies = response.headers.get_list("set-cookie")
            session = next(
                value for value in cookies if value.startswith("onesa_session=")
            )
            csrf = next(value for value in cookies if value.startswith("onesa_csrf="))
            if (
                not all(
                    flag in session.lower()
                    for flag in ["secure", "httponly", "samesite=lax", "max-age="]
                )
                or "secure" not in csrf.lower()
                or "httponly" in csrf.lower()
            ):
                raise ValueError("Session/CSRF cookie attributes incorrect")
        checks.append("secure_httponly_samesite_cookies")
        require(
            clients[2].post(
                "/api/v1/auth/login",
                json={key: accounts[2][key] for key in ["email", "password"]},
            ),
            403,
            "uninvited_identity_denied",
        )
        require(
            clients[2].post(
                "/api/v1/auth/login",
                json={
                    "email": accounts[0]["email"],
                    "password": "wrong-synthetic-password",
                },
            ),
            401,
            "invalid_credentials_denied",
        )
        require(
            clients[0].post(
                "/api/v1/conversations", json={"title": "CSRF negative fixture"}
            ),
            403,
            "missing_csrf_denied",
        )
        csrf_headers = {"X-CSRF-Token": clients[0].cookies.get("onesa_csrf")}
        require(
            clients[0].post(
                "/api/v1/conversations",
                json={"title": "Origin negative fixture"},
                headers={**csrf_headers, "Origin": "https://foreign.invalid"},
            ),
            403,
            "foreign_origin_denied",
        )
        conversation = require(
            clients[0].post(
                "/api/v1/conversations",
                json={"title": "Synthetic hosted persistence verification"},
                headers=csrf_headers,
            ),
            201,
            "conversation_created",
        ).json()["id"]
        require(
            clients[0].get("/api/v1/conversations/" + conversation),
            200,
            "conversation_retrieved",
        )
        require(
            clients[1].get("/api/v1/conversations/" + conversation),
            404,
            "conversation_user_isolation",
        )
        require(
            clients[0].post(
                "/api/v1/conversations", json={"title": ""}, headers=csrf_headers
            ),
            422,
            "conversation_validation",
        )
        phase = "explicit-tools-and-dependency-failures"
        run = require(
            clients[0].post(
                "/api/v1/agents/runs",
                headers=csrf_headers,
                json={
                    "goal": "Synthetic explicit addition",
                    "allowed_tools": ["arithmetic"],
                    "steps": [
                        {
                            "tool": "arithmetic",
                            "arguments": {"operation": "add", "values": [2, 3]},
                        }
                    ],
                },
            ),
            201,
            "explicit_local_tool_run",
        ).json()
        if run["status"] != "completed" or run["steps"][0]["result"]["result"] != 5:
            raise ValueError("Explicit local tool computation failed")
        require(
            clients[1].get("/api/v1/agents/runs/" + run["id"]),
            404,
            "agent_user_isolation",
        )
        require(
            clients[0].post(
                "/api/v1/agents/runs",
                headers=csrf_headers,
                json={
                    "goal": "Unavailable model planning",
                    "allowed_tools": ["arithmetic"],
                },
            ),
            503,
            "model_planning_unavailable",
        )
        require(clients[0].get("/api/v1/knowledge/documents"), 200, "knowledge_listing")
        require(
            clients[0].post(
                "/api/v1/knowledge/documents",
                headers=csrf_headers,
                files={
                    "file": (
                        "synthetic.txt",
                        b"Synthetic staging document for honest unavailable embedding verification.",
                        "text/plain",
                    )
                },
            ),
            503,
            "embedding_ingestion_unavailable",
        )
        require(
            clients[0].post(
                "/api/v1/knowledge/search",
                headers=csrf_headers,
                json={"query": "Synthetic staging"},
            ),
            503,
            "semantic_retrieval_unavailable",
        )
        require(
            clients[0].post(
                "/api/v1/knowledge/documents",
                headers=csrf_headers,
                files={
                    "file": (
                        "synthetic.bin",
                        b"unsupported",
                        "application/octet-stream",
                    )
                },
            ),
            415,
            "knowledge_format_validation",
        )
        require(clients[0].get("/api/v1/travel/trips"), 200, "travel_listing")
        require(
            clients[0].post(
                "/api/v1/travel/trips",
                headers=csrf_headers,
                json={
                    "destination": "Synthetic location",
                    "duration": 1,
                    "budget": 10,
                    "currency": "EUR",
                },
            ),
            503,
            "itinerary_inference_unavailable",
        )
        require(
            clients[0].post(
                "/api/v1/travel/trips",
                headers=csrf_headers,
                json={"destination": "", "duration": 0, "budget": -1},
            ),
            422,
            "travel_validation",
        )
        phase = "session-expiration-and-revocation"
        from uuid import UUID

        with Session(engine) as db:
            db.execute(
                update(AuthSession)
                .where(AuthSession.user_id == UUID(accounts[1]["id"]))
                .values(expires_at=now() - timedelta(minutes=1))
            )
            db.commit()
        require(clients[1].get("/api/v1/auth/me"), 401, "expired_session_denied")
        require(
            clients[1].post(
                "/api/v1/auth/login",
                json={key: accounts[1][key] for key in ["email", "password"]},
            ),
            200,
            "login_after_expiration",
        )
        revoked = clients[1].cookies.get("onesa_session")
        require(
            clients[1].post(
                "/api/v1/auth/logout",
                headers={"X-CSRF-Token": clients[1].cookies.get("onesa_csrf")},
            ),
            204,
            "logout",
        )
        require(
            clients[1].get(
                "/api/v1/auth/me", headers={"Cookie": "onesa_session=" + revoked}
            ),
            401,
            "revoked_session_denied",
        )
        phase = "authorized-staging-restart"
        import deploy_render

        os.environ["RENDER_SERVICE_ID"] = SERVICE_ID
        deploy_render.main()
        require(
            clients[0].get("/api/v1/conversations/" + conversation),
            200,
            "conversation_survives_restart",
        )
        require(
            clients[0].get("/api/v1/agents/runs/" + run["id"]),
            200,
            "explicit_tool_run_survives_restart",
        )
        phase = "scoped-idle-connection-recovery"
        # Interrupt only idle connections of this verified staging runtime role.
        # Active queries, owner/migration sessions and other products are untouched.
        with engine.begin() as connection:
            recovered_connections = connection.scalars(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE pid IN (SELECT pid FROM pg_stat_activity WHERE usename=:role AND datname='neondb' AND state='idle' AND pid<>pg_backend_pid() LIMIT 5)"
                ),
                {"role": ROLE},
            ).all()
        if not any(recovered_connections):
            raise ValueError(
                "No idle staging connection was available for recovery verification"
            )
        require(
            clients[0].get("/api/v1/conversations/" + conversation),
            200,
            "staging_connection_recovers_after_idle_disconnect",
        )
        # Account grants expire in two hours; keep synthetic records for persistence evidence.
        with Session(engine) as db:
            if not db.scalar(select(User.id).where(User.id == UUID(accounts[0]["id"]))):
                raise ValueError("Synthetic identity disappeared after restart")
        for client in clients:
            client.close()
        engine.dispose()
        report = {
            "commit": os.environ["GITHUB_SHA"],
            "frontend": origin,
            "backend": api_origin,
            "checks_passed": checks,
            "model_generation": "BLOCKED",
            "semantic_embeddings": "BLOCKED",
            "production_modified": False,
        }
        Path("/tmp/onesa-staging-acceptance.json").write_text(
            json.dumps(report, indent=2)
        )
        print(json.dumps(report, indent=2))
    except (
        httpx.HTTPError,
        SQLAlchemyError,
        PsycopgError,
        ValueError,
        KeyError,
        OSError,
        RuntimeError,
        StopIteration,
    ) as error:
        raise SystemExit(
            f"Hosted staging acceptance failed during {phase} ({type(error).__name__}); no credentials or response bodies are logged"
        ) from None


if __name__ == "__main__":
    main()
