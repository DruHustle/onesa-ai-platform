"""Actual verified local TLS, cookie/CSRF/ownership and least-privilege acceptance."""

import json
import secrets
import ssl
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
URL = "https://localhost:3443"
context = ssl.create_default_context(
    cafile=str(ROOT / "data/acceptance-005/staging-ca.crt")
)
checks = {}
with httpx.Client(
    base_url=URL, verify=context, headers={"Origin": URL}, timeout=30
) as owner:
    redirect = owner.get("/api/v1/auth/me/")
    checks["redirect_preserves_tls_origin"] = (
        redirect.headers.get("location") == URL + "/api/v1/auth/me"
    )
    checks["tls_and_readiness"] = owner.get("/ready").status_code == 200
    credentials = {
        "email": f"tls-{secrets.token_hex(8)}@example.com",
        "password": secrets.token_urlsafe(24),
    }
    response = owner.post(
        "/api/v1/auth/register", json={**credentials, "display_name": "TLS fixture"}
    )
    response.raise_for_status()
    cookies = response.headers.get_list("set-cookie")
    session = next(cookie for cookie in cookies if cookie.startswith("onesa_session="))
    checks["secure_session_cookie"] = all(
        value in session.lower()
        for value in ["secure", "httponly", "samesite=lax", "path=/"]
    )
    checks["host_only_cookie"] = "domain=" not in session.lower()
    checks["csrf_cookie_secure"] = any(
        cookie.startswith("onesa_csrf=") and "secure" in cookie.lower()
        for cookie in cookies
    )
    token = owner.cookies["onesa_session"]
    checks["csrf_denied"] = (
        owner.post("/api/v1/conversations", json={}).status_code == 403
    )
    owner.headers["X-CSRF-Token"] = owner.cookies["onesa_csrf"]
    checks["origin_denied"] = (
        owner.post(
            "/api/v1/conversations", headers={"Origin": "https://evil.invalid"}, json={}
        ).status_code
        == 403
    )
    response = owner.post(
        "/api/v1/conversations", json={"title": "TLS retained fixture"}
    )
    response.raise_for_status()
    identifier = response.json()["id"]
    document = owner.post(
        "/api/v1/knowledge/documents",
        files={
            "file": (
                "private.txt",
                b"Synthetic TLS private document Berlin",
                "text/plain",
            )
        },
    )
    document.raise_for_status()
    document_id = document.json()["id"]
    run = owner.post(
        "/api/v1/agents/runs",
        json={"goal": "Count words", "allowed_tools": ["text_stats"]},
    )
    run.raise_for_status()
    trip = owner.post(
        "/api/v1/travel/trips",
        json={"destination": "Berlin", "duration": 1, "budget": 100},
    )
    trip.raise_for_status()
    checks["private_metrics_not_public"] = owner.get("/metrics").status_code == 404
    checks["upload_type_denied"] = (
        owner.post(
            "/api/v1/knowledge/documents",
            files={"file": ("bad.html", b"<script>bad</script>", "text/html")},
        ).status_code
        == 415
    )
    checks["invalid_pdf_denied"] = (
        owner.post(
            "/api/v1/knowledge/documents",
            files={"file": ("bad.pdf", b"%PDF-malformed", "application/pdf")},
        ).status_code
        == 422
    )
    checks["extra_privilege_field_denied"] = (
        owner.post(
            "/api/v1/agents/runs",
            json={
                "goal": "test",
                "allowed_tools": ["text_stats"],
                "administrator": True,
            },
        ).status_code
        == 422
    )
    checks["tool_without_grant_denied"] = (
        owner.post("/api/v1/agents/runs", json={"goal": "Count words"}).status_code
        == 403
    )
    checks["no_cors_wildcard"] = (
        "access-control-allow-origin"
        not in owner.options(
            "/api/v1/conversations", headers={"Origin": "https://evil.invalid"}
        ).headers
    )
    response = owner.get("/")
    checks["security_headers"] = all(
        name in response.headers
        for name in [
            "strict-transport-security",
            "x-content-type-options",
            "x-frame-options",
            "referrer-policy",
        ]
    )
    owner.post("/api/v1/auth/login", json=credentials).raise_for_status()
    with httpx.Client(
        base_url=URL, verify=context, cookies={"onesa_session": token}
    ) as stale:
        checks["reauthentication_revokes_previous"] = (
            stale.get("/api/v1/auth/me").status_code == 401
        )
    with httpx.Client(
        base_url=URL, verify=context, headers={"Origin": URL}
    ) as intruder:
        intruder.post(
            "/api/v1/auth/register",
            json={
                "email": f"intruder-{secrets.token_hex(8)}@example.com",
                "password": secrets.token_urlsafe(24),
                "display_name": "Isolation fixture",
            },
        ).raise_for_status()
        intruder.headers["X-CSRF-Token"] = intruder.cookies["onesa_csrf"]
        for name, path in {
            "conversation": f"/conversations/{identifier}",
            "document": f"/knowledge/documents/{document_id}",
            "agent": f"/agents/runs/{run.json()['id']}",
            "trip": f"/travel/trips/{trip.json()['id']}",
        }.items():
            checks[name + "_isolation"] = (
                intruder.get("/api/v1" + path).status_code == 404
            )
    owner.headers["X-CSRF-Token"] = owner.cookies["onesa_csrf"]
    current = owner.cookies["onesa_session"]
    owner.post("/api/v1/auth/logout").raise_for_status()
    owner.cookies.set("onesa_session", current)
    checks["logout_revocation"] = owner.get("/api/v1/auth/me").status_code == 401
path = ROOT / "data/acceptance-005/tls-security.json"
path.write_text(
    json.dumps(
        {
            "environment": "isolated local staging",
            "public_tls_verified": False,
            "checks": checks,
        },
        indent=2,
    )
    + "\n"
)
print(f"Verified local TLS/security checks: {sum(checks.values())}/{len(checks)}")
if not all(checks.values()):
    raise SystemExit(
        "Failed checks: "
        + ", ".join(name for name, valid in checks.items() if not valid)
    )
