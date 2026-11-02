"""Real PostgreSQL replay, linking, ownership and session regressions for shared sign-in."""

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit
from uuid import UUID, uuid4

import pytest
from cryptography.fernet import Fernet
from fastapi import Request
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text, update
from sqlalchemy.orm import Session

from app import shared_identity
from app.models import (
    AccessGrant,
    AuthSession,
    IdentitySession,
    IdentityTransaction,
    SharedIdentity,
    User,
    now,
)
from app.onesa_identity import Identity, IdentityError
from tests.conftest import signup

TOKEN = "synthetic-test-access-token-" + "x" * 32


def enable(api, monkeypatch, email="shared@example.com", *, admin=False):
    settings = api.app.state.settings
    issuer = "https://account.example.test/api/v1/identity"
    api.app.state.settings = settings.model_copy(
        update={
            "identity_enabled": True,
            "identity_issuer": issuer,
            "identity_client_id": "ai-test",
            "identity_client_secret": "synthetic-" + "x" * 40,
            "identity_callback_url": settings.public_origin + "/api/v1/auth/onesa/callback",
            "identity_encryption_key": Fernet.generate_key().decode(),
            "environment": "test",
        }
    )
    identity = Identity(
        issuer,
        str(uuid4()),
        email,
        "Synthetic Shared User",
        int(time.time()) + 3600,
        int(time.time()),
        ("pwd", "otp") if admin else ("pwd",),
        ("global_admin",) if admin else (),
        ("ai",),
        {"ai": "admin" if admin else "user"},
        (),
    )
    current = {"identity": identity, "active": True, "exchanges": 0, "revoked": []}

    def validate(config, token):
        assert config.client_id == "ai-test" and token == TOKEN
        if not current["active"]:
            raise IdentityError("identity_rejected", "Session revoked")
        return current["identity"]

    def exchange(config, code, verifier):
        assert code == "synthetic-code" and len(verifier) >= 43
        current["exchanges"] += 1
        return TOKEN

    def revoke(config, token, *, all_sessions=False):
        assert token == TOKEN
        current["revoked"].append(all_sessions)
        return True

    monkeypatch.setattr(shared_identity, "validate_session", validate)
    monkeypatch.setattr(shared_identity, "exchange_code", exchange)
    monkeypatch.setattr(shared_identity, "revoke_session", revoke)
    return current


def start(api, *, next="/knowledge", reauthenticate=False):
    response = api.post(
        "/api/v1/auth/onesa/start", json={"next": next, "reauthenticate": reauthenticate}
    )
    assert response.status_code == 200, response.text
    url = urlsplit(response.json()["authorize_url"])
    query = parse_qs(url.query)
    assert query["code_challenge_method"] == ["S256"]
    return query["state"][0]


def finish(api, state):
    response = api.get(
        "/api/v1/auth/onesa/callback",
        params={"state": state, "code": "synthetic-code"},
        follow_redirects=False,
    )
    if "onesa_csrf" in api.cookies:
        api.headers["X-CSRF-Token"] = api.cookies["onesa_csrf"]
    return response


def test_shared_sign_in_creates_passwordless_local_owner_and_encrypts_token(api, pg, monkeypatch):
    current = enable(api, monkeypatch)
    response = finish(api, start(api))
    assert response.status_code == 303 and response.headers["location"] == "/knowledge"
    user = api.get("/api/v1/auth/me")
    assert user.status_code == 200
    assert user.json()["identity_mode"] == "onesa" and user.json()["global_admin"] is False
    with Session(pg) as db:
        row = db.get(User, UUID(user.json()["id"]))
        assert row.password_hash == "!shared-identity-no-local-password"
        mapping = db.scalar(select(SharedIdentity).where(SharedIdentity.user_id == row.id))
        assert mapping.subject == current["identity"].subject
        session = db.scalar(select(IdentitySession))
        assert TOKEN not in session.encrypted_token
    assert api.post("/api/v1/conversations", json={"title": "Shared account"}).status_code == 201
    assert current["exchanges"] == 1


def test_native_password_routes_refuse_when_shared_identity_is_enabled(api, monkeypatch):
    enable(api, monkeypatch)
    for path, body in [
        ("login", {"email": "shared@example.com", "password": "synthetic-password"}),
        (
            "register",
            {"email": "shared@example.com", "password": "synthetic-password", "display_name": "X"},
        ),
        ("recovery/request", {"email": "shared@example.com"}),
    ]:
        response = api.post("/api/v1/auth/" + path, json=body)
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "shared_sign_in_required"


