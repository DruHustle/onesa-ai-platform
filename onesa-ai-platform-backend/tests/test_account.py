"""Account controls against real PostgreSQL, including token and owner isolation."""

from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.models import User
from tests.conftest import signup

PASSWORD = "correct-horse-123!"
NEW_PASSWORD = "changed-horse-456!"


def another_session(api: TestClient) -> tuple[str, str]:
    old = (api.cookies["onesa_session"], api.cookies["onesa_csrf"])
    api.cookies.clear()
    assert (
        api.post(
            "/api/v1/auth/login", json={"email": "user@example.com", "password": PASSWORD}
        ).status_code
        == 200
    )
    api.headers["X-CSRF-Token"] = api.cookies["onesa_csrf"]
    return old


def test_profile_is_persistent_and_owner_scoped(api: TestClient, pg: Engine) -> None:
    first = signup(api)
    assert api.patch("/api/v1/auth/profile", json={"display_name": "   "}).status_code == 422
    assert (
        api.patch(
            "/api/v1/auth/profile", json={"display_name": " Alice ", "email": "other@example.com"}
        ).status_code
        == 422
    )
    response = api.patch("/api/v1/auth/profile", json={"display_name": " Alice "})
    assert response.status_code == 200
    assert response.json() == {**first, "display_name": "Alice"}
    assert api.get("/api/v1/auth/me").json()["display_name"] == "Alice"
    signup(api, "other@example.com")
    api.patch("/api/v1/auth/profile", json={"display_name": "Bob"})
    with Session(pg) as db:
        assert (
            db.scalar(select(User).where(User.email == "user@example.com")).display_name == "Alice"
        )


def test_revoke_others_keeps_current_and_hides_secrets(api: TestClient) -> None:
    signup(api)
    old_token, old_csrf = another_session(api)
    result = api.get("/api/v1/auth/sessions")
    assert result.status_code == 200
    assert result.json()["total"] == 2
    assert sum(row["current"] for row in result.json()["items"]) == 1
    for row in result.json()["items"]:
        assert set(row) == {"id", "created_at", "expires_at", "current"}
    assert (
        api.post(
            "/api/v1/auth/sessions/revoke-others", json={"current_password": "wrong"}
        ).status_code
        == 403
    )
    assert api.get("/api/v1/auth/sessions").json()["total"] == 2
    assert (
        api.post(
            "/api/v1/auth/sessions/revoke-others", json={"current_password": PASSWORD}
        ).status_code
        == 204
    )
    assert api.get("/api/v1/auth/sessions").json()["total"] == 1
    api.cookies.set("onesa_session", old_token)
    api.headers["X-CSRF-Token"] = old_csrf
    assert api.get("/api/v1/auth/me").status_code == 401
    assert api.patch("/api/v1/auth/profile", json={"display_name": "Revoked"}).status_code == 401


def test_password_change_rotates_every_session_and_requires_csrf(api: TestClient) -> None:
    signup(api)
    old_token, _ = another_session(api)
    current_token = api.cookies["onesa_session"]
    body = {"current_password": PASSWORD, "new_password": NEW_PASSWORD}
    csrf = api.headers.pop("X-CSRF-Token")
    assert api.post("/api/v1/auth/password", json=body).status_code == 403
    api.headers["X-CSRF-Token"] = csrf
    api.headers["Origin"] = "https://untrusted.example"
    assert api.post("/api/v1/auth/password", json=body).status_code == 403
    api.headers["Origin"] = api.app.state.settings.public_origin
    assert (
        api.post("/api/v1/auth/password", json={**body, "current_password": "wrong"}).status_code
        == 403
    )
    assert (
        api.post("/api/v1/auth/password", json={**body, "new_password": PASSWORD}).status_code
        == 422
    )
    assert api.post("/api/v1/auth/password", json=body).status_code == 200
    assert api.cookies["onesa_session"] not in {old_token, current_token}
    api.headers["X-CSRF-Token"] = api.cookies["onesa_csrf"]
    assert api.get("/api/v1/auth/sessions").json()["total"] == 1
    for token in (old_token, current_token):
        api.cookies.clear()
        api.cookies.set("onesa_session", token)
        assert api.post("/api/v1/auth/refresh").status_code == 401
    api.cookies.clear()
    assert (
        api.post(
            "/api/v1/auth/login", json={"email": "user@example.com", "password": PASSWORD}
        ).status_code
        == 401
    )
    assert (
        api.post(
            "/api/v1/auth/login", json={"email": "user@example.com", "password": NEW_PASSWORD}
        ).status_code
        == 200
    )


def test_session_revoked_after_authentication_cannot_commit_profile(
    api: TestClient, pg: Engine, monkeypatch
) -> None:
    import threading
    from concurrent.futures import ThreadPoolExecutor

    from sqlalchemy import update

    import app.auth as auth_module
    from app.models import AuthSession, now

    signup(api)
    entered, release = threading.Event(), threading.Event()
    original = auth_module.lock_account

    def paused(db, auth):
        entered.set()
        assert release.wait(timeout=5)
        return original(db, auth)

    monkeypatch.setattr(auth_module, "lock_account", paused)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(
            api.patch, "/api/v1/auth/profile", json={"display_name": "Must not persist"}
        )
        try:
            assert entered.wait(timeout=3)
            with Session(pg) as db:
                db.execute(update(AuthSession).values(revoked_at=now()))
                db.commit()
        finally:
            release.set()
        assert pending.result(timeout=5).status_code == 401
    with Session(pg) as db:
        assert db.query(User).one().display_name == "Tester"
