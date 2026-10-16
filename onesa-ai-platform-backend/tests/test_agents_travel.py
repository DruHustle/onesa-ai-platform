import asyncio

import pytest
from fastapi.testclient import TestClient

from app.agent_runtime import ToolCall, default_registry
from tests.conftest import signup


def test_bounded_registry_permissions_and_validation() -> None:
    registry = default_registry()

    async def check() -> None:
        result = await registry.execute(
            ToolCall(tool="arithmetic", arguments={"operation": "add", "values": [2, 3]}),
            {"arithmetic"},
        )
        assert result == {"result": 5}
        with pytest.raises(PermissionError):
            await registry.execute(
                ToolCall(tool="execute_shell", arguments={"code": "bad"}), {"execute_shell"}
            )
        with pytest.raises(ValueError):
            await registry.execute(
                ToolCall(
                    tool="arithmetic", arguments={"operation": "add", "values": [float("inf"), 1]}
                ),
                {"arithmetic"},
            )

    asyncio.run(check())


def test_agent_execution_history_and_isolation(api: TestClient) -> None:
    signup(api)
    body = {"goal": "Count these words", "allowed_tools": ["text_stats"]}
    result = api.post("/api/v1/agents/runs", json=body)
    assert result.status_code == 201, result.text
    assert result.json()["status"] == "completed"
    identifier = result.json()["id"]
    assert result.json()["steps"][0]["result"]["words"] == 3
    assert api.get(f"/api/v1/agents/runs/{identifier}").status_code == 200
    assert api.post("/api/v1/agents/runs", json={"goal": "No permissions"}).status_code == 403
    signup(api, "other@example.com")
    assert api.get(f"/api/v1/agents/runs/{identifier}").status_code == 404


def test_trip_create_revise_persist_and_isolation(api: TestClient) -> None:
    signup(api)
    body = {
        "destination": "Victoria Falls",
        "duration": 3,
        "budget": 500,
        "currency": "USD",
        "preferences": "Nature",
    }
    result = api.post("/api/v1/travel/trips", json=body)
    assert result.status_code == 201, result.text
    trip = result.json()
    identifier = trip["id"]
    assert len(trip["itinerary"]["days"]) == 3
    assert not trip["live_data_verified"]
    assert all(not p["verified"] for p in trip["itinerary"]["providers"])
    assert api.get(f"/api/v1/travel/trips/{identifier}").json()["destination"] == "Victoria Falls"
    body.update(duration=2, expected_revision=1)
    changed = api.put(f"/api/v1/travel/trips/{identifier}", json=body)
    assert changed.json()["revision"] == 2
    assert api.put(f"/api/v1/travel/trips/{identifier}", json=body).status_code == 409
    signup(api, "other@example.com")
    assert api.get(f"/api/v1/travel/trips/{identifier}").status_code == 404
    assert api.put(f"/api/v1/travel/trips/{identifier}", json=body).status_code == 404


def test_invalid_trip_never_persists(api: TestClient) -> None:
    signup(api)
    assert (
        api.post(
            "/api/v1/travel/trips", json={"destination": "Paris", "duration": 100, "budget": 100}
        ).status_code
        == 422
    )
    assert api.get("/api/v1/travel/trips").json()["items"] == []


def test_registry_timeout_and_cancellation() -> None:
    from app.agent_runtime import TextStats, Tool

    async def slow(arguments):
        await asyncio.sleep(10)
        return {}

    registry = default_registry()
    registry.register("slow", Tool(TextStats, slow))

    async def check() -> None:
        task = asyncio.create_task(
            registry.execute(ToolCall(tool="slow", arguments={"text": "Hi"}), {"slow"})
        )
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        with pytest.raises(TimeoutError):
            await registry.execute(ToolCall(tool="slow", arguments={"text": "Hi"}), {"slow"})

    asyncio.run(check())


def test_model_plan_cannot_authorize_unknown_tool(api: TestClient) -> None:
    from app.inference import MockModelClient

    class Malicious(MockModelClient):
        async def stream(self, messages):
            yield '[{"tool":"execute_shell","arguments":{"command":"unauthorized"}}]'

    signup(api)
    api.app.state.settings.model_backend = "vllm"
    api.app.state.model_client = Malicious()
    result = api.post(
        "/api/v1/agents/runs",
        json={"goal": "Run arbitrary commands", "allowed_tools": ["text_stats"]},
    )
    assert result.status_code == 403
    assert api.get("/api/v1/agents/runs").json()["items"] == []


def test_invalid_model_itinerary_is_not_saved(api: TestClient) -> None:
    from app.inference import MockModelClient
    from app.travel import ModelItineraryPlanner

    class Invalid(MockModelClient):
        async def stream(self, messages):
            yield (
                '{"days":[{"day":2,"activities":[{"title":"Idea",'
                '"notes":"Unverified suggestion"}]}],"assumptions":[]}'
            )

    signup(api)
    api.app.state.trip_planner = ModelItineraryPlanner(Invalid())
    result = api.post(
        "/api/v1/travel/trips", json={"destination": "Harare", "duration": 1, "budget": 100}
    )
    assert result.status_code == 503
    assert api.get("/api/v1/travel/trips").json()["items"] == []


def test_explicit_text_stats_needs_no_model_but_still_requires_permission(api: TestClient) -> None:
    from unittest.mock import Mock

    signup(api)
    api.app.state.settings.model_backend = "vllm"
    model = Mock()
    model.stream.side_effect = AssertionError("Explicit tools must not request inference")
    api.app.state.model_client = model
    body = {
        "goal": "Count these words",
        "steps": [{"tool": "text_stats", "arguments": {"text": "Count these words"}}],
        "allowed_tools": ["text_stats"],
    }
    response = api.post("/api/v1/agents/runs", json=body)
    assert response.status_code == 201
    assert response.json()["steps"][0]["result"] == {"words": 3, "characters": 17}
    body["allowed_tools"] = []
    assert api.post("/api/v1/agents/runs", json=body).status_code == 403
    model.stream.assert_not_called()
    assert len(api.get("/api/v1/agents/runs").json()["items"]) == 1


def test_planning_failure_metric_does_not_expose_generated_text(api: TestClient) -> None:
    from app.inference import MockModelClient
    from app.observability import agent_planning_failure_reasons

    class Invalid(MockModelClient):
        async def stream(self, messages):
            yield "synthetic private generated text"

    signup(api)
    api.app.state.settings.model_backend = "vllm"
    api.app.state.model_client = Invalid()
    metric = agent_planning_failure_reasons.labels("plan_invalid_json")
    before = metric._value.get()
    response = api.post(
        "/api/v1/agents/runs",
        json={
            "goal": "synthetic private goal",
            "allowed_tools": ["text_stats"],
        },
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "planning_failed"
    assert "private" not in response.text
    assert metric._value.get() == before + 1
    assert api.get("/api/v1/agents/runs").json()["items"] == []