@pytest.mark.parametrize("registration_mode", ["open", "invitation"])
def test_flag_rollback_rejects_shared_sessions_but_preserves_native_sessions(
    api, pg, monkeypatch, registration_mode
):
    native = signup(api, "native@example.com")
    native_cookies = dict(api.cookies)
    api.cookies.clear()
    api.headers.pop("X-CSRF-Token")
    enable(api, monkeypatch)
    assert finish(api, start(api)).status_code == 303
    shared = api.get("/api/v1/auth/me").json()
    with Session(pg) as db:
        # Even current native eligibility must not convert a central session
        # into authority that can bypass central revocation after flag rollback.
        for identifier in (native["id"], shared["id"]):
            db.add(AccessGrant(user_id=UUID(identifier), expires_at=now() + timedelta(days=1)))
        db.commit()
    api.app.state.settings = api.app.state.settings.model_copy(
        update={"identity_enabled": False, "registration_mode": registration_mode}
    )
    for method, path in [
        ("get", "/api/v1/auth/me"),
        ("get", "/api/v1/conversations"),
        ("post", "/api/v1/auth/refresh"),
    ]:
        response = getattr(api, method)(path)
        assert response.status_code == 401, response.text
        assert response.json()["error"]["code"] == "shared_sign_in_required"
    api.cookies.clear()
    api.cookies.update(native_cookies)
    api.headers["X-CSRF-Token"] = native_cookies["onesa_csrf"]
    assert api.get("/api/v1/auth/me").json()["id"] == native["id"]
    assert api.post("/api/v1/auth/refresh").status_code == 200
    with Session(pg) as db:
        assert db.scalar(select(func.count()).select_from(User)) == 2
        assert db.scalar(select(func.count()).select_from(SharedIdentity)) == 1
        assert db.scalar(select(func.count()).select_from(IdentitySession)) == 1


def test_native_authentication_supports_schema_without_identity_tables(api, pg):
    from app.auth import authenticated, digest

    schema = "native_auth_test_" + uuid4().hex
    with pg.connect() as connection:
        transaction = connection.begin()
        try:
            # Isolate the preceding table layout without altering public data or
            # invoking the intentionally forbidden identity migration downgrade.
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            User.__table__.create(connection)
            AuthSession.__table__.create(connection)
            assert connection.scalar(text("SELECT to_regclass('identity_sessions')")) is None
            with Session(bind=connection, join_transaction_mode="create_savepoint") as db:
                user = User(
                    email="native@example.com", display_name="Native", password_hash="synthetic"
                )
                db.add(user)
                db.flush()
                session = AuthSession(
                    user_id=user.id,
                    token_hash=digest("synthetic-test-native-session"),
                    csrf_hash=digest("synthetic-test-native-csrf"),
                    expires_at=now() + timedelta(hours=1),
                )
                db.add(session)
                db.flush()
                request = Request({"type": "http", "method": "GET", "headers": [], "app": api.app})
                assert authenticated(request, db, "synthetic-test-native-session") == (
                    user,
                    session,
                )
        finally:
            transaction.rollback()


def test_email_collision_requires_existing_password_and_preserves_user_and_owned_data(
    api, pg, monkeypatch
):
    native = signup(api, "shared@example.com")
    conversation = api.post("/api/v1/conversations", json={"title": "Retain my work"}).json()
    with Session(pg) as db:
        original_hash = db.get(User, UUID(native["id"])).password_hash
    enable(api, monkeypatch)
    response = finish(api, start(api))
    assert (
        response.status_code == 303 and response.headers["location"] == "/?identity=link_required"
    )
    assert api.get("/api/v1/auth/me").status_code == 401
    wrong = api.post(
        "/api/v1/auth/onesa/link",
        json={"email": "shared@example.com", "current_password": "wrong-password"},
    )
    assert wrong.status_code == 403
    linked = api.post(
        "/api/v1/auth/onesa/link",
        json={"email": "shared@example.com", "current_password": "correct-horse-123!"},
    )
    assert linked.status_code == 200
    api.headers["X-CSRF-Token"] = api.cookies["onesa_csrf"]
    assert api.get("/api/v1/auth/me").json()["id"] == native["id"]
    assert api.get("/api/v1/conversations/" + conversation["id"]).status_code == 200
    with Session(pg) as db:
        assert db.get(User, UUID(native["id"])).password_hash == original_hash
        assert db.scalar(select(func.count()).select_from(User)) == 1
        assert db.scalar(select(func.count()).select_from(SharedIdentity)) == 1


