import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.identity import bearer
from app.identity_worker import process_one
from app.main import create_app
from app.models import AccessGrant, IdentityMail, IdentityToken, User, now
from tests.conftest import signup


def configured(api: TestClient) -> str:
    owner = signup(api, "operator@example.com")
    config = api.app.state.settings
    api.app.state.settings = config.model_copy(
        update={
            "access_operator_user_ids": [owner["id"]],
            "auth_delivery_key": "synthetic-fixture-delivery-key-" + "x" * 48,
            "mail_provider": "resend",
            "resend_api_key": "fixture-not-live",
            "mail_from": "Onesa Test <sender@example.com>",
        }
    )
    return owner["id"]


def invite(api: TestClient, pg, email: str = "invited@example.com") -> tuple[UUID, str]:
    result = api.post(
        "/api/v1/admin/invitations",
        json={
            "email": email,
            "current_password": "correct-horse-123!",
            "access_days": 30,
        },
    )
    assert result.status_code == 202
    identifier = UUID(result.json()["id"])
    with Session(pg) as db:
        row = db.get(IdentityToken, identifier)
        return identifier, bearer(api.app.state.settings, row)


def register(api: TestClient, token: str, email: str = "invited@example.com"):
    return api.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "new-invited-account-123!",
            "display_name": "Invited",
            "invitation_token": token,
        },
    )


def test_invitation_blocks_registration_login_and_existing_sessions(api, pg):
    signup(api)
    api.app.state.settings = api.app.state.settings.model_copy(
        update={"registration_mode": "invitation"}
    )
    assert (
        api.post(
            "/api/v1/auth/register",
            json={
                "email": "new@example.com",
                "password": "correct-horse-123!",
                "display_name": "New",
            },
        ).status_code
        == 403
    )
    assert (
        api.post(
            "/api/v1/auth/login",
            json={"email": "user@example.com", "password": "correct-horse-123!"},
        ).status_code
        == 403
    )
    for route in [
        "/auth/me",
        "/conversations",
        "/knowledge/documents",
        "/agents/runs",
        "/travel/trips",
    ]:
        assert api.get("/api/v1" + route).status_code == 403


@pytest.mark.parametrize("reason", ["expired", "revoked", "wrong_email", "grant_expired"])
def test_invitation_denial_cases(api, pg, reason):
    configured(api)
    identifier, token = invite(api, pg)
    api.app.state.settings = api.app.state.settings.model_copy(
        update={"registration_mode": "invitation"}
    )
    with Session(pg) as db:
        row = db.get(IdentityToken, identifier)
        if reason == "expired":
            row.expires_at = now() - timedelta(seconds=1)
        if reason == "revoked":
            row.revoked_at = now()
        if reason == "grant_expired":
            row.grant_expires_at = now() - timedelta(seconds=1)
        db.commit()
    assert (
        register(
            api, token, "other@example.com" if reason == "wrong_email" else "invited@example.com"
        ).status_code
        == 403
    )


def test_invitation_atomic_consumption_and_grant_revocation(api, pg):
    configured(api)
    identifier, token = invite(api, pg)
    config = api.app.state.settings.model_copy(update={"registration_mode": "invitation"})
    api.app.state.settings = config

    def redeem(_):
        with TestClient(create_app(config)) as other:
            other.headers["Origin"] = config.public_origin
            return register(other, token).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(redeem, range(2))) == [201, 403]
    assert register(api, token).status_code == 403
    with Session(pg) as db:
        row = db.get(IdentityToken, identifier)
        assert row.consumed_at is not None
        user = db.scalar(select(User).where(User.email == "invited@example.com"))
        user_id = user.id
        assert db.get(AccessGrant, user_id) is not None
    assert (
        api.post(
            f"/api/v1/admin/access/{user_id}/revoke",
            json={"current_password": "correct-horse-123!"},
        ).status_code
        == 200
    )
    assert (
        api.post(
            "/api/v1/auth/login",
            json={"email": "invited@example.com", "password": "new-invited-account-123!"},
        ).status_code
        == 403
    )


