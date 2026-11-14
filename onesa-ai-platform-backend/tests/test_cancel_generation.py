from datetime import timedelta
from uuid import uuid4

from sqlalchemy.orm import Session

from app.chat import release
from app.models import Conversation, InferenceRun, Message, now

from .conftest import signup


def test_owned_cancellation_is_atomic_idempotent_and_rejects_late_completion(api, pg):
    user = signup(api)
    cid = api.post("/api/v1/conversations", json={}).json()["id"]
    from uuid import UUID

    cid = UUID(cid)
    rid = uuid4()
    with Session(pg) as db:
        row = db.get(Conversation, cid)
        row.active_run_id, row.lease_until = rid, now() + timedelta(minutes=1)
        db.add(
            InferenceRun(id=rid, user_id=UUID(user["id"]), conversation_id=cid, request_id=uuid4())
        )
        db.commit()
    assert (
        api.post(f"/api/v1/conversations/{cid}/cancel", json={"run_id": str(uuid4())}).status_code
        == 204
    )
    with Session(pg) as db:
        assert db.get(Conversation, cid).active_run_id == rid
    for _ in range(2):
        assert (
            api.post(f"/api/v1/conversations/{cid}/cancel", json={"run_id": str(rid)}).status_code
            == 204
        )
    with Session(pg) as db:
        assert db.get(Conversation, cid).active_run_id is None
        assert db.get(InferenceRun, rid).status == "cancelled"
    from types import SimpleNamespace

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(engine=pg)))
    assert release(request, cid, rid, "completed", 1, "Late content") is None
    with Session(pg) as db:
        assert list(db.query(Message).filter_by(conversation_id=cid)) == []


def test_cancel_rejects_cross_user_missing_csrf_and_mass_assignment(api):
    signup(api)
    cid = api.post("/api/v1/conversations", json={}).json()["id"]
    body = {"run_id": str(uuid4())}
    csrf = api.headers.pop("X-CSRF-Token")
    assert api.post(f"/api/v1/conversations/{cid}/cancel", json=body).status_code == 403
    api.headers["X-CSRF-Token"] = csrf
    assert (
        api.post(
            f"/api/v1/conversations/{cid}/cancel", json={**body, "user_id": str(uuid4())}
        ).status_code
        == 422
    )
    signup(api, "second@example.com")
    assert api.post(f"/api/v1/conversations/{cid}/cancel", json=body).status_code == 404