def test_callback_binding_expiry_and_replay_fail_before_exchange(api, monkeypatch):
    current = enable(api, monkeypatch)
    state = start(api)
    assert finish(api, "x" * 43).status_code == 400
    assert current["exchanges"] == 0
    cookie = api.cookies.get("onesa_identity_flow")
    with TestClient(api.app) as other:
        other.headers["Origin"] = api.app.state.settings.public_origin
        assert finish(other, state).status_code == 400
    assert finish(api, state).status_code == 303
    api.cookies.set("onesa_identity_flow", cookie, path="/api/v1/auth/onesa")
    assert finish(api, state).status_code == 400
    assert current["exchanges"] == 1


def test_concurrent_callback_has_one_code_exchange(api, monkeypatch):
    current = enable(api, monkeypatch)
    state = start(api)
    cookie = api.cookies.get("onesa_identity_flow")

    def callback(_):
        with TestClient(api.app) as client:
            client.cookies.set("onesa_identity_flow", cookie, path="/api/v1/auth/onesa")
            return finish(client, state).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(callback, [1, 2]))
    assert sorted(statuses) == [303, 400] and current["exchanges"] == 1


def test_expired_browser_transaction_never_exchanges_code(api, pg, monkeypatch):
    current = enable(api, monkeypatch)
    state = start(api)
    with Session(pg) as db:
        db.execute(update(IdentityTransaction).values(expires_at=now()))
        db.commit()
    assert finish(api, state).status_code == 400
    assert current["exchanges"] == 0


@pytest.mark.parametrize("change", ["logout", "disable"])
def test_concurrent_local_revocation_during_central_validation_is_rechecked(
    api, pg, monkeypatch, change
):
    current = enable(api, monkeypatch)
    assert finish(api, start(api)).status_code == 303

    def validate(config, token):
        with Session(pg) as db:
            if change == "logout":
                db.execute(update(AuthSession).values(revoked_at=now()))
            else:
                db.execute(update(User).values(status="disabled"))
            db.commit()
        return current["identity"]

    monkeypatch.setattr(shared_identity, "validate_session", validate)
    assert api.get("/api/v1/auth/me").status_code == 401


def test_sensitive_reauthentication_requires_a_live_same_account_session(api, pg, monkeypatch):
    current = enable(api, monkeypatch, admin=True)
    assert api.post("/api/v1/auth/onesa/start", json={"reauthenticate": True}).status_code == 401
    assert finish(api, start(api)).status_code == 303
    state = start(api, reauthenticate=True)
    original = current["identity"]
    current["identity"] = replace(original, subject=str(uuid4()), email="other@example.com")
    assert finish(api, state).status_code == 403
    with Session(pg) as db:
        assert db.scalar(select(func.count()).select_from(User)) == 1
    current["identity"] = original
    assert api.get("/api/v1/auth/me").status_code == 200
    state = start(api, reauthenticate=True)
    with Session(pg) as db:
        db.execute(update(AuthSession).values(revoked_at=now()))
        db.commit()
    assert finish(api, state).status_code == 403


def test_sensitive_reauthentication_preserves_the_same_user_and_owned_workspace(api, monkeypatch):
    enable(api, monkeypatch, admin=True)
    assert finish(api, start(api)).status_code == 303
    user = api.get("/api/v1/auth/me").json()
    old_cookie = api.cookies["onesa_session"]
    assert finish(api, start(api, reauthenticate=True)).status_code == 303
    assert api.cookies["onesa_session"] != old_cookie
    assert api.get("/api/v1/auth/me").json()["id"] == user["id"]


