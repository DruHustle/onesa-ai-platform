"""Shared Onesa sign-in adapter for native AI ownership and host-only sessions."""

import json
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit
from uuid import UUID

from argon2.exceptions import InvalidHashError, VerificationError
from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import Field
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import DB, authenticated, digest, hasher, origin, throttle
from app.errors import fail
from app.models import (
    AuthSession,
    IdentityAudit,
    IdentitySession,
    IdentityTransaction,
    SharedIdentity,
    User,
    now,
)
from app.onesa_identity import (
    Identity,
    IdentityConfig,
    IdentityError,
    authorization_url,
    exchange_code,
    new_transaction,
    revoke_session,
    validate_session,
)
from app.schemas import PasswordProof, Strict

router = APIRouter(prefix="/api/v1/auth/onesa", tags=["shared Onesa identity"])
FLOW_COOKIE = "onesa_identity_flow"


class Start(Strict):
    next: str = Field(default="/", max_length=1000)
    reauthenticate: bool = False


class Authorization(Strict):
    authorize_url: str


class Method(Strict):
    enabled: bool
    account_url: str | None = None


class Link(PasswordProof):
    email: str = Field(min_length=3, max_length=254)


def configuration(request: Request) -> IdentityConfig:
    config = request.app.state.settings
    if not config.identity_enabled:
        fail(404, "identity_disabled", "Shared Onesa sign-in is not enabled")
    return IdentityConfig(
        config.identity_issuer,
        config.identity_client_id,
        config.identity_client_secret,
        config.identity_callback_url,
        "ai",
        config.environment in {"development", "test"},
    )


def cipher(request: Request) -> Fernet:
    return Fernet(request.app.state.settings.identity_encryption_key.encode("ascii"))


def encrypt(request: Request, value: str) -> str:
    return cipher(request).encrypt(value.encode()).decode("ascii")


def decrypt(request: Request, value: str) -> str:
    try:
        return cipher(request).decrypt(value.encode("ascii")).decode()
    except (InvalidToken, ValueError, UnicodeError):
        fail(401, "identity_rejected", "Your Onesa session is no longer valid")


def safe_next(value: str) -> str:
    parsed = urlsplit(value)
    if (
        not value.startswith("/")
        or value.startswith("//")
        or "\\" in value
        or any(ord(char) < 32 for char in value)
        or parsed.scheme
        or parsed.netloc
        or parsed.fragment
        or "%" in parsed.path
        or parsed.path.startswith("/api/")
    ):
        fail(422, "invalid_return_path", "Choose an application page to return to")
    return value


def live_identity(request: Request, token: str) -> Identity:
    try:
        identity = validate_session(configuration(request), token)
    except IdentityError as error:
        fail(error.status, error.code, error.message)
    request.state.onesa_identity = identity
    return identity


def authenticate_shared(
    request: Request, db: Session, user: User, session: AuthSession
) -> Identity:
    record = db.get(IdentitySession, session.id)
    if record is None or record.issuer != request.app.state.settings.identity_issuer:
        fail(401, "shared_sign_in_required", "Continue with your Onesa account")
    identity = live_identity(request, decrypt(request, record.encrypted_token))
    if identity.subject != record.subject:
        fail(401, "identity_rejected", "Your Onesa session is no longer valid")
    # The issuer call can take several seconds. A concurrent local logout or
    # account disable must not be hidden by SQLAlchemy's earlier identity map.
    current_user = db.scalar(
        select(User).where(User.id == user.id).execution_options(populate_existing=True)
    )
    current_session = db.scalar(
        select(AuthSession)
        .where(AuthSession.id == session.id)
        .execution_options(populate_existing=True)
    )
    if (
        current_user is None
        or current_user.status != "active"
        or current_session is None
        or current_session.revoked_at is not None
        or current_session.expires_at <= now()
        or current_session.user_id != current_user.id
    ):
        fail(401, "unauthorized", "Sign in to continue")
    mapping = db.scalar(
        select(SharedIdentity).where(
            SharedIdentity.issuer == identity.issuer,
            SharedIdentity.subject == identity.subject,
            SharedIdentity.user_id == user.id,
        )
    )
    if mapping is None:
        fail(401, "identity_rejected", "Your Onesa session is no longer valid")
    request.state.onesa_user_id = str(user.id)
    return identity


def current_identity(request: Request, user_id: object | None = None) -> Identity | None:
    identity = getattr(request.state, "onesa_identity", None)
    if (
        not request.app.state.settings.identity_enabled
        or not isinstance(identity, Identity)
        or (user_id is not None and getattr(request.state, "onesa_user_id", None) != str(user_id))
    ):
        return None
    return identity


def administrator(request: Request, user_id: object) -> bool:
    identity = current_identity(request, user_id)
    return bool(
        identity
        and (identity.global_admin or identity.product_roles.get("ai") == "admin")
        and {"otp", "mfa"}.intersection(identity.amr)
    )


def require_recent(request: Request, *, mfa: bool = False) -> None:
    identity = current_identity(request)
    if identity is None or not identity.fresh(mfa=mfa):
        fail(403, "identity_reauthentication_required", "Confirm your Onesa sign-in to continue")


