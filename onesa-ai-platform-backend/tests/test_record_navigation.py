"""Real PostgreSQL pages retain deterministic order and owner scope under updates."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

from app.models import AgentRun, Conversation, Document, Trip
from tests.conftest import signup


@pytest.mark.parametrize(
    "model,route",
    [
        (Conversation, "/conversations"),
        (Document, "/knowledge/documents"),
        (AgentRun, "/agents/runs"),
        (Trip, "/travel/trips"),
    ],
)
def test_cursor_reaches_older_records_with_equal_times_and_concurrent_updates(
    api, pg, model, route
):
    user = signup(api)
    instant = datetime(2026, 1, 1, tzinfo=UTC)
    identifiers = []
    with Session(pg) as db:
        for i in range(121):
            fields = dict(id=uuid4(), user_id=UUID(user["id"]), created_at=instant)
            if model is Conversation:
                fields.update(title=f"Conversation {i}", updated_at=instant)
            elif model is Document:
                fields.update(
                    title=f"Document {i}",
                    media_type="text/plain",
                    text="Owned source",
                    checksum=f"{i:064x}",
                    embedding_version="lexical:test",
                )
            elif model is AgentRun:
                fields.update(goal=f"Run {i}", status="completed", steps=[])
            else:
                fields.update(
                    destination=f"Trip {i}",
                    duration=1,
                    budget=10,
                    currency="EUR",
                    preferences="",
                    itinerary={
                        "days": [
                            {
                                "day": 1,
                                "activities": [
                                    {"title": "Synthetic activity", "notes": "No live provider"}
                                ],
                            }
                        ],
                        "assumptions": [],
                        "providers": [],
                        "backend": "mock",
                    },
                    updated_at=instant,
                )
            row = model(**fields)
            identifiers.append(row.id)
            db.add(row)
        db.commit()
    expected = [str(identifier) for identifier in sorted(identifiers, reverse=True)]
    first = api.get("/api/v1" + route, params={"limit": 50})
    assert first.status_code == 200, first.text
    cursor = first.json()["next_cursor"]
    seen = [row["id"] for row in first.json()["items"]]
    with Session(pg) as db:
        row = db.get(model, identifiers[0])
        if model in {Conversation, Trip}:
            row.updated_at = instant + timedelta(days=3)
        db.commit()
    while cursor:
        response = api.get("/api/v1" + route, params={"limit": 50, "cursor": cursor})
        assert response.status_code == 200, response.text
        rows = response.json()["items"]
        assert len(rows) <= 50
        seen.extend(row["id"] for row in rows)
        cursor = response.json()["next_cursor"]
    assert seen == expected and len(set(seen)) == 121
    assert api.get("/api/v1" + route, params={"cursor": "malformed"}).status_code == 422
    assert api.get("/api/v1" + route, params={"limit": 101}).status_code == 422
    signup(api, "other@example.com")
    assert api.get("/api/v1" + route).json()["items"] == []
    assert (
        api.get("/api/v1" + route, params={"cursor": first.json()["next_cursor"]}).status_code
        == 422
    )
    assert api.get("/api/v1" + route + "/" + expected[-1]).status_code == 404