def test_verified_existing_user_id_grants_remain_scoped_and_require_fresh_mfa(api, monkeypatch):
    native = signup(api, "shared@example.com")
    current = enable(api, monkeypatch)
    api.app.state.settings = api.app.state.settings.model_copy(
        update={"documentation_engineering_user_ids": [native["id"]]}
    )
    assert finish(api, start(api)).status_code == 303
    assert (
        api.post(
            "/api/v1/auth/onesa/link",
            json={"email": "shared@example.com", "current_password": "correct-horse-123!"},
        ).status_code
        == 200
    )
    api.headers["X-CSRF-Token"] = api.cookies["onesa_csrf"]
    assert api.get("/api/v1/documentation/access").json()["engineering"] is False
    current["identity"] = replace(current["identity"], amr=("pwd", "otp"))
    assert api.get("/api/v1/documentation/access").json()["engineering"] is True
    current["identity"] = replace(current["identity"], auth_time=int(time.time()) - 301)
    assert api.get("/api/v1/documentation/access").json()["engineering"] is False
    current["active"] = False
    assert api.get("/api/v1/documentation/access").status_code == 401


def test_central_revocation_and_role_changes_are_effective_on_next_request(api, monkeypatch):
    current = enable(api, monkeypatch, admin=True)
    assert finish(api, start(api)).status_code == 303
    assert api.get("/api/v1/auth/me").json()["global_admin"] is True
    current["identity"] = replace(current["identity"], roles=(), product_roles={"ai": "user"})
    assert api.get("/api/v1/auth/me").json()["administrator"] is False
    current["active"] = False
    assert api.get("/api/v1/conversations").status_code == 401


def test_csrf_origin_and_fresh_auth_protect_sensitive_actions(api, monkeypatch):
    current = enable(api, monkeypatch)
    assert finish(api, start(api)).status_code == 303
    api.headers.pop("X-CSRF-Token")
    assert api.post("/api/v1/conversations", json={"title": "Denied"}).status_code == 403
    api.headers["X-CSRF-Token"] = api.cookies["onesa_csrf"]
    api.headers["Origin"] = "https://foreign.example.test"
    assert api.post("/api/v1/conversations", json={"title": "Denied"}).status_code == 403
    api.headers["Origin"] = api.app.state.settings.public_origin
    current["identity"] = replace(current["identity"], auth_time=int(time.time()) - 301)
    response = api.post("/api/v1/auth/sessions/revoke-others", json={"current_password": ""})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "identity_reauthentication_required"


def test_shared_logout_revokes_all_central_sessions_and_clears_local_cookie(api, monkeypatch):
    current = enable(api, monkeypatch)
    assert finish(api, start(api)).status_code == 303
    assert api.post("/api/v1/auth/logout").status_code == 204
    assert current["revoked"] == [True]
    assert "onesa_session" not in api.cookies


@pytest.mark.parametrize("status", [401, 403, 503])
def test_issuer_failure_during_logout_still_revokes_and_clears_local_session(
    api, monkeypatch, status
):
    enable(api, monkeypatch)
    assert finish(api, start(api)).status_code == 303

    def unavailable(*args, **kwargs):
        raise IdentityError("identity_unavailable", "Unavailable", status)

    monkeypatch.setattr(shared_identity, "revoke_session", unavailable)
    monkeypatch.setattr(shared_identity, "validate_session", unavailable)
    response = api.post("/api/v1/auth/logout")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "identity_logout_incomplete"
    assert "onesa_session" not in api.cookies
    assert api.get("/api/v1/auth/me").status_code == 401


def test_stale_central_token_logout_is_truthfully_partial(api, monkeypatch):
    enable(api, monkeypatch)
    assert finish(api, start(api)).status_code == 303
    monkeypatch.setattr(shared_identity, "revoke_session", lambda *args, **kwargs: False)
    response = api.post("/api/v1/auth/logout")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "identity_logout_incomplete"
    assert "onesa_session" not in api.cookies


@pytest.mark.parametrize(
    "target",
    [
        "https://evil.example.test",
        "//evil.example.test",
        "/\\evil",
        "/%2f%2fevil",
        "/api/v1/auth/logout",
    ],
)
def test_external_return_paths_are_rejected(api, monkeypatch, target):
    enable(api, monkeypatch)
    assert api.post("/api/v1/auth/onesa/start", json={"next": target}).status_code == 422


