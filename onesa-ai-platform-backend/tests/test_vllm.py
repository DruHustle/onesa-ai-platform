import asyncio
import json

import httpx
import pytest

from app.config import Settings
from app.inference import (
    GenerationStats,
    InferenceError,
    ModelMessage,
    VLLMModelClient,
    observe_generation,
)


@pytest.fixture(autouse=True)
def explicit_transport_endpoint(monkeypatch):
    monkeypatch.setenv("ONESA_MODEL_BASE_URL", "https://model.example.invalid/v1")


def test_unconfigured_endpoint_fails_without_transport_request() -> None:
    def unexpected_request(request):
        pytest.fail("Unconfigured inference must not issue a network request")

    client = VLLMModelClient(
        Settings(model_backend="vllm", model_base_url=""),
        httpx.MockTransport(unexpected_request),
    )

    async def check():
        with pytest.raises(InferenceError, match="Inference temporarily unavailable"):
            await client.healthy()
        with pytest.raises(InferenceError, match="Inference temporarily unavailable"):
            async for _ in client.stream([ModelMessage(role="user", content="Hi")]):
                pass

    asyncio.run(check())


def test_vllm_health_and_stream_contract() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer test-key"
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "local-model"}]})
        return httpx.Response(
            200, text='data: {"choices":[{"delta":{"content":"Mhoro"}}]}\n\ndata: [DONE]\n\n'
        )

    client = VLLMModelClient(
        Settings(model_backend="vllm", model_name="local-model", model_api_key="test-key"),
        httpx.MockTransport(handler),
    )

    async def check() -> None:
        assert await client.healthy()
        assert (
            "".join([s async for s in client.stream([ModelMessage(role="user", content="Hi")])])
            == "Mhoro"
        )

    asyncio.run(check())


@pytest.mark.parametrize(
    "response", ["data: not-json\n\n", 'data: {"choices":[]}\n\n', 'data: {"error":"no"}\n\n']
)
def test_vllm_rejects_malformed_or_truncated_stream(response: str) -> None:
    client = VLLMModelClient(
        Settings(model_backend="vllm"),
        httpx.MockTransport(lambda r: httpx.Response(200, text=response)),
    )

    async def collect() -> None:
        async for _ in client.stream([ModelMessage(role="user", content="Hi")]):
            pass

    with pytest.raises(ValueError):
        asyncio.run(collect())


@pytest.mark.parametrize(
    "response,reason,numeric_code",
    [
        ("data: not-json\n\n", "invalid_stream_json", None),
        ('data: {"choices":[]}\n\n', "stream_terminated_early", None),
        (
            'data: {"error":{"code":3040,"message":"PRIVATE-provider-diagnostic"}}\n\n',
            "provider_stream_error",
            3040,
        ),
        (
            'data: {"error":{"code":"PRIVATE-provider-diagnostic"}}\n\n',
            "provider_stream_error",
            None,
        ),
        ('data: {"choices":[{"delta":null}]}\n\n', "invalid_stream_shape", None),
        ('data: {"choices":[{"delta":{"content":42}}]}\n\n', "invalid_stream_delta", None),
    ],
)
def test_stream_failure_diagnostics_are_bounded_without_retry(response, reason, numeric_code):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, text=response)

    client = VLLMModelClient(Settings(model_backend="vllm"), httpx.MockTransport(handler))

    async def collect():
        async for _ in client.stream([ModelMessage(role="user", content="Synthetic input")]):
            pass

    with pytest.raises(InferenceError) as caught:
        asyncio.run(collect())
    assert caught.value.code == "generation_failed"
    assert caught.value.reason == reason
    assert caught.value.provider_error_code == numeric_code
    assert "PRIVATE" not in str(caught.value)
    assert len(requests) == 1


@pytest.mark.parametrize("code", [True, -1, 1000000, "PRIVATE", {"private": "details"}])
def test_error_metadata_rejects_untrusted_provider_values(code):
    error = InferenceError(reason="PRIVATE-provider-message", provider_error_code=code)
    assert error.reason is None and error.provider_error_code is None


@pytest.mark.parametrize("reason", [None, {"private": "details"}, ["private"], True])
def test_error_reason_rejects_nonstring_values(reason):
    assert InferenceError(reason=reason).reason is None


@pytest.mark.parametrize(
    "first_reason,later_choice",
    [
        pytest.param("length", {"delta": {}, "finish_reason": "stop"}, id="contradictory-finish"),
        pytest.param(
            "stop",
            {"delta": {"content": "UNEXPECTED_AFTER_FINISH"}},
            id="content-after-finish",
        ),
    ],
)
def test_provider_cannot_reopen_or_replace_a_terminal_finish(first_reason, later_choice):
    content = '[{"tool":"text_stats","arguments":{"text":"synthetic"}}]'
    frames = [
        {"choices": [{"delta": {"content": content}, "finish_reason": first_reason}]},
        {"choices": [later_choice]},
    ]
    response = "".join("data: " + json.dumps(frame) + "\n\n" for frame in frames)
    response += "data: [DONE]\n\n"
    requests = []

    def provider(request):
        requests.append(request)
        return httpx.Response(200, text=response)

    client = VLLMModelClient(Settings(model_backend="vllm"), httpx.MockTransport(provider))
    stats = GenerationStats()
    observed = []

    async def collect():
        with observe_generation(stats):
            messages = [ModelMessage(role="user", content="Synthetic input")]
            async for chunk in client.stream(messages):
                observed.append(chunk)

    with pytest.raises(InferenceError):
        asyncio.run(collect())
    assert stats.finish_reason == first_reason
    assert observed == [content]
    assert len(requests) == 1


def test_usage_only_frame_after_terminal_finish_remains_valid():
    frames = [
        {"choices": [{"delta": {"content": "Synthetic answer"}, "finish_reason": "stop"}]},
        {"choices": [], "usage": {"prompt_tokens": 11, "completion_tokens": 7}},
    ]
    response = "".join("data: " + json.dumps(frame) + "\n\n" for frame in frames)
    response += "data: [DONE]\n\n"
    client = VLLMModelClient(
        Settings(model_backend="vllm"),
        httpx.MockTransport(lambda request: httpx.Response(200, text=response)),
    )
    stats = GenerationStats()

    async def collect():
        with observe_generation(stats):
            return "".join(
                [chunk async for chunk in client.stream([ModelMessage(role="user", content="Hi")])]
            )

    assert asyncio.run(collect()) == "Synthetic answer"
    assert stats.finish_reason == "stop"
    assert stats.input_tokens == 11 and stats.output_tokens == 7
