"""Private embedding boundaries and core provider protocol without model downloads."""

import threading
from concurrent.futures import ThreadPoolExecutor

import httpx
from fastapi.testclient import TestClient

from app.config import Settings
from app.knowledge import embed
from embedding_service.server import MODEL, create_app

KEY = "synthetic-local-embedding-test-key-only-12345"


def encoder(texts: list[str], dimensions: int) -> list[list[float]]:
    return [[1.0] + [0.0] * (dimensions - 1) for _ in texts]


def test_embedding_boundary_requires_key_and_bounds_payload() -> None:
    with TestClient(create_app(encoder, KEY)) as client:
        body = {"model": MODEL, "input": ["A synthetic document"], "dimensions": 256}
        assert client.post("/v1/embeddings", json=body).status_code == 401
        headers = {"Authorization": "Bearer " + KEY}
        assert (
            client.post(
                "/v1/embeddings", headers=headers, json={**body, "dimensions": 384}
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/v1/embeddings", headers=headers, json={**body, "input": ["x"] * 17}
            ).status_code
            == 422
        )
        assert (
            client.post("/v1/embeddings", headers=headers, content=b"x" * 65537).status_code == 413
        )
        response = client.post("/v1/embeddings", headers=headers, json=body)
        assert response.status_code == 200
        assert len(response.json()["data"][0]["embedding"]) == 256
        assert response.headers["cache-control"] == "no-store"


def test_bad_encoder_is_sanitized_and_busy_requests_are_rejected() -> None:
    entered, release = threading.Event(), threading.Event()

    def slow(texts, dimensions):
        entered.set()
        assert release.wait(timeout=5)
        raise RuntimeError("synthetic-private-encoder-message")

    with TestClient(create_app(slow, KEY)) as client, ThreadPoolExecutor(max_workers=1) as pool:
        headers = {"Authorization": "Bearer " + KEY}
        body = {"model": MODEL, "input": ["hello"], "dimensions": 256}
        result = pool.submit(client.post, "/v1/embeddings", headers=headers, json=body)
        try:
            assert entered.wait(timeout=3)
            busy = client.post("/v1/embeddings", headers=headers, json=body)
            assert busy.status_code == 429
        finally:
            release.set()
        response = result.result(timeout=5)
        assert response.status_code == 503
        assert "synthetic-private" not in response.text


def test_query_instruction_applies_only_to_query_and_dimension_is_explicit(monkeypatch) -> None:
    requests = []

    def provider(url, **kwargs):
        requests.append(kwargs["json"])
        return httpx.Response(
            200,
            json={"data": [{"index": 0, "embedding": [1.0] + [0.0] * 255}]},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", provider)
    config = Settings(
        embedding_backend="http",
        embedding_name=MODEL,
        embedding_query_instruction="Retrieve relevant passages",
    )
    embed(["Document passage"], config)
    embed(["Search question"], config, query=True)
    assert requests[0] == {"model": MODEL, "input": ["Document passage"], "dimensions": 256}
    assert requests[1]["input"] == ["Instruct: Retrieve relevant passages\nQuery:Search question"]


def test_production_embedding_transport_rejects_development_endpoint() -> None:
    import pytest

    base = dict(
        environment="production",
        database_url="postgresql://app:dummy@db/app",
        public_origin="https://app.example.com",
        secure_cookies=True,
        metrics_token="x" * 32,
        model_backend="vllm",
        model_base_url="https://inference.example.com/v1",
        model_api_key="synthetic-key",
        embedding_backend="http",
        embedding_api_key="synthetic-key",
    )
    for url in [
        "http://private.example.com/v1",
        "https://localhost/v1",
        "https://[::ffff:127.0.0.1]/v1",
    ]:
        with pytest.raises(ValueError, match="Production embeddings"):
            Settings(**base, embedding_base_url=url)
    assert (
        Settings(**base, embedding_base_url="https://embeddings.example.com/v1").embedding_backend
        == "http"
    )
