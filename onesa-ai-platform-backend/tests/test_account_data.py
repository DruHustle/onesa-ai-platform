"""Live personal-data controls preserve isolation and remove derived document data."""

from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.models import (
    AgentRun,
    AuthSession,
    Conversation,
    Document,
    DocumentChunk,
    InferenceRun,
    Message,
    Trip,
    User,
)
from tests.conftest import signup

PASSWORD = "correct-horse-123!"


def test_export_and_delete_owned_resources_and_vectors(api: TestClient, pg: Engine) -> None:
    signup(api, "other@example.com")
    other_conversation = api.post(
        "/api/v1/conversations", json={"title": "Other private chat"}
    ).json()["id"]
    api.post(
        "/api/v1/knowledge/documents",
        files={"file": ("other.txt", b"Other private document", "text/plain")},
    )
    signup(api)
    conversation = api.post("/api/v1/conversations", json={"title": "Exported chat"}).json()["id"]
    assert (
        api.post(
            "/api/v1/chat/completions",
            json={
                "conversation_id": conversation,
                "content": "Personal conversation",
                "stream": False,
            },
        ).status_code
        == 200
    )
    assert (
        api.post(
            "/api/v1/knowledge/documents",
            files={"file": ("mine.txt", b"My owned source document", "text/plain")},
        ).status_code
        == 201
    )
    exported = api.post("/api/v1/account/export", json={"current_password": PASSWORD})
    assert exported.status_code == 200, exported.text
    assert exported.headers["content-disposition"].endswith('filename="onesa-account-export.json"')
    result = exported.json()
    assert result["account"]["email"] == "user@example.com"
    assert len(result["conversations"]) == 1
    assert len(result["conversations"][0]["messages"]) == 2
    assert result["documents"][0]["text"] == "My owned source document"
    assert "Other private" not in exported.text
    assert "password_hash" not in exported.text and "token_hash" not in exported.text
    assert (
        api.post(
            "/api/v1/account/delete", json={"current_password": PASSWORD, "confirmation": "wrong"}
        ).status_code
        == 422
    )
    assert (
        api.post(
            "/api/v1/account/delete",
            json={"current_password": "incorrect", "confirmation": "DELETE MY ACCOUNT"},
        ).status_code
        == 403
    )
    assert (
        api.post(
            "/api/v1/account/delete",
            json={"current_password": PASSWORD, "confirmation": "DELETE MY ACCOUNT"},
        ).status_code
        == 204
    )
    assert "onesa_session" not in api.cookies
    assert api.get("/api/v1/auth/me").status_code == 401
    with Session(pg) as db:
        assert db.query(User).one().email == "other@example.com"
        assert str(db.query(Conversation).one().id) == other_conversation
        assert db.query(Document).one().title == "other.txt"
        assert db.query(DocumentChunk).count() > 0
        assert db.query(Message).count() == 0
        assert db.query(InferenceRun).count() == 0
        assert db.query(AuthSession).one().user_id == db.query(User).one().id
        assert db.query(AgentRun).count() == db.query(Trip).count() == 0


def test_export_is_bounded_and_delete_blocks_active_runs(api: TestClient, pg: Engine) -> None:
    signup(api)
    with Session(pg) as db:
        user = db.scalar(select(User))
        run = AgentRun(user_id=user.id, goal="Active synthetic run", status="running")
        db.add(run)
        db.commit()
    proof = {"current_password": PASSWORD}
    assert (
        api.post(
            "/api/v1/account/delete", json={**proof, "confirmation": "DELETE MY ACCOUNT"}
        ).status_code
        == 409
    )
    with Session(pg) as db:
        run = db.query(AgentRun).one()
        run.status = "cancelled"
        document = Document(
            user_id=db.query(User).one().id,
            title="Large synthetic export",
            media_type="text/plain",
            text="a" * (2 * 1024 * 1024 + 1),
            checksum="a" * 64,
            embedding_version="lexical:test",
        )
        db.add(document)
        db.commit()
    assert api.post("/api/v1/account/export", json=proof).status_code == 413
    assert (
        api.post(
            "/api/v1/account/delete", json={**proof, "confirmation": "DELETE MY ACCOUNT"}
        ).status_code
        == 204
    )
    with Session(pg) as db:
        assert (
            db.query(DocumentChunk).count()
            == db.query(AgentRun).count()
            == db.query(Document).count()
            == 0
        )
