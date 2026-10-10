from datetime import timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ModelLease, now
from tests.conftest import signup


def conversation(api):
    response = api.post("/api/v1/conversations", json={})
    assert response.status_code == 201
    return response.json()["id"]


def generate(api, identifier):
    return api.post(
        "/api/v1/chat/completions",
        json={
            "conversation_id": identifier,
            "content": "Synthetic bounded request",
            "stream": False,
        },
    )


def test_shared_model_leases_limit_live_work_and_recover_expiry(api, pg):
    user = signup(api)
    identifier = conversation(api)
    api.app.state.settings = api.app.state.settings.model_copy(update={"model_user_concurrency": 1})
    with Session(pg) as db:
        lease = ModelLease(user_id=UUID(user["id"]), expires_at=now() + timedelta(seconds=60))
        db.add(lease)
        db.commit()
        lease_id = lease.id
    assert generate(api, identifier).status_code == 429
    with Session(pg) as db:
        db.get(ModelLease, lease_id).expires_at = now() - timedelta(seconds=1)
        db.commit()
    assert generate(api, identifier).status_code == 200
    with Session(pg) as db:
        assert db.scalar(select(func.count()).select_from(ModelLease)) == 0


def test_request_and_reservation_budgets_survive_other_app_instances(api, pg):
    from fastapi.testclient import TestClient

    from app.main import create_app

    signup(api)
    identifier = conversation(api)
    config = api.app.state.settings.model_copy(update={"model_user_requests_per_minute": 1})
    api.app.state.settings = config
    assert generate(api, identifier).status_code == 200
    with TestClient(create_app(config)) as other:
        other.headers.update(
            {
                "Origin": config.public_origin,
                "Cookie": f"onesa_session={api.cookies['onesa_session']}",
                "X-CSRF-Token": api.cookies["onesa_csrf"],
            }
        )
        assert generate(other, identifier).status_code == 429


def test_global_capacity_and_token_reservation_deny_without_generation(api, pg):
    user = signup(api)
    identifier = conversation(api)
    api.app.state.settings = api.app.state.settings.model_copy(
        update={"model_global_concurrency": 1}
    )
    with Session(pg) as db:
        db.add(ModelLease(user_id=UUID(user["id"]), expires_at=now() + timedelta(seconds=60)))
        db.commit()
    assert generate(api, identifier).status_code == 429
    with Session(pg) as db:
        db.query(ModelLease).delete()
        db.commit()
    api.app.state.settings = api.app.state.settings.model_copy(
        update={"model_user_reserved_tokens_per_minute": 1024}
    )
    assert generate(api, identifier).status_code == 429


def test_knowledge_quota_preserves_existing_content_and_deletion_releases_budget(api):
    signup(api)
    api.app.state.settings = api.app.state.settings.model_copy(
        update={"knowledge_max_documents": 1}
    )
    first = api.post(
        "/api/v1/knowledge/documents",
        files={"file": ("one.txt", b"Private synthetic document one", "text/plain")},
    )
    assert first.status_code == 201
    second = api.post(
        "/api/v1/knowledge/documents",
        files={"file": ("two.txt", b"Private synthetic document two", "text/plain")},
    )
    assert second.status_code == 429
    assert api.get("/api/v1/knowledge/documents").json()["items"][0]["id"] == first.json()["id"]
    assert api.delete("/api/v1/knowledge/documents/" + first.json()["id"]).status_code == 204
    assert (
        api.post(
            "/api/v1/knowledge/documents",
            files={"file": ("two.txt", b"Private synthetic document two", "text/plain")},
        ).status_code
        == 201
    )


def test_metrics_are_private_bounded_and_show_real_queue_state(api):
    signup(api)
    assert api.get("/metrics").status_code == 403
    api.app.state.settings = api.app.state.settings.model_copy(
        update={"metrics_token": "fixture-metrics-only-" + "x" * 40}
    )
    response = api.get(
        "/metrics", headers={"Authorization": "Bearer " + api.app.state.settings.metrics_token}
    )
    assert response.status_code == 200
    assert "onesa_identity_mail_jobs" in response.text
    assert "user@example.com" not in response.text
    assert api.cookies["onesa_session"] not in response.text
