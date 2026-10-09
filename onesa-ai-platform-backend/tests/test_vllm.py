import asyncio

import httpx
import pytest

from app.config import Settings
from app.inference import ModelMessage, VLLMModelClient


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
