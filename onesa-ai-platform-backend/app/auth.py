"""Opaque session cookies, CSRF and database-backed authentication throttling."""

import hashlib
import secrets
from datetime import timedelta
from typing import Annotated

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import APIRouter, Depends, Request, Response
from fastapi.security import APIKeyCookie
from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import database
from app.errors import fail
from app.models import AccessGrant, AuthSession, RateBucket, User, now
from app.schemas import (
    Credentials,
    PasswordChange,
    PasswordProof,
    ProfileUpdate,
    Register,
    SafeUser,
    SessionList,
    SessionOut,
)

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])
DB = Annotated[Session, Depends(database)]
hasher = PasswordHasher()
DUMMY = hasher.hash("unusable-dummy-password-for-timing")


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def origin(request: Request) -> None:
    if request.headers.get("origin") != request.app.state.settings.public_origin:
        fail(403, "origin_rejected", "Request origin is not allowed")


def throttle(request: Request, db: Session, identity: str) -> None:
    # The socket peer is authoritative; never trust arbitrary forwarding headers.
    peer = request.client.host if request.client else "unknown"
    instant = now()
    bucket = int(instant.timestamp()) // 60
    db.execute(delete(RateBucket).where(RateBucket.expires_at < instant))
    exceeded = False
    for scope, value, limit in [
        ("account", identity.casefold(), request.app.state.settings.auth_rate_limit),
        ("peer", peer, request.app.state.settings.auth_peer_rate_limit),
    ]:
        key = digest(f"auth:{scope}:{value}:{bucket}")
        stmt = insert(RateBucket).values(
            key=key, count=1, expires_at=instant + timedelta(minutes=2)
        )
        count = db.scalar(
            stmt.on_conflict_do_update(
                index_elements=[RateBucket.key], set_={"count": RateBucket.count + 1}
            ).returning(RateBucket.count)
        )
        exceeded = exceeded or (count is not None and count > limit)
    db.commit()
    if exceeded:
        fail(429, "rate_limited", "Too many authentication attempts; retry later")


cookie_scheme = APIKeyCookie(name="onesa_session", auto_error=False)


def authenticated(
    request: Request, db: DB, token: Annotated[str | None, Depends(cookie_scheme)]
) -> tuple[User, AuthSession]:
    token = token or ""
    row = db.scalar(
        select(AuthSession).where(
            AuthSession.token_hash == digest(token),
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > now(),
        )
    )
    user = db.get(User, row.user_id) if row else None
    if row is None or user is None or user.status != "active":
        fail(401, "unauthorized", "Sign in to continue")
    eligible(request, db, user)
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin(request)
        csrf = request.headers.get("X-CSRF-Token", "")
        if not csrf or not secrets.compare_digest(digest(csrf), row.csrf_hash):
            fail(403, "csrf_rejected", "Invalid CSRF token")
    return user, row


Auth = Annotated[tuple[User, AuthSession], Depends(authenticated)]


def eligible(request: Request, db: Session, user: User) -> None:
    settings = request.app.state.settings
    if (
        settings.registration_mode == "invitation"
        and str(user.id) not in settings.access_operator_user_ids
    ):
        grant = db.get(AccessGrant, user.id)
        if grant is None or grant.expires_at <= now():
            fail(403, "invitation_required", "An active invitation is required")


def issue(request: Request, response: Response, db: Session, user: User) -> None:
    eligible(request, db, user)
    config = request.app.state.settings
    old_token = request.cookies.get("onesa_session")
    if old_token:
        db.execute(
            update(AuthSession)
            .where(AuthSession.token_hash == digest(old_token), AuthSession.user_id == user.id)
            .values(revoked_at=now())
        )
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    db.add(
        AuthSession(
            user_id=user.id,
            token_hash=digest(token),
            csrf_hash=digest(csrf),
            expires_at=now() + timedelta(hours=config.session_hours),
        )
    )
    db.commit()
    response.set_cookie(
        "onesa_session",
        token,
        httponly=True,
        secure=config.secure_cookies,
        samesite="lax",
        max_age=config.session_hours * 3600,
        path="/",
    )
    response.set_cookie(
        "onesa_csrf",
        csrf,
        httponly=False,
        secure=config.secure_cookies,
        samesite="lax",
        max_age=config.session_hours * 3600,
        path="/",
    )


