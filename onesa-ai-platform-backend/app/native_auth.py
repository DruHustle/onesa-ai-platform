"""Explicit browser consent and one-use S256 exchange for the installed AI app."""

import base64
import hashlib
import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal, cast
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth import (
    DB,
    authenticated,
    cookie_scheme,
    digest,
    eligible,
    lock_account,
    origin,
    safe_user,
    throttle,
    validate_authority,
)
from app.errors import fail
from app.models import AuthSession, IdentitySession, NativeAuthRequest, NativeSession, User, now
from app.schemas import SafeUser, Strict

router = APIRouter(prefix="/api/v1/auth/native", tags=["native authentication"])
native_scheme = HTTPBearer(auto_error=False, scheme_name="NativeSession")
NATIVE_ORIGIN = "onesaai://native"
NATIVE_CALLBACK = "onesaai://auth/callback"
NATIVE_SCHEMA_REVISION = "20261128_native_sessions"
_UUID = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
_ROUTES = (
    ("GET", r"/api/v1/auth/me"),
    ("POST", r"/api/v1/auth/native/(?:start|token|logout)"),
    ("GET", r"/api/v1/models(?:/[A-Za-z0-9_.-]{1,80})?"),
    ("GET|POST", r"/api/v1/conversations"),
    ("GET|PATCH|DELETE", rf"/api/v1/conversations/{_UUID}"),
    ("POST", rf"/api/v1/conversations/{_UUID}/cancel"),
    ("POST", r"/api/v1/chat/completions"),
    ("GET|POST", r"/api/v1/knowledge/documents"),
    ("GET|DELETE", rf"/api/v1/knowledge/documents/{_UUID}"),
    ("POST", rf"/api/v1/knowledge/documents/{_UUID}/reindex"),
    ("POST", r"/api/v1/knowledge/search"),
    ("GET", r"/api/v1/agents/tools"),
    ("GET|POST", r"/api/v1/agents/runs"),
    ("GET", rf"/api/v1/agents/runs/{_UUID}"),
    ("POST", rf"/api/v1/agents/runs/{_UUID}/cancel"),
    ("GET|POST", r"/api/v1/travel/trips"),
    ("GET|PUT|DELETE", rf"/api/v1/travel/trips/{_UUID}"),
)


class Start(Strict):
    code_challenge: str = Field(pattern=r"^[A-Za-z0-9_-]{43}$")
    state: str = Field(pattern=r"^[A-Za-z0-9_-]{43,128}$")
    platform: Literal["ios", "android"]


class Authorization(Strict):
    request_id: UUID
    authorize_url: str


class Consent(Strict):
    request_id: UUID
    app_name: Literal["Onesa AI Platform"] = "Onesa AI Platform"
    platform: Literal["ios", "android"]
    expires_at: datetime
    status: Literal["pending", "approved", "consumed"]
    user: SafeUser


class Approved(Strict):
    redirect_url: str


class Exchange(Strict):
    code: str = Field(pattern=r"^[A-Za-z0-9_-]{43}$")
    code_verifier: str = Field(pattern=r"^[A-Za-z0-9._~-]{43,128}$")


class NativeToken(Strict):
    access_token: str
    expires_at: datetime
    user: SafeUser


def enabled(request: Request) -> None:
    if not request.app.state.settings.native_client_enabled:
        fail(404, "native_disabled", "Native sign-in is not enabled")


def allowed_route(method: str, path: str) -> bool:
    return any(
        method in methods.split("|") and re.fullmatch(route, path) for methods, route in _ROUTES
    )


def native_headers(request: Request) -> None:
    if request.headers.get("origin") != NATIVE_ORIGIN:
        fail(403, "origin_rejected", "Request origin is not allowed")
    # Native networking must omit every cookie and CSRF header. Never silently
    # downgrade a mixed request to whichever authority happens to be valid.
    if "cookie" in request.headers or "x-csrf-token" in request.headers:
        fail(403, "mixed_authentication", "Use the native sign-in session")
    if request.headers.get("sec-fetch-site") not in {None, "none"}:
        fail(403, "origin_rejected", "Request origin is not allowed")


def request_guard(request: Request) -> None:
    """Run before admission; no CORS exception or browser credential fallback."""
    authorization = request.headers.get("authorization", "")
    native = request.headers.get("origin") == NATIVE_ORIGIN or authorization.startswith(
        "Bearer nai_"
    )
    if request.url.path.startswith("/api/v1/auth/native"):
        enabled(request)
    if native:
        enabled(request)
        native_headers(request)
        if not allowed_route(request.method, request.url.path):
            fail(403, "native_route_rejected", "This route is not available in the native app")


