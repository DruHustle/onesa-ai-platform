"""Explicit opt-in real model acceptance against disposable PostgreSQL only."""

import os
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.inference import build_model_client
from app.models import Document, DocumentChunk
from tests.conftest import signup

ENDPOINT = os.environ.get("ONESA_SEMANTIC_TEST_ENDPOINT")
KEY_FILE = os.environ.get("ONESA_SEMANTIC_TEST_KEY_FILE")
pytestmark = pytest.mark.skipif(
    not ENDPOINT or not KEY_FILE, reason="Explicit local semantic test service/key file required"
)
REVISION = "97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3:qwen-retrieval-v1"
PASSAGE = (
    "Wenn die Temperatur eines Akkupacks über den sicheren Betriebsbereich steigt, "
    "wird das Laden unterbrochen. Ein Techniker prüft die Kühlung und den Zustand "
    "der Zellen."
)


def semantic(api: TestClient) -> None:
    config = api.app.state.settings
    config.embedding_backend = "http"
    config.embedding_name = "Qwen/Qwen3-Embedding-0.6B"
    config.embedding_base_url = ENDPOINT
    config.embedding_api_key = Path(KEY_FILE).read_text().strip()
    config.embedding_revision = REVISION
    config.embedding_query_instruction = (
        "Given a user question, retrieve relevant document passages that answer the question"
    )


def upload(api: TestClient, title="battery.txt", text=PASSAGE) -> str:
    response = api.post(
        "/api/v1/knowledge/documents", files={"file": (title, text.encode(), "text/plain")}
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_actual_semantic_pgvector_cross_language_isolation_and_deletion(
    api: TestClient, pg: Engine
) -> None:
    signup(api)
    semantic(api)
    identifier = upload(api)
    question = "What should happen when a battery gets too hot during charging?"
    response = api.post(
        "/api/v1/knowledge/search", json={"query": question, "document_ids": [identifier]}
    )
    assert response.status_code == 200, response.text
    assert response.json()["backend"] == "http"
    assert response.json()["sources"][0]["document_id"] == identifier
    with Session(pg) as db:
        chunk = db.query(DocumentChunk).one()
        assert len(chunk.embedding) == 256
        assert abs(sum(float(v) ** 2 for v in chunk.embedding) - 1) < 0.001
    cookies = dict(api.cookies)
    signup(api, "other@example.com")
    assert api.post("/api/v1/knowledge/search", json={"query": question}).json()["sources"] == []
    assert (
        api.post(
            "/api/v1/knowledge/search", json={"query": question, "document_ids": [identifier]}
        ).status_code
        == 404
    )
    assert api.post(f"/api/v1/knowledge/documents/{identifier}/reindex").status_code == 404
    assert api.delete(f"/api/v1/knowledge/documents/{identifier}").status_code == 404
    api.cookies.clear()
    api.cookies.update(cookies)
    api.headers["X-CSRF-Token"] = api.cookies["onesa_csrf"]
    assert api.delete(f"/api/v1/knowledge/documents/{identifier}").status_code == 204
    assert api.post("/api/v1/knowledge/search", json={"query": question}).json()["sources"] == []
    with Session(pg) as db:
        assert db.query(DocumentChunk).count() == 0


def test_reindex_replaces_lexical_and_preserves_previous_vectors_on_failure(
    api: TestClient, pg: Engine, monkeypatch
) -> None:
    signup(api)
    identifier = upload(api)
    lexical = api.get(f"/api/v1/knowledge/documents/{identifier}").json()["embedding_version"]
    semantic(api)
    assert (
        api.post("/api/v1/knowledge/search", json={"query": "battery heat"}).json()["sources"] == []
    )
    indexed = api.post(f"/api/v1/knowledge/documents/{identifier}/reindex")
    assert indexed.status_code == 200, indexed.text
    assert indexed.json()["embedding_version"] != lexical
    with Session(pg) as db:
        before = [
            (str(row.id), list(row.embedding), row.embedding_version)
            for row in db.scalars(select(DocumentChunk))
        ]

    def unavailable(*args, **kwargs):
        raise httpx.ConnectError("synthetic-private-upstream-error")

    monkeypatch.setattr(httpx, "post", unavailable)
    failed = api.post(f"/api/v1/knowledge/documents/{identifier}/reindex")
    assert failed.status_code == 503
    assert "synthetic-private" not in failed.text
    with Session(pg) as db:
        after = [
            (str(row.id), list(row.embedding), row.embedding_version)
            for row in db.scalars(select(DocumentChunk))
        ]
        assert after == before
        assert db.query(Document).one().embedding_version == indexed.json()["embedding_version"]


@pytest.mark.skipif(
    os.environ.get("ONESA_REAL_INFERENCE") != "1",
    reason="Existing authorized native Qwen chat inference must be explicitly selected",
)
def test_real_chat_uses_semantic_sources_and_persists_grounded_answer(api: TestClient) -> None:
    signup(api)
    semantic(api)
    identifier = upload(api)
    config = api.app.state.settings
    config.model_backend = "ollama"
    config.model_name = "qwen3:4b-instruct-2507-q4_K_M"
    config.model_base_url = "http://127.0.0.1:11434/v1"
    config.model_context_length = 8192
    config.model_max_output_tokens = 128
    api.app.state.model_client = build_model_client(config)
    conversation = api.post("/api/v1/conversations", json={}).json()["id"]
    response = api.post(
        "/api/v1/chat/completions",
        json={
            "conversation_id": conversation,
            "content": (
                "Based only on the uploaded passage, what must happen when a battery overheats "
                "while charging? Reply in English in one sentence."
            ),
            "document_ids": [identifier],
            "stream": False,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["sources"][0]["document_id"] == identifier
    answer = response.json()["content"].lower()
    assert "charg" in answer and any(
        word in answer for word in ["stop", "interrupt", "halt", "discontinu", "suspend", "ceas"]
    ), response.text
    saved = api.get(f"/api/v1/conversations/{conversation}").json()["messages"][-1]
    assert saved["content"]["text"] == response.json()["content"]
    assert saved["content"]["sources"][0]["document_id"] == identifier
