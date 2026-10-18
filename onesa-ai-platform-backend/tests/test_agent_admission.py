from datetime import timedelta
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app import capacity
from app.models import AgentRun, AuthSession, ModelLease, now
from tests.conftest import signup


def test_denied_agent_permissions_do_not_enter_admission(api, pg, monkeypatch):
    signup(api)
    calls = []

    def unavailable(request):
        calls.append(request)
        raise RuntimeError("Synthetic unavailable admission")

    monkeypatch.setattr(capacity, "begin", unavailable)
    for body in [
        {"goal": "Denied", "allowed_tools": []},
        {
            "goal": "Denied explicit tool",
            "allowed_tools": ["arithmetic"],
            "steps": [{"tool": "text_stats", "arguments": {"text": "Synthetic"}}],
        },
    ]:
        response = api.post("/api/v1/agents/runs", json=body)
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "tool_not_allowed"
    assert calls == []
    with Session(pg) as db:
        assert db.scalar(select(func.count()).select_from(ModelLease)) == 0
        assert db.scalar(select(func.count()).select_from(AgentRun)) == 0


def test_valid_agent_keeps_shared_admission_and_releases_lease(api, pg):
    user = signup(api)
    api.app.state.settings = api.app.state.settings.model_copy(update={"model_user_concurrency": 1})
    with Session(pg) as db:
        lease = ModelLease(user_id=UUID(user["id"]), expires_at=now() + timedelta(seconds=60))
        db.add(lease)
        db.commit()
        identifier = lease.id
    body = {
        "goal": "Synthetic bounded addition",
        "allowed_tools": ["arithmetic"],
        "steps": [{"tool": "arithmetic", "arguments": {"operation": "add", "values": [2, 3]}}],
    }
    assert api.post("/api/v1/agents/runs", json=body).status_code == 429
    with Session(pg) as db:
        assert db.scalar(select(func.count()).select_from(AgentRun)) == 0
        db.get(ModelLease, identifier).expires_at = now() - timedelta(seconds=1)
        db.commit()
    response = api.post("/api/v1/agents/runs", json=body)
    assert response.status_code == 201
    assert response.json()["steps"][0]["result"]["result"] == 5
    with Session(pg) as db:
        assert db.scalar(select(func.count()).select_from(ModelLease)) == 0


def test_planning_failure_releases_agent_admission(api, pg, monkeypatch):
    from app.agent_runtime import BasicPlanner

    signup(api)

    async def unavailable(self, goal):
        raise ValueError("Synthetic planning failure")

    monkeypatch.setattr(BasicPlanner, "plan", unavailable)
    response = api.post(
        "/api/v1/agents/runs", json={"goal": "Synthetic failure", "allowed_tools": ["arithmetic"]}
    )
    assert response.status_code == 503
    with Session(pg) as db:
        assert db.scalar(select(func.count()).select_from(ModelLease)) == 0
        assert db.scalar(select(func.count()).select_from(AgentRun)) == 0


def test_revoked_session_cannot_receive_agent_result(api, pg, monkeypatch):
    from app.agents import registry

    user = signup(api)
    execute = registry.execute

    async def revoke_during_execution(call, allowed):
        result = await execute(call, allowed)
        with Session(pg) as db:
            db.execute(
                update(AuthSession)
                .where(AuthSession.user_id == UUID(user["id"]))
                .values(revoked_at=now())
            )
            db.commit()
        return result

    monkeypatch.setattr(registry, "execute", revoke_during_execution)
    response = api.post(
        "/api/v1/agents/runs",
        json={
            "goal": "Synthetic revocation boundary",
            "allowed_tools": ["arithmetic"],
            "steps": [{"tool": "arithmetic", "arguments": {"operation": "add", "values": [2, 3]}}],
        },
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "generation_lease_lost"
    assert "steps" not in response.json()
    assert api.get("/api/v1/agents/runs").status_code == 401
    with Session(pg) as db:
        assert db.scalar(select(func.count()).select_from(ModelLease)) == 0