def bearer(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(native_scheme)] = None,
) -> str:
    enabled(request)
    native_headers(request)
    match = re.fullmatch(
        r"Bearer (nai_[A-Za-z0-9_-]{43})", request.headers.get("authorization", "")
    )
    if match is None:
        fail(401, "unauthorized", "Sign in to continue")
    return match.group(1)


def authenticate_native(request: Request, db: Session) -> tuple[User, AuthSession]:
    token = bearer(request)
    if not allowed_route(request.method, request.url.path):
        fail(403, "native_route_rejected", "This route is not available in the native app")
    row = db.scalar(
        select(AuthSession)
        .join(NativeSession, NativeSession.session_id == AuthSession.id)
        .where(
            NativeSession.token_hash == digest(token),
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > now(),
        )
    )
    user = db.get(User, row.user_id) if row else None
    if row is None or user is None or user.status != "active":
        fail(401, "unauthorized", "Sign in to continue")
    validate_authority(request, db, user, row)
    request.state.native_session_id = str(row.id)
    return user, row


def browser_auth(
    request: Request, db: DB, token: Annotated[str | None, Depends(cookie_scheme)]
) -> tuple[User, AuthSession]:
    enabled(request)
    if request.headers.get("authorization") is not None:
        fail(403, "mixed_authentication", "Approve with your browser sign-in")
    if request.headers.get("origin") is not None:
        origin(request)
    if request.headers.get("sec-fetch-site") == "cross-site":
        fail(403, "origin_rejected", "Request origin is not allowed")
    auth = authenticated(request, db, token)
    # GET binds the displayed owner too; require the same session CSRF proof.
    # Browsers do not always send Origin on a same-origin GET.
    csrf = request.headers.get("x-csrf-token", "")
    if not csrf or not secrets.compare_digest(digest(csrf), auth[1].csrf_hash):
        fail(403, "csrf_rejected", "Invalid CSRF token")
    return auth


BrowserAuth = Annotated[tuple[User, AuthSession], Depends(browser_auth)]
NativeBearer = Annotated[str, Depends(bearer)]


def current_request(db: Session, identifier: UUID, *, lock: bool = False) -> NativeAuthRequest:
    query = select(NativeAuthRequest).where(NativeAuthRequest.id == identifier)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    row = db.scalar(query)
    if row is None:
        fail(404, "native_request_unavailable", "Start sign-in again in the app")
    if row.expires_at <= now() or (
        row.code_expires_at is not None and row.code_expires_at <= now()
    ):
        fail(410, "native_request_expired", "Start sign-in again in the app")
    return row


def owner(row: NativeAuthRequest, auth: tuple[User, AuthSession]) -> None:
    if row.user_id != auth[0].id or row.browser_session_id != auth[1].id:
        fail(409, "native_account_changed", "Start sign-in again with your current account")


@router.post("/start", response_model=Authorization)
def start(body: Start, request: Request, db: DB) -> Authorization:
    enabled(request)
    native_headers(request)
    if "authorization" in request.headers:
        fail(403, "mixed_authentication", "Start a new native sign-in")
    throttle(request, db, "native-start")
    db.execute(
        delete(NativeAuthRequest).where(NativeAuthRequest.expires_at < now() - timedelta(hours=1))
    )
    row = NativeAuthRequest(
        platform=body.platform,
        code_challenge=body.code_challenge,
        state=body.state,
        expires_at=now() + timedelta(minutes=5),
    )
    db.add(row)
    db.commit()
    return Authorization(
        request_id=row.id,
        authorize_url=request.app.state.settings.public_origin
        + "/auth/native?request="
        + str(row.id),
    )


@router.get("/requests/{identifier}", response_model=Consent)
def details(identifier: UUID, request: Request, db: DB, auth: BrowserAuth) -> Consent:
    lock_account(db, auth)
    row = current_request(db, identifier, lock=True)
    if row.user_id is None:
        row.user_id, row.browser_session_id = auth[0].id, auth[1].id
    owner(row, auth)
    result = Consent(
        request_id=row.id,
        platform=cast(Literal["ios", "android"], row.platform),
        expires_at=row.code_expires_at or row.expires_at,
        status="consumed" if row.consumed_at else "approved" if row.approved_at else "pending",
        user=safe_user(request, auth[0]),
    )
    db.commit()
    return result


