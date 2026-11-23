import json
from datetime import timedelta
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi import Request, Response

from app.auth import LogoutOptions, digest, logout
from app.config import Settings
from app.models import IdentitySession, now

ISSUER = "https://auth.onesa.eu/"
ORIGIN = "https://platform.example.test"


class LogoutDatabase:
    def __init__(self, issuer=ISSUER):
        self.session = SimpleNamespace(
            id="synthetic-session",
            csrf_hash=digest("synthetic-csrf"),
            revoked_at=None,
            expires_at=now() + timedelta(minutes=5),
        )
        self.binding = SimpleNamespace(issuer=issuer) if issuer else None
        self.committed = False

    def scalar(self, statement):
        return self.session

    def get(self, model, identifier):
        assert model is IdentitySession and identifier == self.session.id
        assert self.committed
        return self.binding

    def commit(self):
        assert self.session.revoked_at is not None
        self.committed = True


def logout_request(*, enabled=True):
    settings = SimpleNamespace(
        identity_enabled=True,
        identity_browser_logout_enabled=enabled,
        identity_issuer=ISSUER,
        identity_client_id="synthetic-platform",
        public_origin=ORIGIN,
    )
    request = Request(
        {
            "type": "http",
            "app": SimpleNamespace(state=SimpleNamespace(settings=settings)),
            "headers": [
                (b"origin", ORIGIN.encode()),
                (b"cookie", b"onesa_session=synthetic-session"),
                (b"x-csrf-token", b"synthetic-csrf"),
            ],
        }
    )
    request.state.request_id = "synthetic-request"
    return request


def test_browser_logout_revokes_local_session_and_returns_fixed_managed_destination():
    db = LogoutDatabase()
    result = logout(logout_request(), Response(), db, LogoutOptions(browser=True))
    assert db.committed and db.session.revoked_at
    assert result.status_code == 200
    assert result.headers["cache-control"] == "private, no-store"
    assert "onesa_session=" in result.headers.getlist("set-cookie")[0]
    assert "Max-Age=0" in result.headers.getlist("set-cookie")[0]
    url = urlsplit(json.loads(result.body)["browser_logout_url"])
    assert (url.scheme, url.netloc, url.path) == ("https", "auth.onesa.eu", "/oidc/logout")
    assert parse_qs(url.query) == {
        "client_id": ["synthetic-platform"],
        "post_logout_redirect_uri": [ORIGIN + "/"],
    }


@pytest.mark.parametrize(
    ("enabled", "options", "binding"),
    [
        (False, LogoutOptions(browser=True), ISSUER),
        (True, None, ISSUER),
        (True, LogoutOptions(browser=True), None),
        (True, LogoutOptions(browser=True), "https://other.example.test/"),
    ],
)
def test_missing_browser_opt_in_or_matching_binding_keeps_partial_signout(
    monkeypatch, enabled, options, binding
):
    monkeypatch.setattr("app.shared_identity.sign_out", lambda *_: False)
    db = LogoutDatabase(binding)
    result = logout(logout_request(enabled=enabled), Response(), db, options)
    assert db.committed and db.session.revoked_at
    assert result.status_code == 503
    assert json.loads(result.body)["error"]["code"] == "identity_logout_incomplete"
    assert "Max-Age=0" in result.headers.getlist("set-cookie")[0]


def test_browser_logout_cannot_be_enabled_with_default_local_credentials():
    with pytest.raises(ValueError, match="Browser sign-out requires managed Onesa identity"):
        Settings(identity_browser_logout_enabled=True)
