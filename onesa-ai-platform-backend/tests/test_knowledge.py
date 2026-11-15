import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.models import DocumentChunk
from tests.conftest import signup


def test_document_retrieval_rag_and_isolation(api: TestClient, pg: Engine) -> None:
    signup(api)
    upload = api.post(
        "/api/v1/knowledge/documents",
        files={
            "file": (
                "guide.txt",
                b"Harare is the capital of Zimbabwe. Victoria Falls is a waterfall.",
                "text/plain",
            )
        },
    )
    assert upload.status_code == 201, upload.text
    identifier = upload.json()["id"]
    assert (
        api.post(
            "/api/v1/knowledge/documents",
            files={
                "file": (
                    "guide.txt",
                    b"Harare is the capital of Zimbabwe. Victoria Falls is a waterfall.",
                    "text/plain",
                )
            },
        ).status_code
        == 409
    )
    query = {"query": "Harare Zimbabwe", "document_ids": [identifier]}
    sources = api.post("/api/v1/knowledge/search", json=query).json()["sources"]
    assert sources and sources[0]["document_id"] == identifier
    conversation = api.post("/api/v1/conversations", json={}).json()["id"]
    result = api.post(
        "/api/v1/chat/completions",
        json={
            "conversation_id": conversation,
            "content": "What is Harare?",
            "document_ids": [identifier],
            "stream": False,
        },
    )
    assert "capital" in result.json()["content"]
    assert result.json()["sources"][0]["document_id"] == identifier
    history = api.get(f"/api/v1/conversations/{conversation}").json()["messages"]
    assert history[-1]["content"]["sources"][0]["document_id"] == identifier
    cookies = dict(api.cookies)
    signup(api, "other@example.com")
    assert api.get(f"/api/v1/knowledge/documents/{identifier}").status_code == 404
    assert api.post("/api/v1/knowledge/search", json=query).status_code == 404
    assert api.post("/api/v1/knowledge/search", json={"query": "Harare"}).json()["sources"] == []
    api.cookies.clear()
    api.cookies.update(cookies)
    api.headers["X-CSRF-Token"] = api.cookies["onesa_csrf"]
    assert api.post(f"/api/v1/knowledge/documents/{identifier}/reindex").status_code == 200
    assert api.delete(f"/api/v1/knowledge/documents/{identifier}").status_code == 204
    with Session(pg) as db:
        assert db.scalar(select(func.count()).select_from(DocumentChunk)) == 0


def test_document_validation(api: TestClient) -> None:
    signup(api)
    for filename, data, media, expected in [
        ("bad.txt", b"\xff", "text/plain", 422),
        ("fake.pdf", b"fake", "application/pdf", 415),
        ("empty.txt", b"  ", "text/plain", 422),
        ("bad.html", b"<h1>hello</h1>", "text/html", 415),
    ]:
        assert (
            api.post(
                "/api/v1/knowledge/documents", files={"file": (filename, data, media)}
            ).status_code
            == expected
        )


def test_http_embedding_request_is_bounded_and_validates_numeric_vectors():
    import json

    import httpx

    from app.config import Settings
    from app.knowledge import embed

    config = Settings(
        embedding_backend="http",
        embedding_name="test-embedding",
        embedding_base_url="https://embeddings.example.test/v1",
        embedding_api_key="x" * 40,
        embedding_revision="test-v1",
    )
    requests = []

    def handler(request):
        requests.append(request)
        assert request.url.path == "/v1/embeddings"
        assert request.headers["Authorization"] == "Bearer " + config.embedding_api_key
        assert request.headers["Accept-Encoding"] == "identity"
        assert json.loads(request.content) == {
            "model": "test-embedding",
            "input": ["A bounded synthetic query"],
            "dimensions": 256,
        }
        return httpx.Response(
            200,
            json={"data": [{"index": 0, "embedding": [1.0] * 256}]},
        )

    vectors = embed(
        ["A bounded synthetic query"],
        config,
        query=True,
        transport=httpx.MockTransport(handler),
    )
    assert len(requests) == 1
    assert len(vectors) == 1 and len(vectors[0]) == 256
    assert all(value == 1.0 for value in vectors[0])


def test_http_embedding_rejects_boolean_vector_values():
    import httpx
    from fastapi import HTTPException

    from app.config import Settings
    from app.knowledge import embed

    config = Settings(
        embedding_backend="http",
        embedding_name="test-embedding",
        embedding_base_url="https://embeddings.example.test/v1",
        embedding_api_key="x" * 40,
    )
    response = {"data": [{"index": 0, "embedding": [True] + [1.0] * 255}]}
    with pytest.raises(HTTPException) as failure:
        embed(
            ["Synthetic input"],
            config,
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json=response)),
        )
    assert failure.value.status_code == 503
    assert failure.value.detail["code"] == "embedding_unavailable"


def test_http_embedding_rejects_oversized_provider_response():
    import httpx
    from fastapi import HTTPException

    from app.config import Settings
    from app.knowledge import MAX_EMBEDDING_RESPONSE_BYTES, embed

    config = Settings(
        embedding_backend="http",
        embedding_name="test-embedding",
        embedding_base_url="https://embeddings.example.test/v1",
        embedding_api_key="x" * 40,
    )
    response = httpx.Response(
        200,
        headers={"Content-Type": "application/json"},
        content=b" " * (MAX_EMBEDDING_RESPONSE_BYTES + 1),
    )
    with pytest.raises(HTTPException) as failure:
        embed(
            ["Synthetic input"],
            config,
            transport=httpx.MockTransport(lambda request: response),
        )
    assert failure.value.status_code == 503
    assert failure.value.detail["code"] == "embedding_unavailable"