@router.post("/requests/{identifier}/approve", response_model=Approved)
def approve(identifier: UUID, request: Request, db: DB, auth: BrowserAuth) -> Approved:
    lock_account(db, auth)
    row = current_request(db, identifier, lock=True)
    # Approval is tied to the exact browser session that displayed this account.
    owner(row, auth)
    if row.approved_at is not None:
        fail(409, "native_request_used", "Start sign-in again in the app")
    code = secrets.token_urlsafe(32)
    row.code_hash = digest(code)
    row.approved_at = now()
    row.code_expires_at = min(row.expires_at, now() + timedelta(seconds=60))
    redirect_url = NATIVE_CALLBACK + "?" + urlencode({"code": code, "state": row.state})
    db.commit()
    return Approved(redirect_url=redirect_url)


@router.post("/token", response_model=NativeToken)
def exchange(body: Exchange, request: Request, db: DB) -> NativeToken:
    enabled(request)
    native_headers(request)
    if "authorization" in request.headers:
        fail(403, "mixed_authentication", "Exchange the one-use sign-in code")
    throttle(request, db, "native-token")
    row = db.scalar(
        select(NativeAuthRequest).where(NativeAuthRequest.code_hash == digest(body.code))
    )
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(body.code_verifier.encode("ascii")).digest())
        .rstrip(b"=")
        .decode("ascii")
    )
    if (
        row is None
        or row.consumed_at is not None
        or row.code_expires_at is None
        or row.code_expires_at <= now()
        or row.expires_at <= now()
        or not secrets.compare_digest(challenge, row.code_challenge)
    ):
        fail(401, "invalid_native_grant", "Start sign-in again in the app")
    identifier, browser_id, user_id = row.id, row.browser_session_id, row.user_id
    session = db.get(AuthSession, browser_id) if browser_id else None
    user = db.get(User, user_id) if user_id else None
    if (
        session is None
        or user is None
        or session.user_id != user.id
        or user.status != "active"
        or session.revoked_at is not None
        or session.expires_at <= now()
        or db.get(NativeSession, session.id) is not None
    ):
        fail(401, "invalid_native_grant", "Start sign-in again in the app")
    # Live issuer validation occurs before locking. Explicit rejection revokes
    # the approving browser authority; a temporary outage leaves the grant retryable.
    validate_authority(request, db, user, session)
    lock_account(db, (user, session))
    row = current_request(db, identifier, lock=True)
    owner(row, (user, session))
    if row.consumed_at is not None or row.code_hash != digest(body.code):
        fail(401, "invalid_native_grant", "Start sign-in again in the app")
    eligible(request, db, user)
    native_token = "nai_" + secrets.token_urlsafe(32)
    native = AuthSession(
        user_id=user.id,
        # These independent preimages are never issued to any client.
        token_hash=digest(secrets.token_urlsafe(32)),
        csrf_hash=digest(secrets.token_urlsafe(32)),
        expires_at=min(
            session.expires_at, now() + timedelta(hours=request.app.state.settings.session_hours)
        ),
    )
    identity = None
    if request.app.state.settings.identity_enabled:
        from app.shared_identity import current_identity

        identity = current_identity(request, user.id)
        if identity is None:
            fail(401, "invalid_native_grant", "Start sign-in again in the app")
        native.expires_at = min(native.expires_at, datetime.fromtimestamp(identity.expires_at, UTC))
    if native.expires_at <= now():
        fail(401, "invalid_native_grant", "Start sign-in again in the app")
    db.add(native)
    db.flush()
    if identity is not None:
        binding = db.get(IdentitySession, session.id, populate_existing=True)
        if (
            binding is None
            or binding.issuer != identity.issuer
            or binding.subject != identity.subject
        ):
            fail(401, "invalid_native_grant", "Start sign-in again in the app")
        db.add(
            IdentitySession(
                session_id=native.id,
                issuer=binding.issuer,
                subject=binding.subject,
                encrypted_token=binding.encrypted_token,
            )
        )
    db.add(
        NativeSession(session_id=native.id, token_hash=digest(native_token), platform=row.platform)
    )
    row.consumed_at = now()
    result = NativeToken(
        access_token=native_token, expires_at=native.expires_at, user=safe_user(request, user)
    )
    db.commit()
    return result


@router.post("/logout", status_code=204)
def logout(db: DB, token: NativeBearer) -> Response:
    row = db.scalar(
        select(AuthSession)
        .join(NativeSession, NativeSession.session_id == AuthSession.id)
        .where(NativeSession.token_hash == digest(token))
        .with_for_update(of=AuthSession)
    )
    if row is not None:
        if row.revoked_at is None:
            row.revoked_at = now()
        db.execute(delete(IdentitySession).where(IdentitySession.session_id == row.id))
        db.commit()
    return Response(status_code=204)
