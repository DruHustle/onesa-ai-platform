"""Shared Onesa sign-in adapter for native AI ownership and host-only sessions."""

import json
import re
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode, urlsplit
from uuid import UUID

from argon2.exceptions import InvalidHashError, VerificationError
from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import Field
from sqlalchemy import delete, select, update
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
    pkce_challenge,
    revoke_session,
    validate_session,
)
from app.schemas import PasswordProof, Strict

router = APIRouter(prefix="/api/v1/auth/onesa", tags=["shared Onesa identity"])
FLOW_COOKIE = "onesa_identity_flow"


class Start(Strict):
    next: str = Field(default="/", max_length=1000)
    reauthenticate: bool = False
    mobile: bool = False
    code_challenge: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{43}$")


class MobileExchange(Strict):
    state: str = Field(pattern=r"^native_[A-Za-z0-9_-]{43}$")
    code: str = Field(min_length=1, max_length=4096)
    code_verifier: str = Field(min_length=43, max_length=128, pattern=r"^[A-Za-z0-9._~-]+$")


class Authorization(Strict):
    authorize_url: str


class Method(Strict):
    enabled: bool
    account_url: str | None = None


class Link(PasswordProof):
    email: str = Field(min_length=3, max_length=254)


def configuration(request: Request, *, native: bool = False) -> IdentityConfig:
    config = request.app.state.settings
    if not config.identity_enabled:
        fail(404, "identity_disabled", "Shared Onesa sign-in is not enabled")
    if native and not config.identity_mobile_enabled:
        fail(404, "native_identity_disabled", "Native Onesa sign-in is not configured")
    return IdentityConfig(
        config.identity_issuer,
        config.identity_client_id,
        config.identity_client_secret,
        config.identity_callback_url,
        "ai",
        config.environment in {"development", "test"},
        config.identity_audience,
        config.identity_public_jwks,
        config.identity_mapping_issuer,
        config.identity_account_url,
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
    session_id = session.id
    try:
        return _authenticate_shared(request, db, user, session)
    except HTTPException as error:
        if error.status_code in {401, 403}:
            # Explicitly rejected authority must never revive when access is
            # later restored. Discard pending work before committing only the
            # local revocation; generation checks also use this boundary.
            db.rollback()
            db.execute(
                update(AuthSession)
                .where(AuthSession.id == session_id, AuthSession.revoked_at.is_(None))
                .values(revoked_at=now())
            )
            db.execute(delete(IdentitySession).where(IdentitySession.session_id == session_id))
            db.commit()
            request.state.onesa_identity = None
            request.state.onesa_user_id = None
        # Temporary issuer failures remain retryable on the same valid session.
        raise


def _authenticate_shared(
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
            SharedIdentity.issuer == (configuration(request).mapping_issuer or identity.issuer),
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
    ai_role = identity.product_roles.get("ai") if identity else None
    return bool(
        identity
        and (identity.global_admin or ai_role in {"admin", "administrator"})
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
        if not request.app.state.settings.local_credentials_allowed:
            fail(503, "identity_unavailable", "Onesa sign-in is temporarily unavailable")
        return Method(enabled=False)
    config = configuration(request)
    if config.audience:
        return Method(enabled=True, account_url=config.account_url)
    # Legacy account URL remains available while migration is disabled.
    return Method(
        enabled=True, account_url=config.issuer.removesuffix("/api/v1/identity") + "/account"
    )


@router.post("/start", response_model=Authorization)
def start(body: Start, request: Request, response: Response, db: DB) -> Authorization:
    config = configuration(request, native=body.mobile)
    origin(request)
    throttle(request, db, "shared-sign-in")
    if body.mobile and (body.reauthenticate or body.code_challenge is None):
        fail(422, "invalid_flow", "Native sign-in requires a fresh PKCE challenge")
    if not body.mobile and body.code_challenge is not None:
        fail(422, "invalid_flow", "PKCE challenge is only valid for native sign-in")
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
    if body.mobile:
        state = "native_" + state
    browser = secrets.token_urlsafe(32)
    browser_hash = digest(browser)
    if body.mobile:
        challenge = body.code_challenge
        if challenge is None:
            fail(422, "invalid_flow", "Native sign-in requires a fresh PKCE challenge")
        browser_hash = digest("native:" + challenge)
    db.execute(delete(IdentityTransaction).where(IdentityTransaction.expires_at <= now()))
    db.add(
        IdentityTransaction(
            state_hash=digest(state),
            browser_hash=browser_hash,
            payload=encrypt(
                request,
                json.dumps(
                    {
                        "nonce": nonce,
                        "verifier": None if body.mobile else verifier,
                        "code_challenge": body.code_challenge,
                        "native": body.mobile,
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
    if not body.mobile:
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
            config,
            state,
            nonce,
            None if body.mobile else verifier,
            reauthenticate=body.reauthenticate,
            code_challenge=body.code_challenge,
        )
    )


def transaction(request: Request, db: Session, state: str | None = None) -> IdentityTransaction:
    pieces = request.cookies.get(FLOW_COOKIE, "").split(".")
    if (
        len(pieces) != 2
        or not re.fullmatch(r"(?:native_)?[A-Za-z0-9_-]{43}", pieces[0])
        or not re.fullmatch(r"[A-Za-z0-9_-]{43}", pieces[1])
    ):
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
) -> str:
    from app.auth import issue

    if user.status != "active":
        fail(403, "account_disabled", "This application account is disabled")
    request.state.onesa_identity = identity
    request.state.onesa_user_id = str(user.id)
    csrf = issue(request, response, db, user, shared=(identity, token))
    response.delete_cookie(FLOW_COOKIE, path="/api/v1/auth/onesa")
    return csrf


@router.get("/callback", include_in_schema=False)
def callback(
    request: Request, db: DB, state: str = "", code: str = "", error: str = ""
) -> Response:
    native = re.fullmatch(r"native_[A-Za-z0-9_-]{43}", state) is not None
    config = configuration(request, native=native)
    if native:
        pairs = request.query_params
        row = db.get(IdentityTransaction, digest(state))
        if (
            not row
            or row.consumed_at
            or row.expires_at <= now()
            or any(len(pairs.getlist(key)) != 1 for key in pairs)
            or pairs.get("iss", config.issuer) != config.issuer
            or set(pairs) - {"state", "code", "error", "error_description", "iss"}
        ):
            fail(400, "identity_callback_invalid", "Start sign-in again")
        params = {"state": state}
        if error or not code or len(code) > 4096:
            params["error"] = "cancelled"
        else:
            params["code"] = code
        return RedirectResponse("onesaai://account/callback?" + urlencode(params), status_code=303)
    return finish_sign_in(request, db, state, code, error)


@router.post("/mobile/exchange", include_in_schema=False)
def mobile_exchange(body: MobileExchange, request: Request, db: DB) -> Response:
    origin(request)
    response = finish_sign_in(
        request, db, body.state, body.code, "", native_verifier=body.code_verifier
    )
    if response.status_code != 200:
        fail(403, "mobile_sign_in_unavailable", "Sign-in requires account support or a new attempt")
    return response


def finish_sign_in(
    request: Request,
    db: Session,
    state: str,
    code: str,
    error: str,
    *,
    native_verifier: str | None = None,
) -> Response:
    row: IdentityTransaction | None
    if native_verifier is None:
        row = transaction(request, db, state)
    else:
        configuration(request, native=True)
        row = db.scalar(
            select(IdentityTransaction)
            .where(IdentityTransaction.state_hash == digest(state))
            .with_for_update()
        )
        if row is None or row.expires_at <= now() or row.consumed_at is not None:
            fail(400, "identity_callback_invalid", "Sign-in has expired. Please start again")
        native_payload = json.loads(decrypt(request, row.payload))
        challenge = native_payload.get("code_challenge")
        if (
            native_payload.get("native") is not True
            or not isinstance(challenge, str)
            or not secrets.compare_digest(row.browser_hash, digest("native:" + challenge))
            or not secrets.compare_digest(pkce_challenge(native_verifier), challenge)
        ):
            fail(400, "identity_callback_invalid", "Sign-in has expired. Please start again")
    if row.consumed_at is not None:
        fail(400, "identity_callback_invalid", "Sign-in has already been used. Please start again")
    payload = json.loads(decrypt(request, row.payload))
    if payload.get("native") is not state.startswith("native_"):
        fail(400, "identity_callback_invalid", "Sign-in has expired. Please start again")
    row.consumed_at = now()
    db.commit()  # Code exchange is never retried after an ambiguous network result.
    if error or not code:
        response: Response = RedirectResponse("/?identity=cancelled", status_code=303)
        response.delete_cookie(FLOW_COOKIE, path="/api/v1/auth/onesa")
        return response
    try:
        config = configuration(request, native=payload.get("native") is True)
        verifier = native_verifier if payload.get("native") is True else payload["verifier"]
        if not isinstance(verifier, str):
            fail(400, "identity_callback_invalid", "Sign-in has expired. Please start again")
        if config.audience:
            from app.managed_oidc import exchange

            token = exchange(config, code, verifier, payload["nonce"])
        else:
            token = exchange_code(config, code, verifier)
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
            SharedIdentity.issuer == (configuration(request).mapping_issuer or identity.issuer),
            SharedIdentity.subject == identity.subject,
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
                SharedIdentity(
                    issuer=configuration(request).mapping_issuer or identity.issuer,
                    subject=identity.subject,
                    user_id=user.id,
                )
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
    if state.startswith("native_"):
        # The CSRF value travels in a cookie as it does on the web. Returning it
        # here lets the native client retain the header value in its OS keychain.
        response = Response(headers={"cache-control": "no-store"}, media_type="application/json")
        db.delete(row)
        csrf = issue_shared(request, response, db, user, identity, token)
        response.body = json.dumps({"csrf": csrf}).encode()
        response.headers["content-length"] = str(len(response.body))
        return response
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
    db.add(
        SharedIdentity(
            issuer=configuration(request).mapping_issuer or identity.issuer,
            subject=identity.subject,
            user_id=user.id,
        )
    )
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