def test_ordinary_account_switch_revokes_the_previous_browser_session(api, pg, monkeypatch):
    current = enable(api, monkeypatch)
    assert finish(api, start(api)).status_code == 303
    old_cookie = api.cookies["onesa_session"]
    original = api.get("/api/v1/auth/me").json()["id"]
    current["identity"] = replace(
        current["identity"], subject=str(uuid4()), email="other@example.com"
    )
    assert finish(api, start(api)).status_code == 303
    assert api.get("/api/v1/auth/me").json()["id"] != original
    with Session(pg) as db:
        old = db.scalar(select(AuthSession).where(AuthSession.user_id == UUID(original)))
        assert old.revoked_at is not None
    with TestClient(api.app) as old_browser:
        old_browser.cookies.set("onesa_session", old_cookie)
        assert old_browser.get("/api/v1/auth/me").status_code == 401


def test_legacy_local_session_cannot_claim_global_logout_after_feature_activation(api, monkeypatch):
    signup(api, "shared@example.com")
    current = enable(api, monkeypatch)
    assert api.post("/api/v1/auth/logout").status_code == 503
    assert "onesa_session" not in api.cookies
    assert current["revoked"] == []


def test_lost_encryption_key_logout_clears_local_session_without_claiming_global_success(
    api, monkeypatch
):
    enable(api, monkeypatch)
    assert finish(api, start(api)).status_code == 303
    api.app.state.settings = api.app.state.settings.model_copy(
        update={"identity_encryption_key": Fernet.generate_key().decode()}
    )
    assert api.post("/api/v1/auth/logout").status_code == 503
    assert "onesa_session" not in api.cookies


def test_session_refresh_keeps_live_central_profile_roles_and_original_authentication_time(
    api, pg, monkeypatch
):
    current = enable(api, monkeypatch, admin=True)
    assert finish(api, start(api)).status_code == 303
    original = api.get("/api/v1/auth/me").json()
    auth_time = current["identity"].auth_time
    current["identity"] = replace(
        current["identity"], email="renamed@example.com", name="Updated central name"
    )
    old_cookie = api.cookies["onesa_session"]
    response = api.post("/api/v1/auth/refresh")
    assert response.status_code == 200
    result = response.json()
    assert result["id"] == original["id"] and result["identity_mode"] == "onesa"
    assert result["global_admin"] is True and result["administrator"] is True
    assert result["email"] == "renamed@example.com"
    assert result["display_name"] == "Updated central name"
    assert current["identity"].auth_time == auth_time
    assert api.cookies["onesa_session"] != old_cookie
    with Session(pg) as db:
        assert db.scalar(select(func.count()).select_from(IdentitySession)) == 2
        assert db.get(User, UUID(original["id"])).email == "shared@example.com"


@pytest.mark.parametrize("state", ["missing", "expired", "revoked"])
def test_global_logout_never_claims_success_without_a_live_local_binding(
    api, pg, monkeypatch, state
):
    current = enable(api, monkeypatch)
    if state != "missing":
        assert finish(api, start(api)).status_code == 303
        with Session(pg) as db:
            if state == "expired":
                db.execute(update(AuthSession).values(expires_at=now()))
            else:
                db.execute(update(AuthSession).values(revoked_at=now()))
            db.commit()
    response = api.post("/api/v1/auth/logout")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "identity_logout_incomplete"
    assert "onesa_session" not in api.cookies
    assert current["revoked"] == []


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("revocation", ["central", "logout", "expiry", "disable"])
def test_generation_stops_after_live_authority_is_revoked(api, pg, monkeypatch, stream, revocation):
    from app import chat
    from app.inference import MockModelClient
    from app.models import Conversation, InferenceRun, Message, ModelLease

    current = enable(api, monkeypatch)
    assert finish(api, start(api)).status_code == 303
    identifier = api.post("/api/v1/conversations", json={}).json()["id"]
    clock = [0.0]
    monkeypatch.setattr(chat, "monotonic", lambda: clock[0])

    class Revoked(MockModelClient):
        closed = False

        async def stream(self, messages):
            try:
                yield "Allowed first chunk"
                if revocation == "central":
                    current["active"] = False
                    clock[0] = 5.01
                else:
                    with Session(pg) as db:
                        if revocation == "logout":
                            db.execute(update(AuthSession).values(revoked_at=now()))
                        elif revocation == "expiry":
                            db.execute(update(AuthSession).values(expires_at=now()))
                        else:
                            db.execute(update(User).values(status="disabled"))
                        db.commit()
                yield "Private output after revocation"
            finally:
                self.closed = True

    model = Revoked()
    api.app.state.model_client = model
    response = api.post(
        "/api/v1/chat/completions",
        json={"conversation_id": identifier, "content": "Synthetic request", "stream": stream},
    )
    assert model.closed
    assert "Private output after revocation" not in response.text
    if stream:
        assert response.status_code == 200 and "event: error" in response.text
        assert '"code": "session_expired"' in response.text
        assert "event: message_end" not in response.text
    else:
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "session_expired"
    with Session(pg) as db:
        assert db.get(Conversation, UUID(identifier)).active_run_id is None
        assert db.scalar(select(InferenceRun)).status == "failed"
        assert db.scalar(select(func.count()).select_from(Message)) == 1
        assert db.scalar(select(func.count()).select_from(ModelLease)) == 0