@router.post("/register", status_code=201, response_model=SafeUser)
def register(body: Register, request: Request, response: Response, db: DB) -> User:
    origin(request)
    throttle(request, db, str(body.email))
    invitation = None
    if request.app.state.settings.registration_mode == "invitation":
        from app.identity import consume_invitation

        invitation = consume_invitation(request, db, body.invitation_token, str(body.email))
    with request.app.state.auth_hash_semaphore:
        password_hash = hasher.hash(body.password)
    user = User(
        email=str(body.email).casefold(),
        display_name=body.display_name,
        password_hash=password_hash,
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        fail(409, "account_unavailable", "Unable to register this account")
    if invitation is not None:
        db.add(AccessGrant(user_id=user.id, expires_at=invitation.grant_expires_at))
        db.flush()
    issue(request, response, db, user)
    return user


@router.post("/login", response_model=SafeUser)
def login(body: Credentials, request: Request, response: Response, db: DB) -> User:
    origin(request)
    throttle(request, db, str(body.email))
    # Account mutations and login serialize on the user before issuing sessions.
    user = db.scalar(select(User).where(User.email == str(body.email).casefold()).with_for_update())
    try:
        with request.app.state.auth_hash_semaphore:
            hasher.verify(user.password_hash if user else DUMMY, body.password)
    except VerificationError:
        fail(401, "invalid_credentials", "Invalid email or password")
    if user is None or user.status != "active":
        fail(401, "invalid_credentials", "Invalid email or password")
    issue(request, response, db, user)
    return user


@router.get("/me", response_model=SafeUser)
def me(auth: Auth) -> User:
    return auth[0]


@router.post("/refresh", response_model=SafeUser)
def refresh(request: Request, response: Response, db: DB, auth: Auth) -> User:
    lock_account(db, auth)
    # Serialize rotation: a consumed token cannot create another session.
    old = db.scalar(
        select(AuthSession)
        .where(AuthSession.id == auth[1].id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if old is None or old.revoked_at is not None:
        fail(401, "unauthorized", "Session already rotated")
    old.revoked_at = now()
    issue(request, response, db, auth[0])
    return auth[0]


@router.post("/logout", status_code=204)
def logout(response: Response, db: DB, auth: Auth) -> None:
    auth[1].revoked_at = now()
    db.commit()
    response.delete_cookie("onesa_session", path="/")
    response.delete_cookie("onesa_csrf", path="/")


def lock_account(db: Session, auth: tuple[User, AuthSession]) -> User:
    """Recheck identity after locking; a revoked session cannot mutate an account."""
    user = db.scalar(
        select(User)
        .where(User.id == auth[0].id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    session = db.scalar(
        select(AuthSession)
        .where(AuthSession.id == auth[1].id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if (
        user is None
        or user.status != "active"
        or session is None
        or session.revoked_at is not None
        or session.expires_at <= now()
    ):
        fail(401, "unauthorized", "Sign in to continue")
    return user


def prove_password(
    request: Request, db: Session, auth: tuple[User, AuthSession], proof: PasswordProof
) -> User:
    throttle(request, db, auth[0].email)
    user = lock_account(db, auth)
    try:
        with request.app.state.auth_hash_semaphore:
            hasher.verify(user.password_hash, proof.current_password)
    except VerificationError:
        fail(403, "reauthentication_failed", "Current password is incorrect")
    return user


@router.patch("/profile", response_model=SafeUser)
def profile(body: ProfileUpdate, db: DB, auth: Auth) -> User:
    user = lock_account(db, auth)
    user.display_name = body.display_name.strip()
    db.commit()
    return user


@router.get("/sessions", response_model=SessionList)
def sessions(db: DB, auth: Auth) -> SessionList:
    condition = (
        AuthSession.user_id == auth[0].id,
        AuthSession.revoked_at.is_(None),
        AuthSession.expires_at > now(),
    )
    rows = db.scalars(
        select(AuthSession)
        .where(*condition)
        .order_by(AuthSession.created_at.desc(), AuthSession.id)
        .limit(100)
    ).all()
    total = db.scalar(select(func.count()).select_from(AuthSession).where(*condition)) or 0
    return SessionList(
        items=[
            SessionOut(
                id=row.id,
                created_at=row.created_at,
                expires_at=row.expires_at,
                current=row.id == auth[1].id,
            )
            for row in rows
        ],
        total=total,
        limit=100,
    )


@router.post("/sessions/revoke-others", status_code=204)
def revoke_others(body: PasswordProof, request: Request, db: DB, auth: Auth) -> None:
    user = prove_password(request, db, auth, body)
    db.execute(
        update(AuthSession)
        .where(
            AuthSession.user_id == user.id,
            AuthSession.id != auth[1].id,
            AuthSession.revoked_at.is_(None),
        )
        .values(revoked_at=now())
    )
    db.commit()


@router.post("/password", response_model=SafeUser)
def change_password(
    body: PasswordChange, request: Request, response: Response, db: DB, auth: Auth
) -> User:
    user = prove_password(request, db, auth, body)
    if body.new_password == body.current_password:
        fail(422, "password_unchanged", "Choose a different password")
    with request.app.state.auth_hash_semaphore:
        user.password_hash = hasher.hash(body.new_password)
    # Revoke every prior token, including this browser, then rotate its cookies.
    db.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=now())
    )
    issue(request, response, db, user)
    return user
