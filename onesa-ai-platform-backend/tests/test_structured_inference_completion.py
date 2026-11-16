"""Structured plans must not accept a provider's incomplete text as a success."""

import asyncio
import json

import httpx
import pytest

from app.agent_runtime import ModelToolPlanner, PlanningError, default_registry
from app.config import Settings
from app.inference import MockModelClient, VLLMModelClient
from app.travel import ItineraryPlanningError, ModelItineraryPlanner, Preferences


def plan_fixture(kind, client):
    if kind == "agent":
        return (
            ModelToolPlanner(client, default_registry(), {"text_stats"}),
            "Count the supplied words",
            '[{"tool":"text_stats","arguments":{"text":"synthetic text"}}]',
            PlanningError,
        )
    return (
        ModelItineraryPlanner(client),
        Preferences(destination="Synthetic", duration=1, budget=75),
        json.dumps(
            {
                "days": [{"day": 1, "activities": [{"title": "Walk", "notes": "Suggestion"}]}],
                "assumptions": ["No live research"],
            }
        ),
        ItineraryPlanningError,
    )


@pytest.mark.parametrize("kind", ["agent", "travel"])
@pytest.mark.parametrize("reason", ["length", "content_filter", "tool_calls", "function_call"])
def test_valid_json_with_incomplete_provider_finish_is_rejected(kind, reason):
    _, _, content, expected_error = plan_fixture(kind, None)
    calls = []

    def provider(request):
        calls.append(request)
        return httpx.Response(
            200,
            text="data: "
            + json.dumps({"choices": [{"delta": {"content": content}, "finish_reason": reason}]})
            + "\n\ndata: [DONE]\n\n",
        )

    client = VLLMModelClient(
        Settings(model_backend="vllm", model_base_url="https://model.example.test/v1"),
        httpx.MockTransport(provider),
    )
    planner, request, _, _ = plan_fixture(kind, client)
    with pytest.raises(expected_error, match="incomplete_response"):
        asyncio.run(planner.plan(request))
    assert len(calls) == 1


@pytest.mark.parametrize("kind", ["agent", "travel"])
def test_explicitly_completed_provider_plan_is_accepted(kind):
    _, _, content, _ = plan_fixture(kind, None)
    client = VLLMModelClient(
        Settings(model_backend="vllm", model_base_url="https://model.example.test/v1"),
        httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                text="data: "
                + json.dumps(
                    {"choices": [{"delta": {"content": content}, "finish_reason": "stop"}]}
                )
                + "\n\ndata: [DONE]\n\n",
            )
        ),
    )
    planner, request, _, _ = plan_fixture(kind, client)
    assert asyncio.run(planner.plan(request))


@pytest.mark.parametrize("kind,limit", [("agent", 16000), ("travel", 64000)])
def test_rejected_oversize_stream_is_closed_before_the_planner_returns(kind, limit):
    closed = []

    class Oversize(MockModelClient):
        async def stream(self, messages):
            try:
                yield "x" * (limit + 1)
                pytest.fail("Planner must not consume more rejected output")
            finally:
                closed.append(True)

    planner, request, _, expected_error = plan_fixture(kind, Oversize())

    async def check():
        with pytest.raises(expected_error, match="size_limit"):
            await planner.plan(request)
        # Check while the event loop is still running: shutdown must not be
        # responsible for eventually releasing the upstream connection.
        assert closed == [True]

    asyncio.run(check())