@pytest.mark.parametrize("stream", [False, True])
def test_final_generation_validation_cannot_persist_a_centrally_revoked_response(
    api, pg, monkeypatch, stream
):
    from app import chat
    from app.inference import MockModelClient
    from app.models import Message

    current = enable(api, monkeypatch)
    assert finish(api, start(api)).status_code == 303
    identifier = api.post("/api/v1/conversations", json={}).json()["id"]
    monkeypatch.setattr(chat, "monotonic", lambda: 0.0)

    class EndRevoked(MockModelClient):
        async def stream(self, messages):
            yield "Allowed final chunk"
            current["active"] = False

    api.app.state.model_client = EndRevoked()
    response = api.post(
        "/api/v1/chat/completions",
        json={"conversation_id": identifier, "content": "Synthetic request", "stream": stream},
    )
    assert "session_expired" in response.text and "message_end" not in response.text
    with Session(pg) as db:
        assert db.scalar(select(func.count()).select_from(Message)) == 1


def test_shared_generation_checks_issuer_on_bounded_cadence_outside_event_loop(api, monkeypatch):
    import asyncio
    import threading

    from app import chat
    from app.inference import MockModelClient

    enable(api, monkeypatch)
    assert finish(api, start(api)).status_code == 303
    identifier = api.post("/api/v1/conversations", json={}).json()["id"]
    monkeypatch.setattr(chat, "monotonic", lambda: 0.0)
    validation_threads = []
    validate = shared_identity.validate_session

    def track(config, token):
        validation_threads.append(threading.get_ident())
        return validate(config, token)

    monkeypatch.setattr(shared_identity, "validate_session", track)

    class Chunks(MockModelClient):
        async def stream(self, messages):
            self.loop_thread = threading.get_ident()
            producer = asyncio.current_task()
            self.validations_before_stream = len(validation_threads)
            for _ in range(20):
                assert asyncio.current_task() is producer
                yield "Synthetic chunk "

    model = Chunks()
    api.app.state.model_client = model
    response = api.post(
        "/api/v1/chat/completions",
        json={"conversation_id": identifier, "content": "Synthetic request", "stream": False},
    )
    assert response.status_code == 200 and response.json()["message_id"]
    # One forced persistence check plus the existing capacity response boundary;
    # twenty streamed chunks must not cause twenty issuer roundtrips.
    assert len(validation_threads) - model.validations_before_stream <= 2
    assert all(thread != model.loop_thread for thread in validation_threads)


def test_quiet_upstream_is_cancelled_when_central_access_is_revoked(api, pg, monkeypatch):
    import asyncio
    import threading

    from app import chat
    from app.inference import MockModelClient
    from app.models import Conversation, Message, ModelLease

    current = enable(api, monkeypatch)
    assert finish(api, start(api)).status_code == 303
    identifier = api.post("/api/v1/conversations", json={}).json()["id"]
    clock = [0.0]
    monkeypatch.setattr(chat, "monotonic", lambda: clock[0])
    waiting, closed = threading.Event(), threading.Event()

    class Quiet(MockModelClient):
        async def stream(self, messages):
            try:
                self.release = asyncio.Event()
                self.loop = asyncio.get_running_loop()
                waiting.set()
                await self.release.wait()
                yield "Private delayed output"
            finally:
                closed.set()

    model = Quiet()
    api.app.state.model_client = model
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            api.post,
            "/api/v1/chat/completions",
            json={"conversation_id": identifier, "content": "Synthetic request", "stream": False},
        )
        try:
            assert waiting.wait(2)
            current["active"] = False
            clock[0] = 5.01
            assert closed.wait(2.5)
            response = future.result(timeout=2)
        finally:
            if waiting.is_set():
                model.loop.call_soon_threadsafe(model.release.set)
    assert response.status_code == 401
    with Session(pg) as db:
        assert db.get(Conversation, UUID(identifier)).active_run_id is None
        assert db.scalar(select(func.count()).select_from(Message)) == 1
        assert db.scalar(select(func.count()).select_from(ModelLease)) == 0


