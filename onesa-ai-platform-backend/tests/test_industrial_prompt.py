"""Offline prompt/response boundary; no database or actual model request."""

import asyncio
import json
from types import SimpleNamespace

import pytest

from app import industrial
from app.config import Settings
from app.industrial_evidence import Window, calculate, fixture
from tests.test_industrial import WINDOW, explanation


class ControlledResponse:
    def __init__(self, value):
        self.value = value
        self.messages = []
        self.closed = False

    async def stream(self, messages):
        self.messages.append(messages)
        try:
            yield json.dumps(self.value)
        finally:
            self.closed = True


def context(monkeypatch, value):
    evidence = fixture("demo-press-01", "reference")
    references = [ref.model_dump(mode="json") for ref in evidence.references]
    monkeypatch.setattr(industrial, "selected_references", lambda *args: references)
    provider = ControlledResponse(value)
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                settings=Settings(
                    _env_file=None,
                    environment="development",
                    model_backend="vllm",
                    model_name="synthetic-offline",
                    model_base_url="http://127.0.0.1:9",
                ),
                model_client=provider,
            )
        )
    )
    payload = {
        "evidence": evidence.model_dump(mode="json"),
        "selection": WINDOW,
        "facts": calculate(evidence, Window.model_validate(WINDOW)),
    }
    return request, provider, payload


def test_qualitative_prose_keeps_exact_numeric_source_identity_and_immutable_facts(monkeypatch):
    expected = explanation()
    request, provider, payload = context(monkeypatch, expected)
    before = json.dumps(payload, sort_keys=True)
    result, _ = asyncio.run(industrial.explain(request, payload))
    assert result == expected
    assert result["hypotheses"][0]["citations"][0] == {
        "document_id": "demo-press-01-reference",
        "version": "1",
        "anchor": "pressure-review",
    }
    assert json.dumps(payload, sort_keys=True) == before
    assert len(provider.messages) == 1 and provider.closed
    sent = json.loads(provider.messages[0][1].content)
    assert sent["facts"] == payload["facts"]
    assert sent["references"][0]["id"] == "demo-press-01-reference"
    assert sent["references"][0]["version"] == "1"


@pytest.mark.parametrize(
    "field, text",
    [
        ("statement", "There were 3 stops."),
        ("human_review", "Compare pressure-1 with the stop timestamps."),
        ("statement", "The stop started at 09:12."),
        ("human_review", "Check 10% of samples."),
    ],
)
def test_prompt_clarity_does_not_accept_numeric_narratives_or_retry(monkeypatch, field, text):
    response = explanation()
    response["hypotheses"][0][field] = text
    request, provider, payload = context(monkeypatch, response)
    before = json.dumps(payload, sort_keys=True)
    with pytest.raises(industrial.GenerationFailure) as failure:
        asyncio.run(industrial.explain(request, payload))
    assert failure.value.code == "model_output_narrative_numbers"
    assert len(provider.messages) == 1 and provider.closed
    assert json.dumps(payload, sort_keys=True) == before