def test_recovery_non_enumeration_one_use_and_session_invalidation(api, pg):
    configured(api)
    known = api.post("/api/v1/auth/recovery/request", json={"email": "operator@example.com"})
    unknown = api.post("/api/v1/auth/recovery/request", json={"email": "unknown@example.com"})
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    with Session(pg) as db:
        row = db.scalar(select(IdentityToken).where(IdentityToken.purpose == "recovery"))
        token = bearer(api.app.state.settings, row)
        assert row.token_hash != token
    changed = api.post(
        "/api/v1/auth/recovery/complete",
        json={"token": token, "new_password": "recovered-correct-horse!"},
    )
    assert changed.status_code == 200
    assert api.get("/api/v1/auth/me").status_code == 401
    assert (
        api.post(
            "/api/v1/auth/recovery/complete",
            json={"token": token, "new_password": "recovered-again-horse!"},
        ).status_code
        == 400
    )
    assert (
        api.post(
            "/api/v1/auth/login",
            json={"email": "operator@example.com", "password": "correct-horse-123!"},
        ).status_code
        == 401
    )
    assert (
        api.post(
            "/api/v1/auth/login",
            json={"email": "operator@example.com", "password": "recovered-correct-horse!"},
        ).status_code
        == 200
    )


def test_disabled_mail_and_csrf_are_honest(api):
    signup(api)
    for email in ["user@example.com", "unknown@example.com"]:
        assert api.post("/api/v1/auth/recovery/request", json={"email": email}).status_code == 503
    api.headers["Origin"] = "https://attacker.example"
    assert (
        api.post("/api/v1/auth/recovery/request", json={"email": "user@example.com"}).status_code
        == 403
    )


@pytest.mark.parametrize("case", ["expired", "revoked", "replayed", "concurrent"])
def test_recovery_invalid_and_concurrent_redemption(api, pg, case):
    configured(api)
    api.post("/api/v1/auth/recovery/request", json={"email": "operator@example.com"})
    with Session(pg) as db:
        row = db.scalar(select(IdentityToken).where(IdentityToken.purpose == "recovery"))
        token = bearer(api.app.state.settings, row)
        if case == "expired":
            row.expires_at = now() - timedelta(seconds=1)
        if case == "revoked":
            row.revoked_at = now()
        if case == "replayed":
            row.consumed_at = now()
        db.commit()

    def redeem(_):
        with TestClient(create_app(api.app.state.settings)) as other:
            other.headers["Origin"] = api.app.state.settings.public_origin
            return other.post(
                "/api/v1/auth/recovery/complete",
                json={"token": token, "new_password": "new-recovery-password!"},
            ).status_code

    if case == "concurrent":
        with ThreadPoolExecutor(max_workers=2) as pool:
            assert sorted(pool.map(redeem, range(2))) == [200, 400]
    else:
        assert redeem(0) == 400


def test_worker_retry_expired_lease_idempotency_and_acceptance(api, pg):
    configured(api)
    identifier, token = invite(api, pg)
    calls = []

    def transport(request):
        calls.append(request.headers["Idempotency-Key"])
        body = json.loads(request.content)
        assert token in body["text"]
        return httpx.Response(503 if len(calls) == 1 else 200, json={"id": "fixture-receipt"})

    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        assert process_one(pg, api.app.state.settings, client)
        with Session(pg) as db:
            job = db.get(IdentityMail, identifier)
            assert job.state == "queued" and job.attempts == 1
            job.state = "leased"
            job.lease_until = now() - timedelta(seconds=1)
            job.next_attempt_at = now() - timedelta(seconds=1)
            db.commit()
        assert process_one(pg, api.app.state.settings, client)
        assert calls[0] == calls[1]
        with Session(pg) as db:
            job = db.get(IdentityMail, identifier)
            assert job.state == "accepted" and job.attempts == 2
        assert not process_one(pg, api.app.state.settings, client)


def test_operator_permission_and_identity_no_mass_assignment(api, pg):
    signup(api)
    assert (
        api.post(
            "/api/v1/admin/invitations",
            json={"email": "invited@example.com", "current_password": "correct-horse-123!"},
        ).status_code
        == 403
    )
    assert (
        api.post(
            "/api/v1/auth/recovery/request", json={"email": "user@example.com", "role": "owner"}
        ).status_code
        == 422
    )


def test_worker_terminal_failure_and_expired_work_cleanup(api, pg):
    from app.identity_worker import maintenance

    configured(api)
    identifier, _ = invite(api, pg)
    with Session(pg) as db:
        job = db.get(IdentityMail, identifier)
        job.attempts = 4
        db.commit()
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(503))) as client:
        assert process_one(pg, api.app.state.settings, client)
        assert not process_one(pg, api.app.state.settings, client)
    with Session(pg) as db:
        job = db.get(IdentityMail, identifier)
        assert job.state == "failed" and job.attempts == 5
        job.state = "queued"
        db.get(IdentityToken, identifier).expires_at = now() - timedelta(seconds=1)
        db.commit()
    maintenance(pg)
    with Session(pg) as db:
        assert db.get(IdentityMail, identifier).state == "cancelled"