def attach(
    request: Request, db: Session, session: AuthSession, identity: Identity, token: str
) -> None:
    session.expires_at = min(session.expires_at, datetime.fromtimestamp(identity.expires_at, UTC))
    db.flush()
    db.add(
        IdentitySession(
            session_id=session.id,
            issuer=identity.issuer,
            subject=identity.subject,
            encrypted_token=encrypt(request, token),
        )
    )


def sign_out(request: Request, db: Session, session: AuthSession) -> bool:
    record = db.get(IdentitySession, session.id)
    if record is not None:
        try:
            return revoke_session(
                configuration(request), decrypt(request, record.encrypted_token), all_sessions=True
            )
        except IdentityError:
            return False
        except HTTPException:
            # Losing an encryption key invalidates this local session but cannot
            # establish that the remote authority revoked its other sessions.
            return False
    return False


@router.get("/config", response_model=Method)
def method(request: Request) -> Method:
    if not request.app.state.settings.identity_enabled:
        return Method(enabled=False)
    config = configuration(request)
    # The issuer is the existing Company Portal; this link is informational only.
    return Method(
        enabled=True, account_url=config.issuer.removesuffix("/api/v1/identity") + "/account"
    )


@router.post("/start", response_model=Authorization)
def start(body: Start, request: Request, response: Response, db: DB) -> Authorization:
    config = configuration(request)
    origin(request)
    throttle(request, db, "shared-sign-in")
    target = safe_next(body.next)
    binding = None
    if body.reauthenticate:
        user, session = authenticated(request, db, request.cookies.get("onesa_session"))
        identity = current_identity(request, user.id)
        if identity is None:
            fail(401, "shared_sign_in_required", "Continue with your Onesa account")
        binding = {
            "user_id": str(user.id),
            "session_id": str(session.id),
            "subject": identity.subject,
            "issuer": identity.issuer,
        }
    state, nonce, verifier = new_transaction()
    browser = secrets.token_urlsafe(32)
    db.execute(delete(IdentityTransaction).where(IdentityTransaction.expires_at <= now()))
    db.add(
        IdentityTransaction(
            state_hash=digest(state),
            browser_hash=digest(browser),
            payload=encrypt(
                request,
                json.dumps(
                    {
                        "nonce": nonce,
                        "verifier": verifier,
                        "next": target,
                        "reauthenticate": body.reauthenticate,
                        "binding": binding,
                    }
                ),
            ),
            expires_at=now() + timedelta(minutes=5),
        )
    )
    db.commit()
    response.set_cookie(
        FLOW_COOKIE,
        state + "." + browser,
        httponly=True,
        secure=request.app.state.settings.secure_cookies,
        samesite="lax",
        max_age=300,
        path="/api/v1/auth/onesa",
    )
    return Authorization(
        authorize_url=authorization_url(
            config, state, nonce, verifier, reauthenticate=body.reauthenticate
        )
    )


def transaction(request: Request, db: Session, state: str | None = None) -> IdentityTransaction:
    pieces = request.cookies.get(FLOW_COOKIE, "").split(".")
    if len(pieces) != 2 or any(len(piece) != 43 for piece in pieces):
        fail(400, "identity_callback_invalid", "Sign-in has expired. Please start again")
    if state is not None and not secrets.compare_digest(pieces[0], state):
        fail(400, "identity_callback_invalid", "Sign-in has expired. Please start again")
    row = db.scalar(
        select(IdentityTransaction)
        .where(IdentityTransaction.state_hash == digest(pieces[0]))
        .with_for_update()
    )
    if (
        row is None
        or row.expires_at <= now()
        or not secrets.compare_digest(row.browser_hash, digest(pieces[1]))
    ):
        fail(400, "identity_callback_invalid", "Sign-in has expired. Please start again")
    return row


def issue_shared(
    request: Request, response: Response, db: Session, user: User, identity: Identity, token: str
) -> None:
    from app.auth import issue

    if user.status != "active":
        fail(403, "account_disabled", "This application account is disabled")
    request.state.onesa_identity = identity
    request.state.onesa_user_id = str(user.id)
    issue(request, response, db, user, shared=(identity, token))
    response.delete_cookie(FLOW_COOKIE, path="/api/v1/auth/onesa")


