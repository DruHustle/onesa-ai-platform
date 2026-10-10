"""Database-backed model concurrency, request and conservative token-reservation ceilings."""

from datetime import timedelta
from uuid import UUID

from fastapi import Request
from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.auth import authenticated, digest
from app.errors import fail
from app.models import ModelLease, RateBucket, now


def applies(request: Request) -> bool:
    path, method = request.url.path, request.method
    return (
        method == "POST"
        and path
        in {
            "/api/v1/chat/completions",
            "/api/v1/agents/runs",
            "/api/v1/travel/trips",
            "/api/v1/documentation/answer",
        }
    ) or (method == "PUT" and path.startswith("/api/v1/travel/trips/"))


def begin(request: Request) -> UUID:
    config = request.app.state.settings
    with Session(request.app.state.engine) as db:
        user, _ = authenticated(request, db, request.cookies.get("onesa_session"))
        db.execute(text("SELECT pg_advisory_xact_lock(757837)"))
        db.execute(delete(ModelLease).where(ModelLease.expires_at <= now()))
        total = db.scalar(select(func.count()).select_from(ModelLease)) or 0
        own = (
            db.scalar(
                select(func.count()).select_from(ModelLease).where(ModelLease.user_id == user.id)
            )
            or 0
        )
        if total >= config.model_global_concurrency or own >= config.model_user_concurrency:
            fail(429, "model_capacity", "Generation capacity is busy; retry later")
        # Reservation uses the configured maximum input+output ceiling, not fabricated actual usage.
        tokens = config.model_context_length + config.model_max_output_tokens
        window = int(now().timestamp()) // 60
        for scope, identity, amount, limit in [
            ("requests", str(user.id), 1, config.model_user_requests_per_minute),
            ("requests", "global", 1, config.model_global_requests_per_minute),
            ("reserved_tokens", str(user.id), tokens, config.model_user_reserved_tokens_per_minute),
            ("reserved_tokens", "global", tokens, config.model_global_reserved_tokens_per_minute),
        ]:
            stmt = insert(RateBucket).values(
                key=digest(f"usage:{scope}:{identity}:{window}"),
                count=amount,
                expires_at=now() + timedelta(minutes=2),
            )
            count = db.scalar(
                stmt.on_conflict_do_update(
                    index_elements=[RateBucket.key], set_={"count": RateBucket.count + amount}
                ).returning(RateBucket.count)
            )
            if count is not None and count > limit:
                fail(429, "model_budget", "Generation budget is exhausted; retry later")
        lease = ModelLease(
            user_id=user.id, expires_at=now() + timedelta(seconds=config.generation_timeout + 90)
        )
        db.add(lease)
        db.commit()
        return lease.id


def end(request: Request, identifier: UUID) -> None:
    # Failed cleanup cannot create extra capacity: the lease remains until its bounded expiry.
    try:
        with Session(request.app.state.engine) as db:
            db.execute(delete(ModelLease).where(ModelLease.id == identifier))
            db.commit()
    except Exception:
        pass


def active(request: Request, identifier: UUID) -> bool:
    try:
        with Session(request.app.state.engine) as db:
            lease = db.get(ModelLease, identifier)
            if lease is None or lease.expires_at <= now():
                return False
            authenticated(request, db, request.cookies.get("onesa_session"))
            return True
    except Exception:
        return False
