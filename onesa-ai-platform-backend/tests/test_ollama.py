import asyncio
import json

import httpx
import pytest

from app.config import Settings
from app.inference import (
    GenerationStats,
    InferenceError,
    MockModelClient,
    ModelMessage,
    OllamaModelClient,
    VLLMModelClient,
    build_model_client,
    model_metadata,
    observe_generation,
)


@pytest.mark.parametrize("backend", ["ollama", "vllm"])
def test_shared_mapping_context_and_request_owned_usage(backend: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "test-model"}]})
        body = json.loads(request.content)
        assert [m["role"] for m in body["messages"]] == ["user", "assistant", "user"]
        assert body["messages"][0]["content"] == "Remember blue"
        assert body["max_tokens"] == 32 and body["temperature"] == 0
        assert body["stream_options"]["include_usage"]
        return httpx.Response(
            200,
            text='data: {"choices":[{"delta":{"content":"Blue 🌍"}}]}\n\n'
            'data: {"choices":[],"usage":{"prompt_tokens":15,"completion_tokens":3}}\n\n'
            "data: [DONE]\n\n",
        )

    client_type = OllamaModelClient if backend == "ollama" else VLLMModelClient
    client = client_type(
        Settings(
            model_backend=backend,
            model_name="test-model",
            model_max_output_tokens=32,
            model_temperature=0,
        ),
        httpx.MockTransport(handler),
    )

    async def collect():
        assert await client.healthy()
        stats = GenerationStats()
        with observe_generation(stats):
            text = "".join(
                [
                    part
                    async for part in client.stream(
                        [
                            ModelMessage(role="user", content="Remember blue"),
                            ModelMessage(role="assistant", content="I remember"),
                            ModelMessage(role="user", content="What color?"),
                        ]
                    )
                ]
            )
        return text, stats

    async def check():
        results = await asyncio.gather(collect(), collect())
        for text, stats in results:
            assert text == "Blue 🌍" and stats.input_tokens == 15 and stats.output_tokens == 3
        assert results[0][1] is not results[1][1]

    asyncio.run(check())


def test_backend_selection_and_safe_metadata() -> None:
    assert isinstance(build_model_client(Settings()), MockModelClient)
    assert isinstance(build_model_client(Settings(model_backend="ollama")), OllamaModelClient)
    assert isinstance(build_model_client(Settings(model_backend="vllm")), VLLMModelClient)
    assert (
        model_metadata(Settings(model_backend="ollama", model_name="https://private/secret"))[
            "model_identifier"
        ]
        == "configured-model"
    )
    assert model_metadata(Settings())["model_identifier"] == "deterministic-mock"
    assert model_metadata(Settings())["real_inference"] is False


@pytest.mark.parametrize(
    "failure,code",
    [
        ("missing", "model_not_available"),
        ("timeout", "inference_timeout"),
        ("connection", "inference_unavailable"),
    ],
)
def test_sanitized_transport_errors(failure: str, code: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if failure == "timeout":
            raise httpx.ReadTimeout("private-secret-host", request=request)
        if failure == "connection":
            raise httpx.ConnectError("private-secret-key", request=request)
        return httpx.Response(404, json={"error": "private-secret-model"})

    client = OllamaModelClient(Settings(model_backend="ollama"), httpx.MockTransport(handler))

    async def collect():
        async for _ in client.stream([ModelMessage(role="user", content="Hi")]):
            pass

    with pytest.raises(InferenceError) as error:
        asyncio.run(collect())
    assert error.value.code == code and "private" not in str(error.value)


def test_missing_model_not_ready_and_recovers() -> None:
    available = False

    def handler(request):
        return httpx.Response(200, json={"data": [{"id": "test-model"}] if available else []})

    client = OllamaModelClient(
        Settings(model_backend="ollama", model_name="test-model"), httpx.MockTransport(handler)
    )
    assert not asyncio.run(client.healthy())
    available = True
    assert asyncio.run(client.healthy())


def test_cancel_closes_upstream_stream() -> None:
    class SlowBody(httpx.AsyncByteStream):
        closed = False

        async def __aiter__(self):
            yield b'data: {"choices":[{"delta":{"content":"start"}}]}\n\n'
            await asyncio.sleep(30)

        async def aclose(self):
            self.closed = True

    body = SlowBody()
    client = OllamaModelClient(
        Settings(model_backend="ollama"),
        httpx.MockTransport(lambda _: httpx.Response(200, stream=body)),
    )

    async def check():
        first = asyncio.Event()

        async def consume():
            async for _ in client.stream([ModelMessage(role="user", content="Hi")]):
                first.set()

        task = asyncio.create_task(consume())
        await asyncio.wait_for(first.wait(), timeout=1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert body.closed

    asyncio.run(check())


@pytest.mark.parametrize(
    "payload", ["[]", '{"usage":{"completion_tokens":-1}}', '{"usage":{"completion_tokens":true}}']
)
def test_invalid_accounting_or_payload_rejected(payload: str) -> None:
    client = OllamaModelClient(
        Settings(model_backend="ollama"),
        httpx.MockTransport(
            lambda _: httpx.Response(200, text=f"data: {payload}\n\ndata: [DONE]\n\n")
        ),
    )

    async def collect():
        async for _ in client.stream([ModelMessage(role="user", content="Hi")]):
            pass

    with pytest.raises(ValueError):
        asyncio.run(collect())


def test_empty_optional_metadata_from_compose_is_unknown() -> None:
    assert Settings(model_revision="", model_quantization="").model_revision is None


def test_native_ollama_without_key_omits_empty_authorization() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert "authorization" not in request.headers
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "local-qwen"}]})
        return httpx.Response(
            200,
            text='data: {"choices":[{"delta":{"content":"READY"}}]}\n\ndata: [DONE]\n\n',
        )

    client = OllamaModelClient(
        Settings(model_backend="ollama", model_name="local-qwen", model_api_key=""),
        transport=httpx.MockTransport(handler),
    )

    async def check():
        assert await client.healthy()
        assert (
            "".join(
                [
                    chunk
                    async for chunk in client.stream([ModelMessage(role="user", content="Ready")])
                ]
            )
            == "READY"
        )

    asyncio.run(check())
