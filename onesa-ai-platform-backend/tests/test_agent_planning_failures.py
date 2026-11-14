"""Synthetic streams only; no inference request or database required."""

import asyncio

import pytest

from app.agent_runtime import (
    ModelToolPlanner,
    PlanningError,
    default_registry,
    planning_failure_reason,
)
from app.inference import InferenceError, MockModelClient


class SyntheticPlan(MockModelClient):
    def __init__(self, content):
        self.content = content

    async def stream(self, messages):
        for offset in range(0, len(self.content), 3):
            yield self.content[offset : offset + 3]


@pytest.mark.parametrize(
    "content,reason",
    [
        ("  ", "plan_empty"),
        ("private synthetic text", "plan_invalid_json"),
        ("```json\n[]\n```", "plan_invalid_json"),
        ("{}", "plan_invalid_shape"),
        ("[]", "plan_invalid_shape"),
        ("[{}]", "plan_invalid_schema"),
        ('[{"tool":"text_stats","arguments":{},"unexpected":"secret"}]', "plan_invalid_schema"),
        ("x" * 16001, "plan_size_limit"),
    ],
)
def test_invalid_plan_has_fixed_reason_and_no_content(content, reason):
    planner = ModelToolPlanner(SyntheticPlan(content), default_registry(), {"text_stats"})
    with pytest.raises(PlanningError) as caught:
        asyncio.run(planner.plan("synthetic private goal"))
    assert planning_failure_reason(caught.value) == reason
    assert str(caught.value) == reason


def test_valid_chunked_plan_remains_strict_and_authorization_stays_separate():
    planner = ModelToolPlanner(
        SyntheticPlan('[{"tool":"arithmetic","arguments":{"operation":"add","values":[17,25]}}]'),
        default_registry(),
        {"text_stats"},
    )
    calls = asyncio.run(planner.plan("synthetic goal"))
    with pytest.raises(PermissionError):
        asyncio.run(default_registry().execute(calls[0], {"text_stats"}))


@pytest.mark.parametrize(
    "error,reason",
    [
        (TimeoutError("private timeout details"), "planning_timeout"),
        (InferenceError(reason="invalid_stream_delta"), "invalid_stream_delta"),
        (InferenceError("inference_timeout"), "planning_timeout"),
        (InferenceError(), "inference_unavailable"),
        (ValueError("private provider text"), "planning_internal_error"),
        (PlanningError("untrusted arbitrary category"), "planning_internal_error"),
    ],
)
def test_failure_categories_do_not_copy_exception_messages(error, reason):
    assert planning_failure_reason(error) == reason
