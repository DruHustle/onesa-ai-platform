"""Durable identity-mail outbox. Provider acceptance is distinct from delivery."""

import argparse
import hashlib
import secrets
import signal
from datetime import timedelta
from threading import Event
from uuid import uuid4

import httpx
from sqlalchemy import Engine, delete, or_, select, update
from sqlalchemy.orm import Session

from app.config import Settings
from app.database import make_engine
from app.identity import bearer
from app.models import BoundedUpload, IdentityMail, IdentityToken, now


def process_one(engine: Engine, settings: Settings, client: httpx.Client) -> bool:
    if settings.mail_provider == "disabled":
        return False
    lease = uuid4()
    with Session(engine) as db:
        job = db.scalar(
            select(IdentityMail)
            .where(
                IdentityMail.state.in_(["queued", "leased"]),
                IdentityMail.attempts < 5,
                IdentityMail.next_attempt_at <= now(),
                or_(IdentityMail.lease_until.is_(None), IdentityMail.lease_until < now()),
            )
            .order_by(IdentityMail.next_attempt_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if job is None:
            return False
        row = db.get(IdentityToken, job.token_id)
        if (
            row is None
            or row.revoked_at is not None
            or row.consumed_at is not None
            or row.expires_at <= now()
        ):
            job.state = "cancelled"
            db.commit()
            return True
        token = bearer(settings, row)
        if not secrets.compare_digest(hashlib.sha256(token.encode()).hexdigest(), row.token_hash):
            job.state = (
                "cancelled"  # Delivery-key rotation invalidates old links; never rewrite hashes.
            )
            db.commit()
            return True
        job.state, job.lease_id, job.lease_until = "leased", lease, now() + timedelta(seconds=60)
        job.attempts += 1
        job_id, email, purpose = job.token_id, row.email, row.purpose
        db.commit()
    accepted, provider_id = False, None
    try:
        route = "invitation" if purpose == "invitation" else "recovery"
        # Fragment keeps tokens out of access logs/referrers; UI clears it before API calls.
        link = f"{settings.public_origin}/{route}#token={token}"
        response = client.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": "Bearer " + settings.resend_api_key,
                "Idempotency-Key": "onesa-identity-" + str(job_id),
            },
            json={
                "from": settings.mail_from,
                "to": [email],
                "reply_to": settings.mail_reply_to or settings.mail_from,
                "subject": "Onesa AI invitation"
                if purpose == "invitation"
                else "Onesa AI password recovery",
                "text": f"Open this private, expiring link:\n{link}\n"
                "Ignore this message if unexpected.",
            },
            timeout=10,
        )
        value = response.json().get("id") if response.is_success else None
        accepted = isinstance(value, str) and 0 < len(value) <= 200
        provider_id = value if accepted else None
    except Exception:
        pass  # Never log request/exception strings containing credentials or recipient/token data.
    with Session(engine) as db:
        job = db.scalar(
            select(IdentityMail).where(IdentityMail.token_id == job_id).with_for_update()
        )
        if job is not None and job.lease_id == lease:
            job.provider_id = provider_id
            job.state = "accepted" if accepted else "failed" if job.attempts >= 5 else "queued"
            job.lease_until, job.lease_id = None, None
            job.next_attempt_at = now() + timedelta(seconds=min(600, 15 * 2**job.attempts))
            db.commit()
    return True


def run_worker(
    engine: Engine,
    settings: Settings,
    client: httpx.Client,
    stop: Event,
    max_jobs: int | None = None,
) -> int:
    """Stop claiming after termination; finish the current bounded provider request.

    A bounded invocation exits on an empty queue. Durable retries remain queued for
    the next invocation; it never sleeps until a future retry becomes eligible.
    """
    if max_jobs is not None and max_jobs < 1:
        raise ValueError("max_jobs must be positive")
    processed = 0
    while not stop.is_set() and (max_jobs is None or processed < max_jobs):
        maintenance(engine)
        if stop.is_set():
            break
        if process_one(engine, settings, client):
            processed += 1
        elif max_jobs is not None:
            break
        else:
            stop.wait(2)
    return processed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="Process at most one eligible job")
    parser.add_argument(
        "--max-jobs", type=int, help="Bound claims and exit when the queue is empty"
    )
    args = parser.parse_args()
    if args.max_jobs is not None and args.max_jobs < 1:
        parser.error("--max-jobs must be positive")
    if args.once and args.max_jobs is not None:
        parser.error("Choose --once or --max-jobs")
    settings = Settings()
    if not settings.database_url:
        raise RuntimeError("Identity worker requires a configured database")
    stop = Event()
    previous = {}
    for sig in (signal.SIGTERM, signal.SIGINT):
        previous[sig] = signal.signal(sig, lambda _sig, _frame: stop.set())
    engine = None
    try:
        engine = make_engine(settings.database_url)
        with httpx.Client(follow_redirects=False) as client:
            run_worker(engine, settings, client, stop, 1 if args.once else args.max_jobs)
    finally:
        if engine is not None:
            engine.dispose()
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def maintenance(engine: Engine) -> None:
    with Session(engine) as db:
        db.execute(delete(BoundedUpload).where(BoundedUpload.expires_at <= now()))
        expired = select(IdentityToken.id).where(IdentityToken.expires_at <= now())
        db.execute(
            update(IdentityMail)
            .where(IdentityMail.token_id.in_(expired), IdentityMail.state.in_(["queued", "leased"]))
            .values(state="cancelled", lease_until=None, lease_id=None)
        )
        db.commit()


if __name__ == "__main__":
    main()
