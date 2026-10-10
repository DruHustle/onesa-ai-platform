"""Email-bound invitations and one-use recovery; no bearer secrets persisted in SQL."""

import hashlib
import hmac
from datetime import timedelta
from uuid import UUID, uuid4

from fastapi import APIRouter, Request
from pydantic import EmailStr, Field
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.auth import DB, Auth, digest, hasher, origin, prove_password, throttle
from app.config import Settings
from app.errors import fail
from app.models import (
    AccessGrant,
    AuthSession,
    IdentityAudit,
    IdentityMail,
    IdentityToken,
    User,
    now,
)
from app.schemas import PasswordProof, Strict

router = APIRouter(prefix="/api/v1", tags=["identity recovery"])


class Invite(PasswordProof):
    email: EmailStr
    access_days: int = Field(default=30, ge=1, le=90)


class RecoveryRequest(Strict):
    email: EmailStr


class RecoveryComplete(Strict):
    token: str = Field(min_length=40, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


class Accepted(Strict):
    status: str = "queued_if_eligible"


class InvitationReceipt(Strict):
    id: UUID
    status: str


def bearer(settings: Settings, row: IdentityToken) -> str:
    if len(settings.auth_delivery_key) < 48:
        fail(503, "recovery_unavailable", "Account email is not configured")
    return hmac.new(
        settings.auth_delivery_key.encode(),
        f"onesa-identity-v1:{row.purpose}:{row.id}".encode(),
        hashlib.sha256,
    ).hexdigest()


def mail_available(request: Request) -> None:
    config = request.app.state.settings
    if config.mail_provider == "disabled" or len(config.auth_delivery_key) < 48:
        fail(503, "recovery_unavailable", "Account email is unavailable; contact the operator")


def queue(
    request: Request,
    db: Session,
    email: str,
    purpose: str,
    user: User | None = None,
    access_days: int = 30,
) -> IdentityToken:
    config = request.app.state.settings
    row = IdentityToken(
        id=uuid4(),
        email=email.casefold(),
        purpose=purpose,
        user_id=user.id if user else None,
        expires_at=now()
        + (
            timedelta(hours=config.invitation_hours)
            if purpose == "invitation"
            else timedelta(minutes=config.recovery_minutes)
        ),
        grant_expires_at=now() + timedelta(days=access_days) if purpose == "invitation" else None,
    )
    row.token_hash = digest(bearer(config, row))
    db.add(row)
    db.flush()
    db.add(IdentityMail(token_id=row.id))
    return row


def consume_invitation(
    request: Request, db: Session, token: str | None, email: str
) -> IdentityToken:
    row = db.scalar(
        select(IdentityToken)
        .where(
            IdentityToken.token_hash == digest(token or ""), IdentityToken.purpose == "invitation"
        )
        .with_for_update()
    )
    if (
        row is None
        or row.email != email.casefold()
        or row.consumed_at is not None
        or row.revoked_at is not None
        or row.expires_at <= now()
        or row.grant_expires_at is None
        or row.grant_expires_at <= now()
    ):
        fail(403, "invitation_required", "A valid invitation for this email is required")
    row.consumed_at = now()
    db.add(IdentityAudit(event="invitation.redeemed", record_id=row.id))
    return row


def operator(
    request: Request, db: Session, auth: tuple[User, AuthSession], proof: PasswordProof
) -> None:
    if str(auth[0].id) not in request.app.state.settings.access_operator_user_ids:
        fail(403, "operator_required", "Operator permission is required")
    prove_password(request, db, auth, proof)


@router.post("/admin/invitations", status_code=202, response_model=InvitationReceipt)
def invite(body: Invite, request: Request, db: DB, auth: Auth) -> dict[str, object]:
    operator(request, db, auth, body)
    mail_available(request)
    throttle(request, db, str(body.email))
    row = queue(request, db, str(body.email), "invitation", access_days=body.access_days)
    db.add(IdentityAudit(actor_id=auth[0].id, event="invitation.created", record_id=row.id))
    db.commit()
    return {"id": row.id, "status": "queued"}


@router.post("/admin/invitations/{identifier}/revoke", response_model=InvitationReceipt)
def revoke_invite(
    identifier: UUID, body: PasswordProof, request: Request, db: DB, auth: Auth
) -> dict[str, object]:
    operator(request, db, auth, body)
    row = db.scalar(
        select(IdentityToken)
        .where(IdentityToken.id == identifier, IdentityToken.purpose == "invitation")
        .with_for_update()
    )
    if row is None:
        fail(404, "not_found", "Invitation not found")
    row.revoked_at = now()
    db.add(IdentityAudit(actor_id=auth[0].id, event="invitation.revoked", record_id=row.id))
    db.commit()
    return {"id": row.id, "status": "revoked"}


@router.post("/admin/access/{identifier}/revoke", response_model=Accepted)
def revoke_access(
    identifier: UUID, body: PasswordProof, request: Request, db: DB, auth: Auth
) -> Accepted:
    operator(request, db, auth, body)
    if str(identifier) in request.app.state.settings.access_operator_user_ids:
        fail(409, "operator_protected", "Manage operator access through reviewed configuration")
    # Lock account first, matching login/reset, so no new session survives revocation.
    user = db.scalar(select(User).where(User.id == identifier).with_for_update())
    if user is None:
        fail(404, "not_found", "Account not found")
    grant = db.get(AccessGrant, identifier)
    if grant:
        db.delete(grant)
    db.execute(
        update(AuthSession).where(AuthSession.user_id == identifier).values(revoked_at=now())
    )
    db.add(IdentityAudit(actor_id=auth[0].id, event="access.revoked", record_id=identifier))
    db.commit()
    return Accepted(status="revoked")


@router.post("/auth/recovery/request", status_code=202, response_model=Accepted)
def recovery_request(body: RecoveryRequest, request: Request, db: DB) -> Accepted:
    origin(request)
    throttle(request, db, str(body.email))
    mail_available(request)  # Same unavailable result for every account; never false success.
    user = db.scalar(select(User).where(User.email == str(body.email).casefold()).with_for_update())
    if user is not None and user.status == "active":
        pending = db.scalar(
            select(IdentityToken.id).where(
                IdentityToken.user_id == user.id,
                IdentityToken.purpose == "recovery",
                IdentityToken.expires_at > now(),
                IdentityToken.revoked_at.is_(None),
                IdentityToken.consumed_at.is_(None),
            )
        )
        if pending is None:
            row = queue(request, db, user.email, "recovery", user)
            db.add(IdentityAudit(event="recovery.requested", record_id=row.id))
    db.commit()
    return Accepted()


@router.post("/auth/recovery/complete", response_model=Accepted)
def recovery_complete(body: RecoveryComplete, request: Request, db: DB) -> Accepted:
    origin(request)
    throttle(request, db, "recovery-redemption")
    row = db.scalar(
        select(IdentityToken).where(
            IdentityToken.token_hash == digest(body.token), IdentityToken.purpose == "recovery"
        )
    )
    if row is None or row.user_id is None:
        fail(400, "invalid_recovery", "Recovery link is invalid or expired")
    user = db.scalar(select(User).where(User.id == row.user_id).with_for_update())
    row = db.scalar(
        select(IdentityToken)
        .where(IdentityToken.id == row.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if (
        row is None
        or user is None
        or user.status != "active"
        or row.consumed_at is not None
        or row.revoked_at is not None
        or row.expires_at <= now()
    ):
        fail(400, "invalid_recovery", "Recovery link is invalid or expired")
    with request.app.state.auth_hash_semaphore:
        user.password_hash = hasher.hash(body.new_password)
    row.consumed_at = now()
    db.execute(update(AuthSession).where(AuthSession.user_id == user.id).values(revoked_at=now()))
    db.execute(
        update(IdentityToken)
        .where(
            IdentityToken.user_id == user.id,
            IdentityToken.purpose == "recovery",
            IdentityToken.id != row.id,
        )
        .values(revoked_at=now())
    )
    db.add(IdentityAudit(actor_id=user.id, event="recovery.completed", record_id=row.id))
    db.commit()
    return Accepted(status="password_changed_sign_in")