def test_local_revocation_between_final_validation_and_commit_cannot_persist_response(
    api, pg, monkeypatch
):
    from app import chat
    from app.models import Message

    enable(api, monkeypatch)
    assert finish(api, start(api)).status_code == 303
    identifier = api.post("/api/v1/conversations", json={}).json()["id"]
    original = chat.release

    def revoke_before_commit(request, conversation, run, status, *args, **kwargs):
        if status == "completed":
            with Session(pg) as db:
                db.execute(update(AuthSession).values(revoked_at=now()))
                db.commit()
        return original(request, conversation, run, status, *args, **kwargs)

    monkeypatch.setattr(chat, "release", revoke_before_commit)
    response = api.post(
        "/api/v1/chat/completions",
        json={"conversation_id": identifier, "content": "Synthetic request", "stream": False},
    )
    assert response.status_code == 503
    with Session(pg) as db:
        assert db.scalar(select(func.count()).select_from(Message)) == 1


def test_polled_browser_disconnect_never_persists_partial_generation(api, pg, monkeypatch):
    from fastapi import Request

    from app.inference import MockModelClient
    from app.models import Conversation, InferenceRun, Message, ModelLease

    enable(api, monkeypatch)
    assert finish(api, start(api)).status_code == 303
    identifier = api.post("/api/v1/conversations", json={}).json()["id"]
    polls = [0]

    async def disconnected(request):
        polls[0] += 1
        return polls[0] > 1

    class Chunks(MockModelClient):
        async def stream(self, messages):
            yield "Allowed first chunk"
            yield "Partial reply must not be committed"

    monkeypatch.setattr(Request, "is_disconnected", disconnected)
    api.app.state.model_client = Chunks()
    response = api.post(
        "/api/v1/chat/completions",
        json={"conversation_id": identifier, "content": "Synthetic request", "stream": True},
    )
    assert response.status_code == 200
    assert "Allowed first chunk" in response.text
    assert "Partial reply must not be committed" not in response.text
    assert "message_end" not in response.text
    with Session(pg) as db:
        assert db.get(Conversation, UUID(identifier)).active_run_id is None
        assert db.scalar(select(InferenceRun)).status == "cancelled"
        assert db.scalar(select(func.count()).select_from(Message)) == 1
        assert db.scalar(select(func.count()).select_from(ModelLease)) == 0


def test_reauthentication_locks_user_before_session_for_generation_commit_order(
    api, pg, monkeypatch
):
    import threading

    from sqlalchemy import event

    enable(api, monkeypatch, admin=True)
    assert finish(api, start(api)).status_code == 303
    owner = UUID(api.get("/api/v1/auth/me").json()["id"])
    state = start(api, reauthenticate=True)
    reached_lock = threading.Event()

    def before(conn, cursor, statement, parameters, context, many):
        if "FROM users" in statement and "FOR UPDATE" in statement:
            reached_lock.set()

    def after(conn, cursor, statement, parameters, context, many):
        if "FROM auth_sessions" in statement and "FOR UPDATE" in statement:
            reached_lock.set()

    with pg.connect() as connection:
        transaction = connection.begin()
        connection.execute(select(User.id).where(User.id == owner).with_for_update())
        event.listen(api.app.state.engine, "before_cursor_execute", before)
        event.listen(api.app.state.engine, "after_cursor_execute", after)
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(finish, api, state)
                try:
                    assert reached_lock.wait(3)
                    # The callback is waiting on our User lock. It must not
                    # already hold the session a generation commit needs next.
                    connection.execute(
                        select(AuthSession.id)
                        .where(AuthSession.user_id == owner)
                        .with_for_update(nowait=True)
                    )
                finally:
                    transaction.rollback()
                assert future.result(timeout=5).status_code == 303
        finally:
            event.remove(api.app.state.engine, "before_cursor_execute", before)
            event.remove(api.app.state.engine, "after_cursor_execute", after)
            if transaction.is_active:
                transaction.rollback()
