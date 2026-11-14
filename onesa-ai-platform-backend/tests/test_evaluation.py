import asyncio
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import Settings
from evaluation.local import check_response, measure


def test_checks_reject_bad_json_tool_plans_and_false_claims() -> None:
    assert check_response({"check": "json", "expected": {"city": "Berlin"}}, '{"city":"Berlin"}')
    assert not check_response({"check": "json", "expected": {"city": "Berlin"}}, "```json {} ```")
    assert not check_response({"check": "tool"}, '[{"tool":"execute_shell"}]')
    assert not check_response({"check": "not_contains", "terms": ["CANARY"]}, "The canary is here")
    with pytest.raises(ValueError):
        check_response({"check": "unknown"}, "text")


def test_report_keeps_missing_usage_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    import evaluation.local as runner
    from app.inference import OllamaModelClient

    client = OllamaModelClient(
        Settings(model_backend="ollama", model_base_url="https://model.example.invalid/v1"),
        httpx.MockTransport(
            lambda _: httpx.Response(
                200, text='data: {"choices":[{"delta":{"content":"Hello"}}]}\n\ndata: [DONE]\n\n'
            )
        ),
    )
    monkeypatch.setattr(runner, "build_model_client", lambda _: client)
    result = asyncio.run(
        measure(Settings(model_backend="ollama"), [{"role": "user", "content": "Hi"}])
    )
    assert result["success"] and result["response"] == "Hello"
    assert result["output_tokens"] is None and result["output_tokens_per_second"] is None
    assert (
        result["first_token_seconds"] >= 0
        and result["total_seconds"] >= result["first_token_seconds"]
    )
