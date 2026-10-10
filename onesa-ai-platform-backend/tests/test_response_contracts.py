"""Public contracts reject malformed persisted results instead of publishing them."""

from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.models import AgentRun, User
from tests.conftest import signup


def test_invalid_stored_agent_result_does_not_escape_public_contract(
    api: TestClient, pg: Engine
) -> None:
    signup(api)
    with Session(pg) as db:
        user = db.query(User).one()
        run = AgentRun(
            user_id=user.id,
            goal="Synthetic result",
            status="completed",
            steps=[
                {
                    "tool": "text_stats",
                    "status": "completed",
                    "result": {},
                    "private_debug": "synthetic-confidential-marker",
                }
            ],
        )
        db.add(run)
        db.commit()
        identifier = str(run.id)
    with TestClient(api.app, raise_server_exceptions=False) as client:
        response = client.get(
            f"/api/v1/agents/runs/{identifier}",
            headers={"Cookie": f"onesa_session={api.cookies['onesa_session']}"},
        )
    assert response.status_code == 503
    assert "synthetic-confidential-marker" not in response.text
