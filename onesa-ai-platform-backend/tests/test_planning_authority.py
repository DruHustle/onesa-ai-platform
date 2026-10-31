"""An authority revoked during inference must not commit a generated result."""

from uuid import UUID

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.agent_runtime import BasicPlanner
from app.models import AgentRun, AuthSession, Trip, now
from app.travel import MockItineraryPlanner
from tests.conftest import signup


def revoke(pg, user_id):
    with Session(pg) as db:
        db.execute(
            update(AuthSession).where(AuthSession.user_id == UUID(user_id)).values(revoked_at=now())
        )
        db.commit()


@pytest.mark.parametrize("revision", [False, True])
def test_travel_rechecks_authority_before_saving_generated_plan(api, pg, revision):
    user = signup(api)
    body = {"destination": "Synthetic", "duration": 1, "budget": 75}
    identifier = None
    if revision:
        created = api.post("/api/v1/travel/trips", json=body)
        assert created.status_code == 201
        identifier = created.json()["id"]

    class RevokingPlanner(MockItineraryPlanner):
        async def plan(self, request):
            result = await super().plan(request)
            revoke(pg, user["id"])
            return result

    api.app.state.trip_planner = RevokingPlanner()
    if revision:
        result = api.put(
            "/api/v1/travel/trips/" + identifier,
            json={**body, "expected_revision": 1, "destination": "Changed destination"},
        )
    else:
        result = api.post("/api/v1/travel/trips", json=body)
    with Session(pg) as db:
        if revision:
            trip = db.get(Trip, UUID(identifier))
            assert trip.revision == 1 and trip.destination == "Synthetic"
        else:
            assert db.scalar(select(func.count()).select_from(Trip)) == 0
    assert result.status_code == 401
    assert result.json()["error"]["code"] == "unauthorized"


def test_agent_rechecks_authority_after_planning_before_creating_or_executing_run(
    api, pg, monkeypatch
):
    user = signup(api)
    original = BasicPlanner.plan

    async def revoking_plan(self, goal):
        result = await original(self, goal)
        revoke(pg, user["id"])
        return result

    monkeypatch.setattr(BasicPlanner, "plan", revoking_plan)
    result = api.post(
        "/api/v1/agents/runs",
        json={"goal": "Synthetic local computation", "allowed_tools": ["text_stats"]},
    )
    with Session(pg) as db:
        assert db.scalar(select(func.count()).select_from(AgentRun)) == 0
    assert result.status_code == 401
    assert result.json()["error"]["code"] == "unauthorized"
