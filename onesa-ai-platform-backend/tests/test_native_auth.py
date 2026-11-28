"""Real PostgreSQL native consent, transport isolation and authority regressions."""

import base64
import hashlib
import importlib.util
import json
import os
import secrets
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from uuid import UUID, uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app import chat, shared_identity
from app.auth import digest
from app.config import Settings
from app.inference import MockModelClient
from app.main import create_app
from app.models import (
    AccessGrant,
    AuthSession,
    Base,
    Conversation,
    IdentitySession,
    InferenceRun,
    Message,
    ModelLease,
    NativeAuthRequest,
    NativeSession,
    RateBucket,
    SharedIdentity,
    User,
    now,
)
from app.native_auth import NATIVE_ORIGIN, NATIVE_SCHEMA_REVISION
from app.onesa_identity import Identity, IdentityError
from tests.conftest import signup


@pytest.fixture(scope="module")
def native_pg(request):
    url = os.environ.get("ONESA_NATIVE_TEST_DATABASE_URL")
    if not url:
        # Normal integration CI uses the full migration/pgvector fixture.
        return request.getfixturevalue("pg")
    parsed = make_url(url)
    if (
        os.environ.get("ONESA_NATIVE_TEST_CONFIRM_ISOLATED") != "1"
        or parsed.host not in {"127.0.0.1", "::1"}
        or not (parsed.database or "").endswith("_test")
    ):
        raise RuntimeError("An explicitly disposable loopback native-auth database is required")
    engine = create_engine(url)
    # Focused local auth acceptance needs no vector extension. Build only the
    # prerequisite legacy tables, then execute the actual additive migration.
    tables = [
        model.__table__
        for model in (
            User,
            AuthSession,
            IdentitySession,
            SharedIdentity,
            RateBucket,
            AccessGrant,
            Conversation,
            Message,
            InferenceRun,
            ModelLease,
        )
    ]
    Base.metadata.create_all(engine, tables=tables)
    path = Path(__file__).parents[1] / "migrations/versions/20261128_native_sessions.py"
    spec = importlib.util.spec_from_file_location("native_session_migration", path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        connection.execute(
            text("CREATE TABLE alembic_version (version_num varchar(32) PRIMARY KEY)")
        )
        connection.execute(
            text("INSERT INTO alembic_version VALUES (:revision)"),
            {"revision": NATIVE_SCHEMA_REVISION},
        )
    request.addfinalizer(engine.dispose)
    return engine


@pytest.fixture
def native_api(native_pg):
    with native_pg.begin() as connection:
        connection.execute(text("TRUNCATE users, rate_buckets CASCADE"))
        connection.execute(text("TRUNCATE native_auth_requests"))
    settings = Settings(
        database_url=native_pg.url.render_as_string(hide_password=False),
        environment="test",
        native_client_enabled=True,
        auth_rate_limit=1000,
    )
    with TestClient(create_app(settings)) as client:
        client.headers["origin"] = settings.public_origin
        signup(client)
        yield client


def client(api, token=None):
    result = TestClient(api.app)
    result.headers["origin"] = NATIVE_ORIGIN
    if token:
        result.headers["authorization"] = "Bearer " + token
    return result


def pending(api, *, platform="ios"):
    verifier, state = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    )
    mobile = client(api)
    response = mobile.post(
        "/api/v1/auth/native/start",
        json={
            "platform": platform,
            "state": state,
            "code_challenge": challenge,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert (
        body["authorize_url"]
        == api.app.state.settings.public_origin + "/auth/native?request=" + body["request_id"]
    )
    return mobile, body["request_id"], verifier, state


def approved(api, *, platform="ios"):
    mobile, identifier, verifier, state = pending(api, platform=platform)
    details = api.get("/api/v1/auth/native/requests/" + identifier)
    assert details.status_code == 200, details.text
    assert details.json()["app_name"] == "Onesa AI Platform"
    assert details.json()["platform"] == platform
    assert details.json()["status"] == "pending"
    response = api.post("/api/v1/auth/native/requests/" + identifier + "/approve", json={})
    assert response.status_code == 200, response.text
    destination = urlsplit(response.json()["redirect_url"])
    assert (destination.scheme, destination.netloc, destination.path) == (
        "onesaai",
        "auth",
        "/callback",
    )
    query = parse_qs(destination.query)
    assert query["state"] == [state] and set(query) == {"code", "state"}
    return mobile, identifier, verifier, query["code"][0]


def exchange(api, *, platform="ios"):
    mobile, identifier, verifier, code = approved(api, platform=platform)
    response = mobile.post(
        "/api/v1/auth/native/token", json={"code": code, "code_verifier": verifier}
    )
    assert response.status_code == 200, response.text
    assert "set-cookie" not in response.headers and not mobile.cookies
    result = response.json()
    mobile.headers["authorization"] = "Bearer " + result["access_token"]
    return mobile, result, identifier


def central(api, native_pg, monkeypatch):
    issuer = "https://account.example.test/api/v1/identity"
    identity = Identity(
        issuer,
        str(uuid4()),
        "user@example.com",
        "Synthetic native owner",
        int(time.time()) + 1800,
        int(time.time()),
        ("pwd",),
        (),
        ("ai",),
        {"ai": "user"},
        (),
    )
    key = Fernet.generate_key()
    cipher = Fernet(key)
    api.app.state.settings = api.app.state.settings.model_copy(
        update={
            "identity_enabled": True,
            "identity_issuer": issuer,
            "identity_client_id": "ai-test",
            "identity_client_secret": "synthetic-" + "x" * 40,
            "identity_callback_url": api.app.state.settings.public_origin
            + "/api/v1/auth/onesa/callback",
            "identity_encryption_key": key.decode(),
        }
    )
    # Generated fixture authority is accepted only by the local issuer substitute.
    synthetic_token = secrets.token_urlsafe(32)
    with Session(native_pg) as db:
        browser = db.scalar(
            select(AuthSession).where(
                AuthSession.token_hash == digest(api.cookies["onesa_session"])
            )
        )
        assert browser is not None
        db.add(SharedIdentity(issuer=issuer, subject=identity.subject, user_id=browser.user_id))
        db.add(
            IdentitySession(
                session_id=browser.id,
                issuer=issuer,
                subject=identity.subject,
                encrypted_token=cipher.encrypt(synthetic_token.encode()).decode(),
            )
        )
        db.commit()
    state = {"mode": "active", "identity": identity, "calls": 0}

    def validate(config, token):
        assert config.client_id == "ai-test" and token == synthetic_token
        state["calls"] += 1
        if state["mode"] == "unavailable":
            raise IdentityError("identity_unavailable", "Synthetic issuer outage", 503)
        if state["mode"] == "revoked":
            raise IdentityError("identity_rejected", "Synthetic issuer revocation")
        hook = state.pop("hook", None)
        if hook:
            hook()
        return state["identity"]

    monkeypatch.setattr(shared_identity, "validate_session", validate)
    monkeypatch.setattr(
        shared_identity,
        "revoke_session",
        lambda *_a, **_k: pytest.fail(
            "Native logout must not revoke the browser or central session"
        ),
    )
    return state


@pytest.mark.parametrize("platform", ["ios", "android"])
def test_native_exchange_uses_separate_hashed_authority_and_existing_owner(
    native_api, native_pg, monkeypatch, platform
):
    state = central(native_api, native_pg, monkeypatch)
    browser_cookies = dict(native_api.cookies)
    mobile, result, identifier = exchange(native_api, platform=platform)
    assert result["user"]["email"] == state["identity"].email
    assert result["user"]["identity_mode"] == "onesa"
    assert (
        datetime.fromisoformat(result["expires_at"].replace("Z", "+00:00")).timestamp()
        <= state["identity"].expires_at
    )
    assert dict(native_api.cookies) == browser_cookies
    assert mobile.get("/api/v1/auth/me").json()["id"] == result["user"]["id"]
    with Session(native_pg) as db:
        native = db.scalar(select(NativeSession))
        assert native.platform == platform and native.token_hash == digest(result["access_token"])
        authority = db.get(AuthSession, native.session_id)
        browser = db.scalar(
            select(AuthSession).where(
                AuthSession.token_hash == digest(browser_cookies["onesa_session"])
            )
        )
        assert authority.id != browser.id and authority.user_id == browser.user_id
        assert authority.token_hash != native.token_hash
        assert (
            db.get(IdentitySession, authority.id).encrypted_token
            == db.get(IdentitySession, browser.id).encrypted_token
        )
        assert db.get(NativeAuthRequest, UUID(identifier)).consumed_at is not None
    created = mobile.post("/api/v1/conversations", json={"title": "Native owned conversation"})
    assert created.status_code == 201
    assert native_api.get("/api/v1/conversations/" + created.json()["id"]).status_code == 200


def test_consent_binds_displayed_account_and_requires_browser_csrf(native_api):
    _, identifier, _, _ = pending(native_api)
    path = "/api/v1/auth/native/requests/" + identifier
    assert native_api.get(path, headers={"x-csrf-token": ""}).status_code == 403
    assert (
        native_api.get(path, headers={"origin": "https://external.example.test"}).status_code == 403
    )
    assert native_api.post(path + "/approve", json={}).status_code == 409
    assert native_api.get(path).status_code == 200
    other = TestClient(native_api.app)
    other.headers["origin"] = native_api.app.state.settings.public_origin
    signup(other, "other@example.com")
    assert other.get(path).status_code == 409
    assert other.post(path + "/approve", json={}).status_code == 409
    assert (
        native_api.post(path + "/approve", json={}, headers={"x-csrf-token": ""}).status_code == 403
    )
    assert native_api.post(path + "/approve", json={}).status_code == 200
    assert native_api.post(path + "/approve", json={}).status_code == 409


@pytest.mark.parametrize(
    "changes",
    [
        {"platform": "web"},
        {"state": "x"},
        {"code_challenge": "plain-text"},
        {"redirect_uri": "https://external.example.test"},
        {"code_challenge_method": "plain"},
    ],
)
def test_start_accepts_only_fixed_s256_native_contract(native_api, changes):
    body = {"platform": "ios", "state": "s" * 43, "code_challenge": "c" * 43, **changes}
    assert client(native_api).post("/api/v1/auth/native/start", json=body).status_code == 422


def test_wrong_pkce_does_not_consume_but_code_is_one_use(native_api, native_pg):
    mobile, identifier, verifier, code = approved(native_api)
    path = "/api/v1/auth/native/token"
    assert mobile.post(path, json={"code": code, "code_verifier": "z" * 43}).status_code == 401
    assert mobile.post(path, json={"code": code, "code_verifier": verifier}).status_code == 200
    assert mobile.post(path, json={"code": code, "code_verifier": verifier}).status_code == 401
    with Session(native_pg) as db:
        assert db.scalar(select(func.count()).select_from(NativeSession)) == 1
        assert db.get(NativeAuthRequest, UUID(identifier)).consumed_at is not None


def test_concurrent_exchange_issues_exactly_one_native_session(native_api, native_pg):
    _, _, verifier, code = approved(native_api)

    def submit():
        return (
            client(native_api)
            .post("/api/v1/auth/native/token", json={"code": code, "code_verifier": verifier})
            .status_code
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = sorted(pool.map(lambda _: submit(), range(2)))
    assert statuses == [200, 401]
    with Session(native_pg) as db:
        assert db.scalar(select(func.count()).select_from(NativeSession)) == 1


def test_expired_code_and_revoked_browser_cannot_be_exchanged(native_api, native_pg):
    mobile, identifier, verifier, code = approved(native_api)
    with Session(native_pg) as db:
        row = db.get(NativeAuthRequest, UUID(identifier))
        row.code_expires_at = now() - timedelta(seconds=1)
        db.commit()
    assert native_api.get("/api/v1/auth/native/requests/" + identifier).status_code == 410
    assert (
        mobile.post(
            "/api/v1/auth/native/token", json={"code": code, "code_verifier": verifier}
        ).status_code
        == 401
    )
    mobile, identifier, verifier, code = approved(native_api)
    with Session(native_pg) as db:
        row = db.get(NativeAuthRequest, UUID(identifier))
        db.get(AuthSession, row.browser_session_id).revoked_at = now()
        db.commit()
    assert (
        mobile.post(
            "/api/v1/auth/native/token", json={"code": code, "code_verifier": verifier}
        ).status_code
        == 401
    )
    with Session(native_pg) as db:
        assert db.scalar(select(func.count()).select_from(NativeSession)) == 0


@pytest.mark.parametrize("mode,expected", [("revoked", 401), ("unavailable", 503)])
def test_exchange_revalidates_central_authority_and_only_outages_are_retryable(
    native_api, native_pg, monkeypatch, mode, expected
):
    state = central(native_api, native_pg, monkeypatch)
    mobile, _, verifier, code = approved(native_api)
    state["mode"] = mode
    body = {"code": code, "code_verifier": verifier}
    assert mobile.post("/api/v1/auth/native/token", json=body).status_code == expected
    state["mode"] = "active"
    assert mobile.post("/api/v1/auth/native/token", json=body).status_code == (
        200 if mode == "unavailable" else 401
    )


def test_account_disable_during_issuer_call_cannot_issue_native_authority(
    native_api, native_pg, monkeypatch
):
    state = central(native_api, native_pg, monkeypatch)
    mobile, _, verifier, code = approved(native_api)

    def disable():
        with native_pg.begin() as connection:
            connection.execute(update(User).values(status="disabled"))

    state["hook"] = disable
    assert (
        mobile.post(
            "/api/v1/auth/native/token", json={"code": code, "code_verifier": verifier}
        ).status_code
        == 401
    )
    with Session(native_pg) as db:
        assert db.scalar(select(func.count()).select_from(NativeSession)) == 0


def test_native_cookie_and_browser_bearer_are_not_interchangeable(native_api):
    mobile, result, _ = exchange(native_api)
    cookie = TestClient(native_api.app)
    cookie.headers["origin"] = native_api.app.state.settings.public_origin
    cookie.cookies.set("onesa_session", result["access_token"])
    assert cookie.get("/api/v1/auth/me").status_code == 401
    assert (
        client(native_api, native_api.cookies["onesa_session"]).get("/api/v1/auth/me").status_code
        == 401
    )
    assert (
        mobile.get(
            "/api/v1/auth/me",
            headers={"cookie": "onesa_session=" + native_api.cookies["onesa_session"]},
        ).status_code
        == 403
    )
    assert mobile.get("/api/v1/auth/me", headers={"x-csrf-token": "synthetic"}).status_code == 403
    assert (
        mobile.get(
            "/api/v1/auth/me", headers={"origin": native_api.app.state.settings.public_origin}
        ).status_code
        == 403
    )
    assert (
        mobile.get(
            "/api/v1/auth/me", headers={"origin": "https://external.example.test"}
        ).status_code
        == 403
    )
    assert (
        mobile.get("/api/v1/auth/me", headers={"sec-fetch-site": "cross-site"}).status_code == 403
    )
    assert native_api.get("/api/v1/auth/me").status_code == 200


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/v1/auth/sessions"),
        ("POST", "/api/v1/auth/refresh"),
        ("POST", "/api/v1/auth/logout"),
        ("POST", "/api/v1/auth/onesa/start"),
        ("GET", "/api/v1/auth/native/requests/" + str(uuid4())),
        ("GET", "/api/v1/documentation/access"),
        ("GET", "/api/v1/cybersecurity/findings"),
        ("GET", "/api/v1/industrial/investigations"),
        ("GET", "/api/v1/twins/assets"),
        ("POST", "/api/v1/inference/completions"),
        ("GET", "/metrics"),
        ("DELETE", "/api/v1/account"),
        ("POST", "/api/v1/travel/trips/" + str(uuid4())),
    ],
)
def test_native_transport_has_an_exact_product_route_allowlist(native_api, method, path):
    mobile, _, _ = exchange(native_api)
    assert mobile.request(method, path).status_code == 403


def test_native_session_rechecks_owner_and_local_and_central_revocation(
    native_api, native_pg, monkeypatch
):
    state = central(native_api, native_pg, monkeypatch)
    mobile, _, _ = exchange(native_api)
    created = mobile.post("/api/v1/conversations", json={}).json()
    with Session(native_pg) as db:
        outsider = User(
            email="outsider@example.com", password_hash="unusable", display_name="Outsider"
        )
        db.add(outsider)
        db.flush()
        other = Conversation(user_id=outsider.id)
        db.add(other)
        db.commit()
        other_id = str(other.id)
    assert mobile.get("/api/v1/conversations/" + other_id).status_code == 404
    assert mobile.get("/api/v1/conversations/" + created["id"]).status_code == 200
    state["mode"] = "revoked"
    assert mobile.get("/api/v1/auth/me").status_code == 401
    state["mode"] = "active"
    assert mobile.get("/api/v1/auth/me").status_code == 401
    assert native_api.get("/api/v1/auth/me").status_code == 200


def test_revoke_other_sessions_revokes_native_backing_authority(native_api):
    mobile, _, _ = exchange(native_api)
    response = native_api.post(
        "/api/v1/auth/sessions/revoke-others", json={"current_password": "correct-horse-123!"}
    )
    assert response.status_code == 204, response.text
    assert mobile.get("/api/v1/auth/me").status_code == 401
    assert native_api.get("/api/v1/auth/me").status_code == 200


@pytest.mark.parametrize(
    "tool", ["industrial_facts", "cybersecurity_evidence_v1", "knowledge_search"]
)
def test_native_agent_scope_cannot_invoke_optional_evidence_tools(native_api, native_pg, tool):
    mobile, _, _ = exchange(native_api)
    settings = native_api.app.state.settings
    settings.industrial_demo_enabled = settings.industrial_import_enabled = True
    settings.cybersecurity_enabled = True
    # Avoid optional event capture against this intentionally auth-only fixture;
    # the real registry and permission decision remain unchanged.
    from unittest.mock import patch

    from app import cybersecurity

    with patch.object(cybersecurity, "capture_decision"):
        native_tools = mobile.get("/api/v1/agents/tools")
        browser_tools = native_api.get("/api/v1/agents/tools")
        assert native_tools.status_code == browser_tools.status_code == 200
        assert {item["name"] for item in native_tools.json()["items"]} == {
            "text_stats",
            "arithmetic",
        }
        assert tool in {item["name"] for item in browser_tools.json()["items"]}
        response = mobile.post(
            "/api/v1/agents/runs",
            json={
                "goal": "Synthetic restricted evidence request",
                "allowed_tools": [tool],
                "steps": [],
            },
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "tool_not_allowed"
        # A forged Origin alone cannot activate native authority on cookie traffic.
        assert (
            native_api.get("/api/v1/agents/tools", headers={"origin": NATIVE_ORIGIN}).status_code
            == 403
        )
    with Session(native_pg) as db:
        assert db.scalar(select(func.count()).select_from(ModelLease)) == 0


def test_native_logout_works_during_issuer_outage_and_does_not_revoke_browser(
    native_api, native_pg, monkeypatch
):
    state = central(native_api, native_pg, monkeypatch)
    mobile, _, _ = exchange(native_api)
    state["mode"] = "unavailable"
    before = state["calls"]
    assert mobile.post("/api/v1/auth/native/logout").status_code == 204
    assert mobile.post("/api/v1/auth/native/logout").status_code == 204
    assert state["calls"] == before
    state["mode"] = "active"
    assert mobile.get("/api/v1/auth/me").status_code == 401
    assert native_api.get("/api/v1/auth/me").status_code == 200


@pytest.mark.parametrize("stream", [False, True])
def test_native_generation_cannot_persist_after_central_revocation(
    native_api, native_pg, monkeypatch, stream
):
    state = central(native_api, native_pg, monkeypatch)
    mobile, _, _ = exchange(native_api)
    identifier = mobile.post("/api/v1/conversations", json={}).json()["id"]
    monkeypatch.setattr(chat, "monotonic", lambda: 0.0)

    class EndRevoked(MockModelClient):
        async def stream(self, messages):
            yield "Synthetic final chunk"
            state["mode"] = "revoked"

    native_api.app.state.model_client = EndRevoked()
    response = mobile.post(
        "/api/v1/chat/completions",
        json={
            "conversation_id": identifier,
            "content": "Synthetic native request",
            "stream": stream,
        },
    )
    assert "session_expired" in response.text and "message_end" not in response.text
    with Session(native_pg) as db:
        assert db.scalar(select(func.count()).select_from(Message)) == 1
        assert db.scalar(select(func.count()).select_from(ModelLease)) == 0


def test_native_generation_final_local_fence_still_applies(native_api, native_pg, monkeypatch):
    mobile, _, _ = exchange(native_api)
    identifier = mobile.post("/api/v1/conversations", json={}).json()["id"]
    original = chat.release

    def revoke_before_commit(request, conversation, run, status, *args, **kwargs):
        if status == "completed":
            with native_pg.begin() as connection:
                connection.execute(
                    update(AuthSession)
                    .where(
                        AuthSession.id.in_(select(NativeSession.session_id)),
                    )
                    .values(revoked_at=now())
                )
        return original(request, conversation, run, status, *args, **kwargs)

    monkeypatch.setattr(chat, "release", revoke_before_commit)
    response = mobile.post(
        "/api/v1/chat/completions",
        json={
            "conversation_id": identifier,
            "content": "Synthetic native request",
            "stream": False,
        },
    )
    assert response.status_code >= 400
    with Session(native_pg) as db:
        assert db.scalar(select(func.count()).select_from(Message)) == 1


@pytest.mark.parametrize("revocation", ["local", "central"])
def test_quiet_native_generation_stops_on_authoritative_revocation(
    native_api, native_pg, monkeypatch, revocation
):
    import asyncio
    import threading

    state = central(native_api, native_pg, monkeypatch)
    mobile, result, _ = exchange(native_api)
    identifier = mobile.post("/api/v1/conversations", json={}).json()["id"]
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
                yield "Synthetic delayed output"
            finally:
                closed.set()

    model = Quiet()
    native_api.app.state.model_client = model
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            mobile.post,
            "/api/v1/chat/completions",
            json={"conversation_id": identifier, "content": "Synthetic request", "stream": False},
        )
        try:
            assert waiting.wait(2)
            if revocation == "central":
                state["mode"] = "revoked"
            else:
                assert (
                    client(native_api, result["access_token"])
                    .post("/api/v1/auth/native/logout")
                    .status_code
                    == 204
                )
            clock[0] = 5.01
            assert closed.wait(2.5)
            assert future.result(timeout=2).status_code == 401
        finally:
            if waiting.is_set() and not closed.is_set():
                model.loop.call_soon_threadsafe(model.release.set)
    with Session(native_pg) as db:
        assert db.get(Conversation, UUID(identifier)).active_run_id is None
        assert db.scalar(select(func.count()).select_from(Message)) == 1
        assert db.scalar(select(func.count()).select_from(ModelLease)) == 0


def test_identity_flag_rollback_does_not_convert_native_central_authority(
    native_api, native_pg, monkeypatch
):
    central(native_api, native_pg, monkeypatch)
    mobile, _, _ = exchange(native_api)
    native_api.app.state.settings.identity_enabled = False
    response = mobile.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "shared_sign_in_required"


def test_native_bridge_preserves_managed_issuer_mapping_and_short_signed_authority(
    native_api, native_pg
):
    import jwt
    from cryptography.hazmat.primitives.asymmetric import rsa

    from app.managed_oidc import NS

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    issuer = "https://issuer.example.test/"
    mapping_issuer = "https://legacy.example.test/api/v1/identity"
    audience, client_id, subject = "https://ai-api.example.test", "native-test-client", str(uuid4())
    instant = int(time.time())
    common = {
        "iss": issuer,
        "sub": "auth0|synthetic-native",
        "iat": instant,
        "exp": instant + 240,
    }
    claims = {
        "access_token": {
            **common,
            "aud": audience,
            NS + "products": ["ai"],
            NS + "roles": ["user"],
            NS + "user_id": subject,
        },
        "id_token": {
            **common,
            "aud": client_id,
            "email_verified": True,
            "email": "user@example.com",
            "name": "Synthetic managed owner",
        },
    }
    packed = json.dumps(
        {
            name: jwt.encode(value, key, algorithm="RS256", headers={"kid": "native-fixture"})
            for name, value in claims.items()
        }
    )
    encryption = Fernet.generate_key()
    jwks = json.dumps({"keys": [{**public, "kid": "native-fixture"}]})
    native_api.app.state.settings = native_api.app.state.settings.model_copy(
        update={
            "identity_enabled": True,
            "identity_issuer": issuer,
            "identity_client_id": client_id,
            "identity_client_secret": "synthetic-" + "x" * 40,
            "identity_audience": audience,
            "identity_public_jwks": jwks,
            "identity_mapping_issuer": mapping_issuer,
            "identity_account_url": "https://account.example.test/account",
            "identity_callback_url": native_api.app.state.settings.public_origin
            + "/api/v1/auth/onesa/callback",
            "identity_encryption_key": encryption.decode(),
        }
    )
    with Session(native_pg) as db:
        browser = db.scalar(
            select(AuthSession).where(
                AuthSession.token_hash == digest(native_api.cookies["onesa_session"])
            )
        )
        assert browser is not None
        owner_id = browser.user_id
        db.add(SharedIdentity(issuer=mapping_issuer, subject=subject, user_id=owner_id))
        db.add(
            IdentitySession(
                session_id=browser.id,
                issuer=issuer,
                subject=subject,
                encrypted_token=Fernet(encryption).encrypt(packed.encode()).decode(),
            )
        )
        db.commit()
    mobile, result, _ = exchange(native_api)
    assert result["user"]["id"] == str(owner_id)
    assert (
        datetime.fromisoformat(result["expires_at"].replace("Z", "+00:00")).timestamp()
        <= instant + 240
    )
    assert mobile.get("/api/v1/auth/me").status_code == 200
    native_api.app.state.settings.identity_public_jwks = json.dumps(
        {
            "keys": [{**public, "kid": "different-key"}],
        }
    )
    assert mobile.get("/api/v1/auth/me").status_code == 401
    native_api.app.state.settings.identity_public_jwks = jwks
    assert mobile.get("/api/v1/auth/me").status_code == 401
    assert native_api.get("/api/v1/auth/me").status_code == 200


def test_default_off_and_older_schema_readiness_remain_compatible(native_api, native_pg):
    from sqlalchemy import event

    native_api.app.state.settings.native_client_enabled = False
    statements = []

    def observe(_connection, _cursor, statement, _parameters, _context, _many):
        statements.append(statement)

    event.listen(native_pg, "before_cursor_execute", observe)
    # The application owns a distinct Engine; observe that one as well.
    event.listen(native_api.app.state.engine, "before_cursor_execute", observe)
    try:
        with native_pg.begin() as connection:
            connection.execute(
                text("UPDATE alembic_version SET version_num='20261104_email_presentation'")
            )
        assert native_api.get("/core-ready").status_code == 200
        assert native_api.get("/api/v1/auth/me").status_code == 200
        assert client(native_api).post("/api/v1/auth/native/start", json={}).status_code == 404
        assert not any("native_" in statement.lower() for statement in statements)
        native_api.app.state.settings.native_client_enabled = True
        assert native_api.get("/core-ready").status_code == 503
    finally:
        event.remove(native_pg, "before_cursor_execute", observe)
        event.remove(native_api.app.state.engine, "before_cursor_execute", observe)
        with native_pg.begin() as connection:
            connection.execute(
                text("UPDATE alembic_version SET version_num=:revision"),
                {"revision": NATIVE_SCHEMA_REVISION},
            )
