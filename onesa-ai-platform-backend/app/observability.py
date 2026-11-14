import json
import logging
import secrets

from fastapi import APIRouter, Request
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.responses import Response

from app.errors import fail

logger = logging.getLogger("onesa.requests")
if not logger.handlers:
    logger.addHandler(logging.StreamHandler())
logger.propagate = False
requests = Counter("onesa_http_requests_total", "HTTP requests", ["method", "route", "status"])
latency = Histogram("onesa_http_latency_seconds", "HTTP latency to response headers", ["route"])
router = APIRouter()


def record(request: Request, status: int, duration: float) -> None:
    route = getattr(request.scope.get("route"), "path", "unmatched")
    requests.labels(request.method, route, str(status)).inc()
    if route in {"/api/v1/auth/login", "/api/v1/auth/register"}:
        outcome = "success" if status < 400 else "rate_limited" if status == 429 else "denied"
        authentication_events.labels(outcome).inc()
    latency.labels(route).observe(duration)
    logger.info(
        json.dumps(
            {
                "event": "http_request",
                "request_id": request.state.request_id,
                "method": request.method,
                "route": route,
                "status": status,
                "duration_ms": int(duration * 1000),
            }
        )
    )


@router.get("/metrics", include_in_schema=False)
def metrics(request: Request) -> Response:
    token = request.app.state.settings.metrics_token
    if not token or not secrets.compare_digest(
        request.headers.get("Authorization", ""), "Bearer " + token
    ):
        fail(403, "metrics_denied", "Metrics access denied")
    try:
        with Session(request.app.state.engine) as db:
            for state in ["queued", "leased", "accepted", "failed", "cancelled"]:
                mail_jobs.labels(state).set(
                    db.scalar(
                        text("SELECT count(*) FROM identity_mail WHERE state=:state"),
                        {"state": state},
                    )
                    or 0
                )
            mail_age.set(
                db.scalar(
                    text(
                        "SELECT coalesce(extract(epoch FROM now()-min(t.created_at)),0) "
                        "FROM identity_mail m JOIN identity_tokens t ON t.id=m.token_id "
                        "WHERE m.state IN ('queued','leased')"
                    )
                )
                or 0
            )
            pending_upload_bytes.set(
                db.scalar(
                    text(
                        "SELECT coalesce(sum(received),0) FROM bounded_uploads "
                        "WHERE result IS NULL AND expires_at>now()"
                    )
                )
                or 0
            )
            model_leases.set(
                db.scalar(text("SELECT count(*) FROM model_leases WHERE expires_at>now()")) or 0
            )
            knowledge_bytes.set(
                db.scalar(text("SELECT coalesce(sum(octet_length(text)),0) FROM documents")) or 0
            )
            dependency_available.labels("database").set(1)
    except Exception:
        dependency_available.labels("database").set(0)
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


generation_count = Counter("onesa_generation_total", "Generation outcomes", ["backend", "status"])
generation_latency = Histogram("onesa_generation_seconds", "Total generation duration", ["backend"])
generation_first_token = Histogram(
    "onesa_generation_first_token_seconds", "Time to first text delta", ["backend"]
)


def record_generation(
    backend: str, status: str, duration: float, first_token: float | None
) -> None:
    generation_count.labels(backend, status).inc()
    generation_latency.labels(backend).observe(duration)
    if first_token is not None:
        generation_first_token.labels(backend).observe(first_token)


dependency_available = Gauge(
    "onesa_dependency_available", "Last readiness dependency probe", ["dependency"]
)


authentication_events = Counter(
    "onesa_authentication_events_total", "Authentication outcomes without identities", ["outcome"]
)
agent_outcomes = Counter("onesa_agent_runs_total", "Registered local agent outcomes", ["status"])
agent_planning_failures = Counter(
    "onesa_agent_planning_failures_total", "Rejected or failed agent planning"
)
agent_planning_failure_reasons = Counter(
    "onesa_agent_planning_failure_reasons_total",
    "Agent planning failure categories without request or generated content",
    ["reason"],
)
travel_planning_failure_reasons = Counter(
    "onesa_travel_planning_failure_reasons_total",
    "Travel planning failure categories without preferences or generated content",
    ["reason"],
)
mail_jobs = Gauge(
    "onesa_identity_mail_jobs", "Identity mail states; acceptance is not delivery", ["state"]
)
mail_age = Gauge("onesa_identity_mail_queue_age_seconds", "Age of oldest pending identity message")
pending_upload_bytes = Gauge(
    "onesa_pending_upload_bytes", "Logical received bytes in unexpired staged uploads"
)
model_leases = Gauge("onesa_active_model_leases", "Shared admitted model operations")
knowledge_bytes = Gauge("onesa_knowledge_text_bytes", "Logical stored UTF-8 document bytes")
