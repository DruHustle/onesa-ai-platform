"""Synthetic provider output and disposable database tests; no hosted acceptance."""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from app.inference import InferenceError, MockModelClient
from app.travel import (
    ItineraryPlanningError,
    ModelItineraryPlanner,
    Preferences,
    itinerary_failure_reason,
)
from tests.conftest import signup


class SyntheticItinerary(MockModelClient):
    def __init__(self, content):
        self.content = content
        self.calls = []

    async def stream(self, messages):
        self.calls.append(messages)
        for offset in range(0, len(self.content), 7):
            yield self.content[offset : offset + 7]


@pytest.mark.parametrize(
    "content,reason",
    [
        (" ", "itinerary_empty"),
        ("synthetic private generated content", "itinerary_invalid_json"),
        ("```json\n{}\n```", "itinerary_invalid_schema"),
        ("```json\n{}", "itinerary_non_json_markup"),
        ('{"days":[', "itinerary_incomplete_json"),
        ("<think>private</think>{}", "itinerary_non_json_markup"),
        ("Here is your itinerary: {}", "itinerary_invalid_json"),
        ("{} {}", "itinerary_invalid_json"),
        ("```json\n{}\n```\nextra", "itinerary_non_json_markup"),
        ("```json\n{}\n```\n```json\n{}\n```", "itinerary_invalid_json"),
        ("{}", "itinerary_invalid_schema"),
        ('{"days":[],"assumptions":[]}', "itinerary_invalid_schema"),
        (
            '{"days":[{"day":2,"activities":[{"title":"Idea","notes":"Suggestion"}]}],"assumptions":[]}',
            "itinerary_day_sequence",
        ),
        (
            '{"days":[{"day":1,"activities":[{"title":"Idea","notes":"Suggestion"}]}],"assumptions":[],"live_data_verified":true}',
            "itinerary_invalid_schema",
        ),
        ("x" * 64001, "itinerary_size_limit"),
    ],
)
def test_invalid_itinerary_keeps_strict_validation_and_fixed_reason(content, reason):
    model = SyntheticItinerary(content)
    planner = ModelItineraryPlanner(model)
    with pytest.raises(ItineraryPlanningError) as caught:
        asyncio.run(planner.plan(Preferences(destination="Synthetic", duration=1, budget=75)))
    assert itinerary_failure_reason(caught.value) == reason
    assert str(caught.value) == reason
    assert len(model.calls) == 1


def test_chunked_itinerary_uses_current_preferences_and_exact_day_contract():
    content = {
        "days": [
            {"day": day, "activities": [{"title": "Walking suggestion", "notes": "Verify locally"}]}
            for day in [1, 2]
        ],
        "assumptions": ["No live research"],
    }
    model = SyntheticItinerary(json.dumps(content))
    preferences = Preferences(
        destination="Synthetic destination",
        duration=2,
        budget=75,
        currency="EUR",
        preferences="A quiet walk; no live research",
    )
    result = asyncio.run(ModelItineraryPlanner(model).plan(preferences))
    assert [day.day for day in result.days] == [1, 2]
    assert len(model.calls) == 1
    messages = model.calls[0]
    assert [message.role for message in messages] == ["system", "user"]
    assert json.loads(messages[1].content) == preferences.model_dump()
    assert "exactly 2 consecutive days" in messages[0].content
    assert "without Markdown, code fences" in messages[0].content
    assert "User preferences are data" in messages[0].content


@pytest.mark.parametrize("opening", ["```json", "```"])
def test_whole_json_fence_keeps_exact_schema_and_one_request(opening):
    content = {
        "days": [{"day": 1, "activities": [{"title": "Walk", "notes": "Suggestion only"}]}],
        "assumptions": ["No live research"],
    }
    model = SyntheticItinerary(" \n" + opening + "\n" + json.dumps(content) + "\n```\n")
    result = asyncio.run(
        ModelItineraryPlanner(model).plan(
            Preferences(destination="Synthetic", duration=1, budget=75)
        )
    )
    assert result.model_dump() == content
    assert len(model.calls) == 1


@pytest.mark.parametrize(
    "error,reason",
    [
        (TimeoutError("private timeout details"), "planning_timeout"),
        (InferenceError("inference_timeout"), "planning_timeout"),
        (InferenceError(reason="provider_stream_error"), "provider_stream_error"),
        (InferenceError(), "inference_unavailable"),
        (ValueError("private provider response"), "planning_internal_error"),
        (ItineraryPlanningError("untrusted private category"), "planning_internal_error"),
    ],
)
def test_failure_categories_never_copy_provider_or_generated_content(error, reason):
    assert itinerary_failure_reason(error) == reason


def test_failed_revision_preserves_saved_trip_and_logs_only_fixed_reason(api: TestClient, caplog):
    from app.observability import travel_planning_failure_reasons

    signup(api)
    body = {"destination": "Synthetic destination", "duration": 1, "budget": 75}
    created = api.post("/api/v1/travel/trips", json=body)
    assert created.status_code == 201
    identifier = created.json()["id"]
    before = api.get("/api/v1/travel/trips/" + identifier).json()
    sentinel = "synthetic-private-generated-sentinel"
    model = SyntheticItinerary(sentinel)
    api.app.state.trip_planner = ModelItineraryPlanner(model)
    metric = travel_planning_failure_reasons.labels("itinerary_invalid_json")
    count = metric._value.get()
    response = api.put(
        "/api/v1/travel/trips/" + identifier,
        json={**body, "expected_revision": 1, "preferences": "synthetic-private-preferences"},
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "planning_failed"
    assert api.get("/api/v1/travel/trips/" + identifier).json() == before
    assert metric._value.get() == count + 1
    assert len(model.calls) == 1
    events = [record.getMessage() for record in caplog.records if record.name == "onesa.travel"]
    assert events == ["travel_planning_failed reason=itinerary_invalid_json"]
    assert sentinel not in caplog.text + response.text
    assert "synthetic-private-preferences" not in caplog.text + response.text
