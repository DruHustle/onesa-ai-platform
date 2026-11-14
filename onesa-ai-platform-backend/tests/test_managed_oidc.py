"""Local Auth0-compatible issuance and AI-owned resource identity."""

import json
import time
from dataclasses import replace
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.managed_oidc import NS, exchange, validate
from app.onesa_identity import IdentityConfig, IdentityError, authorization_url, new_transaction


@pytest.fixture
def signed():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    config = IdentityConfig(
        "https://issuer.example/",
        "ai-web",
        "test" * 10,
        "https://ai.example/callback",
        "ai",
        False,
        "https://api.ai.example",
        json.dumps({"keys": [{**public, "kid": "fixture"}]}),
        "https://legacy.example/api/v1/identity",
        "https://admin.example/account",
    )
    uid = str(uuid4())

    def pair(at=None, profile=None):
        now = int(time.time())
        shared = {"iss": config.issuer, "sub": "auth0|synthetic", "iat": now, "exp": now + 240}
        access = {
            **shared,
            "aud": config.audience,
            NS + "products": ["ai"],
            NS + "roles": ["user"],
            NS + "user_id": uid,
            **(at or {}),
        }
        user = {
            **shared,
            "aud": config.client_id,
            "email_verified": True,
            "email": "member@example.com",
            "name": "Member",
            "nonce": "registered-nonce",
            **(profile or {}),
        }
        return {
            k: jwt.encode(v, key, algorithm="RS256", headers={"kid": "fixture"})
            for k, v in [("access_token", access), ("id_token", user)]
        }

    return config, uid, pair


def test_provider_exchange_and_local_key_restart(signed):
    config, uid, pair = signed
    state, nonce, verifier = new_transaction()
    url = urlsplit(authorization_url(config, state, nonce, verifier, reauthenticate=True))
    q = parse_qs(url.query)
    assert (
        url.path == "/authorize"
        and q["audience"] == [config.audience]
        and q["code_challenge_method"] == ["S256"]
    )

    def response(req):
        assert req.url.path == "/oauth/token" and req.method == "POST"
        assert parse_qs(req.content.decode())["code_verifier"] == [verifier]
        return httpx.Response(200, json={**pair(), "token_type": "Bearer"})

    with httpx.Client(transport=httpx.MockTransport(response)) as client:
        packed = exchange(config, "controlled-code", verifier, "registered-nonce", client)
        with pytest.raises(IdentityError):
            exchange(config, "controlled-code", verifier, "wrong-nonce", client)
    recovered = validate(replace(config), packed)
    assert recovered.subject == uid and recovered.issuer == config.issuer
    assert recovered.email == "member@example.com" and not recovered.global_admin


@pytest.mark.parametrize(
    ("changes", "profile"),
    [
        ({"aud": "other"}, {}),
        ({NS + "products": ["robot"]}, {}),
        ({NS + "user_id": "member@example.com"}, {}),
        ({NS + "roles": ["admin"]}, {}),
        ({"exp": int(time.time()) + 600}, {}),
        ({"exp": 10}, {}),
        ({}, {"sub": "other"}),
        ({}, {"email_verified": False}),
        ({}, {"aud": "other"}),
    ],
)
def test_mismatch_or_privilege_denied(signed, changes, profile):
    config, _, pair = signed
    with pytest.raises(IdentityError):
        validate(config, json.dumps(pair(changes, profile)))


def test_managed_callback_preserves_legacy_ai_owner_and_conversation(api, pg, monkeypatch, signed):
    from uuid import UUID

    from cryptography.fernet import Fernet
    from sqlalchemy.orm import Session

    from app import managed_oidc
    from app.models import SharedIdentity
    from tests.conftest import signup

    cfg, stable, pair = signed
    local = signup(api, "member@example.com")
    conversation = api.post("/api/v1/conversations", json={"title": "Retained research"})
    assert conversation.status_code == 201
    with Session(pg) as db:
        db.add(SharedIdentity(issuer=cfg.mapping_issuer, subject=stable, user_id=UUID(local["id"])))
        db.commit()
    api.cookies.clear()
    settings = api.app.state.settings
    api.app.state.settings = settings.model_copy(
        update={
            "identity_enabled": True,
            "identity_issuer": cfg.issuer,
            "identity_client_id": cfg.client_id,
            "identity_client_secret": cfg.client_secret,
            "identity_audience": cfg.audience,
            "identity_public_jwks": cfg.public_jwks,
            "identity_mapping_issuer": cfg.mapping_issuer,
            "identity_account_url": cfg.account_url,
            "identity_encryption_key": Fernet.generate_key().decode(),
            "identity_callback_url": settings.public_origin + "/api/v1/auth/onesa/callback",
        }
    )
    assert api.get("/api/v1/auth/onesa/config").json()["account_url"] == cfg.account_url
    next_path = "/?conversation=" + conversation.json()["id"]
    start = api.post("/api/v1/auth/onesa/start", json={"next": next_path})
    assert start.status_code == 200
    q = parse_qs(urlsplit(start.json()["authorize_url"]).query)
    assert q["audience"] == [cfg.audience]
    issued = pair(profile={"nonce": q["nonce"][0]})
    monkeypatch.setattr(
        managed_oidc, "_request", lambda *a, **k: {**issued, "token_type": "Bearer"}
    )
    end = api.get(
        "/api/v1/auth/onesa/callback",
        params={"code": "fixture", "state": q["state"][0]},
        follow_redirects=False,
    )
    assert end.status_code == 303 and end.headers["location"] == next_path
    user = api.get("/api/v1/auth/me")
    assert user.status_code == 200 and user.json()["id"] == local["id"]
    assert not user.json()["global_admin"]
    work = api.get("/api/v1/conversations")
    assert work.status_code == 200 and conversation.json()["id"] in work.text