@router.get("/callback", include_in_schema=False)
def callback(
    request: Request, db: DB, state: str = "", code: str = "", error: str = ""
) -> Response:
    configuration(request)
    row = transaction(request, db, state)
    if row.consumed_at is not None:
        fail(400, "identity_callback_invalid", "Sign-in has already been used. Please start again")
    payload = json.loads(decrypt(request, row.payload))
    row.consumed_at = now()
    db.commit()  # Code exchange is never retried after an ambiguous network result.
    if error or not code:
        response = RedirectResponse("/?identity=cancelled", status_code=303)
        response.delete_cookie(FLOW_COOKIE, path="/api/v1/auth/onesa")
        return response
    try:
        token = exchange_code(configuration(request), code, payload["verifier"])
    except IdentityError:
        response = RedirectResponse("/?identity=unavailable", status_code=303)
        response.delete_cookie(FLOW_COOKIE, path="/api/v1/auth/onesa")
        return response
    try:
        identity = live_identity(request, token)
    except HTTPException as failure:
        reason = (
            "access_required"
            if isinstance(failure.detail, dict)
            and failure.detail.get("code") == "application_access_required"
            else "unavailable"
        )
        response = RedirectResponse("/?identity=" + reason, status_code=303)
        response.delete_cookie(FLOW_COOKIE, path="/api/v1/auth/onesa")
        return response
    if payload.get("reauthenticate"):
        binding = payload["binding"]
        current_user = db.scalar(
            select(User)
            .where(User.id == UUID(binding["user_id"]))
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        current_session = db.scalar(
            select(AuthSession)
            .where(
                AuthSession.id == UUID(binding["session_id"]),
                AuthSession.user_id == UUID(binding["user_id"]),
                AuthSession.token_hash == digest(request.cookies.get("onesa_session", "")),
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if (
            current_user is None
            or current_user.status != "active"
            or current_session is None
            or current_session.revoked_at is not None
            or current_session.expires_at <= now()
            or identity.subject != binding["subject"]
            or identity.issuer != binding["issuer"]
            or not identity.fresh(mfa=True)
        ):
            fail(
                403,
                "identity_reauthentication_required",
                "Confirm the same Onesa account with a fresh sign-in and MFA",
            )
    mapping = db.scalar(
        select(SharedIdentity).where(
            SharedIdentity.issuer == identity.issuer, SharedIdentity.subject == identity.subject
        )
    )
    user = (
        db.scalar(
            select(User)
            .where(User.id == mapping.user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if mapping
        else None
    )
    if payload.get("reauthenticate") and (
        user is None or str(user.id) != payload["binding"]["user_id"]
    ):
        fail(403, "identity_reauthentication_required", "Your application account has changed")
    if mapping is None:
        existing = db.scalar(select(User).where(User.email == identity.email))
        if existing is not None:
            # Email is never proof of ownership of an existing native account.
            row.payload = encrypt(
                request,
                json.dumps(
                    {
                        "pending_link": True,
                        "token": token,
                        "subject": identity.subject,
                        "email": identity.email,
                        "next": payload["next"],
                    }
                ),
            )
            row.expires_at = now() + timedelta(minutes=5)
            db.commit()
            return RedirectResponse("/?identity=link_required", status_code=303)
        user = User(
            email=identity.email,
            display_name=identity.name[:80],
            password_hash="!shared-identity-no-local-password",
        )
        db.add(user)
        try:
            db.flush()
            db.add(
                SharedIdentity(issuer=identity.issuer, subject=identity.subject, user_id=user.id)
            )
            db.flush()
        except IntegrityError:
            db.rollback()
            fail(
                409, "identity_link_conflict", "Account changed during sign-in. Please start again"
            )
        db.add(IdentityAudit(actor_id=user.id, event="identity.created", record_id=user.id))
    if user is None:
        fail(401, "identity_rejected", "The application account is unavailable")
    response = RedirectResponse(safe_next(payload["next"]), status_code=303)
    db.delete(row)
    issue_shared(request, response, db, user, identity, token)
    return response


@router.post("/link")
def link(body: Link, request: Request, response: Response, db: DB) -> dict[str, str]:
    configuration(request)
    origin(request)
    throttle(request, db, body.email)
    row = transaction(request, db)
    payload = json.loads(decrypt(request, row.payload))
    if payload.get("pending_link") is not True:
        fail(400, "identity_link_invalid", "Begin Onesa sign-in before connecting your account")
    identity = live_identity(request, payload["token"])
    if identity.subject != payload["subject"] or body.email.casefold() != payload["email"]:
        fail(403, "identity_link_invalid", "Account details do not match this sign-in")
    user = db.scalar(select(User).where(User.email == body.email.casefold()).with_for_update())
    try:
        from app.auth import DUMMY

        with request.app.state.auth_hash_semaphore:
            hasher.verify(user.password_hash if user else DUMMY, body.current_password)
    except (VerificationError, InvalidHashError):
        fail(
            403,
            "identity_link_invalid",
            "The existing application credentials could not be verified",
        )
    if user is None or user.status != "active":
        fail(
            403,
            "identity_link_invalid",
            "The existing application credentials could not be verified",
        )
    if db.scalar(select(SharedIdentity.id).where(SharedIdentity.user_id == user.id)):
        fail(409, "identity_link_conflict", "This application account is already connected")
    db.add(SharedIdentity(issuer=identity.issuer, subject=identity.subject, user_id=user.id))
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        fail(409, "identity_link_conflict", "This Onesa identity is already connected")
    db.add(IdentityAudit(actor_id=user.id, event="identity.linked", record_id=user.id))
    target = safe_next(payload["next"])
    db.delete(row)
    issue_shared(request, response, db, user, identity, payload["token"])
    return {"next": target}
