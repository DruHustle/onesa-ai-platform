"""Synthetic protocol tests; none constitutes hosted Cloudflare acceptance."""

import asyncio
import json
import math
import secrets

import httpx
import pytest
from pydantic import ValidationError

from app.cloudflare import embeddings
from app.config import Settings
from app.inference import CloudflareModelClient, InferenceError, ModelMessage, build_model_client
from app.knowledge import version


def settings(**changes):
    values = dict(
        model_backend="cloudflare",
        model_name="@cf/qwen/qwen3-30b-a3b-fp8",
        model_base_url="https://api.cloudflare.com/client/v4/accounts/" + "a" * 32 + "/ai/v1",
        model_api_key=secrets.token_hex(24),
        embedding_backend="cloudflare",
        embedding_name="@cf/qwen/qwen3-embedding-0.6b",
        embedding_base_url="https://api.cloudflare.com/client/v4/accounts/" + "a" * 32 + "/ai",
        embedding_api_key=secrets.token_hex(24),
        embedding_revision="cf-qwen3-mrl256-v1",
        embedding_query_instruction="Retrieve relevant document passages",
    )
    return Settings(**(values | changes))


def test_cloudflare_selection_catalog_and_openai_stream():
    config = settings()
    assert isinstance(build_model_client(config), CloudflareModelClient)

    def handler(request):
        assert request.headers["Authorization"] == "Bearer " + config.model_api_key
        if request.method == "GET":
            assert request.url.path.endswith("/ai/models/search")
            return httpx.Response(
                200, json={"success": True, "result": [{"name": config.model_name}]}
            )
        assert request.url.path.endswith("/ai/v1/chat/completions")
        body = json.loads(request.content)
        assert body["model"] == config.model_name and body["stream"] is True
        assert body["max_tokens"] == 1024
        return httpx.Response(
            200,
            text=(
                'data: {"choices":[{"delta":{"content":"Synthetic protocol response"}}]}\n\n'
                "data: [DONE]\n\n"
            ),
        )

    async def run():
        client = CloudflareModelClient(config, httpx.MockTransport(handler))
        assert await client.healthy()
        assert (
            "".join([x async for x in client.stream([ModelMessage(role="user", content="Hi")])])
            == "Synthetic protocol response"
        )

    asyncio.run(run())


def test_provider_quota_failure_is_not_retried_or_replaced_by_mock():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            429, json={"error": {"message": "synthetic private provider diagnostic"}}
        )

    async def run():
        client = CloudflareModelClient(settings(), httpx.MockTransport(handler))
        with pytest.raises(InferenceError) as error:
            async for _ in client.stream([ModelMessage(role="user", content="Hi")]):
                pass
        assert "private provider" not in str(error.value)

    asyncio.run(run())
    assert len(calls) == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"model_base_url": "http://api.cloudflare.com/"},
        {
            "model_base_url": "https://api.cloudflare.com.evil.test/client/v4/accounts/"
            + "a" * 32
            + "/ai/v1"
        },
        {"model_name": "@cf/unreviewed/paid-model"},
        {"model_api_key": ""},
        {"embedding_base_url": "https://localhost/ai"},
        {"embedding_api_key": ""},
        {"embedding_name": "@cf/baai/bge-m3"},
        {"embedding_revision": "unversioned"},
    ],
)
def test_unconfigured_or_foreign_or_unreviewed_profiles_fail(changes):
    with pytest.raises(ValidationError):
        settings(**changes)


def response_for(rows):
    return {"success": True, "errors": [], "result": {"shape": [len(rows), 1024], "data": rows}}


def test_explicit_mrl256_normalization_and_query_instruction_version():
    config = settings()
    requests = []

    def handler(request):
        requests.append(json.loads(request.content))
        assert request.url.path.endswith("/ai/run/@cf/qwen/qwen3-embedding-0.6b")
        assert request.headers["Authorization"] == "Bearer " + config.embedding_api_key
        return httpx.Response(200, json=response_for([[1.0] * 1024]))

    for query in (False, True):
        vectors = embeddings(
            ["Synthetic staging document"],
            config,
            query=query,
            transport=httpx.MockTransport(handler),
        )
        assert len(vectors[0]) == 256
        assert math.isclose(sum(x * x for x in vectors[0]), 1.0)
    assert requests[0] == {"documents": ["Synthetic staging document"]}
    assert requests[1] == {
        "queries": ["Synthetic staging document"],
        "instruction": config.embedding_query_instruction,
    }
    assert version(config) == "cloudflare:@cf/qwen/qwen3-embedding-0.6b:cf-qwen3-mrl256-v1:256"


@pytest.mark.parametrize("mode", ["shape", "nan", "zero", "boolean", "count", "error"])
def test_incompatible_embeddings_fail_without_fallback(mode):
    body = response_for([[1.0] * 1024])
    if mode == "shape":
        body["result"]["shape"] = [1, 384]
    elif mode == "count":
        body["result"]["data"] = []
    elif mode == "error":
        body["success"] = False
    else:
        body["result"]["data"][0] = [
            float("nan") if mode == "nan" else False if mode == "boolean" else 0.0
        ] * 1024
    with pytest.raises(ValueError):
        embeddings(
            ["Synthetic input"],
            settings(),
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, content=json.dumps(body))
            ),
        )


def test_input_limits_reject_before_request():
    def unexpected(request):
        pytest.fail("Invalid batch must not reach provider")

    for texts in ([], ["text"] * 17, ["x" * 4001]):
        with pytest.raises(ValueError):
            embeddings(texts, settings(), transport=httpx.MockTransport(unexpected))
