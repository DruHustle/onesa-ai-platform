from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.chat import CONVERSATION_INSTRUCTION
from app.inference import InferenceError, MockModelClient
from app.models import AuthSession, Conversation, InferenceRun, Message, User, now
from tests.conftest import signup


def new(api: TestClient) -> str:
    response = api.post("/api/v1/conversations", json={"title": "My chat"})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_auth_csrf_rotation_logout(api: TestClient, pg: Engine) -> None:
    signup(api)
    token = api.cookies["onesa_session"]
    assert api.get("/api/v1/auth/me").status_code == 200
    with Session(pg) as db:
        row = db.scalar(select(AuthSession))
        assert row is not None and row.token_hash != token
        user = db.scalar(select(User))
        assert user is not None and user.password_hash.startswith("$argon2id$")
    api.headers.pop("X-CSRF-Token")
    assert api.post("/api/v1/conversations", json={}).status_code == 403
    api.headers["X-CSRF-Token"] = api.cookies["onesa_csrf"]
    assert api.post("/api/v1/auth/refresh").status_code == 200
    assert token != api.cookies["onesa_session"]
    api.headers["X-CSRF-Token"] = api.cookies["onesa_csrf"]
    assert api.post("/api/v1/auth/logout").status_code == 204
    assert api.get("/api/v1/auth/me").status_code == 401
    api.cookies.set("onesa_session", token)
    assert api.get("/api/v1/auth/me").status_code == 401


def test_login_and_expiry(api: TestClient, pg: Engine) -> None:
    signup(api)
    assert api.post("/api/v1/auth/logout").status_code == 204
    data = {"email": "USER@example.com", "password": "wrong-password-123"}
    assert api.post("/api/v1/auth/login", json=data).status_code == 401
    data["password"] = "correct-horse-123!"
    assert api.post("/api/v1/auth/login", json=data).status_code == 200
    with Session(pg) as db:
        for row in db.scalars(select(AuthSession)):
            row.expires_at = now() - timedelta(seconds=1)
        db.commit()
    assert api.get("/api/v1/auth/me").status_code == 401


def test_origin_and_rate_limit(api: TestClient, fixed_auth_window) -> None:
    data = {"email": "nobody@example.com", "password": "wrong-password-123"}
    api.headers["Origin"] = "https://attacker.invalid"
    assert api.post("/api/v1/auth/login", json=data).status_code == 403
    api.headers["Origin"] = "http://localhost:3000"
    api.app.state.settings.auth_rate_limit = 1
    assert api.post("/api/v1/auth/login", json=data).status_code == 401
    assert api.post("/api/v1/auth/login", json=data).status_code == 429


def test_chat_persistence_crud_and_ownership(api: TestClient, pg: Engine) -> None:
    signup(api)
    identifier = new(api)
    payload = {"conversation_id": identifier, "content": "Mhoro 🌍"}
    response = api.post("/api/v1/chat/completions", json=payload)
    assert response.status_code == 200
    assert "event: message_start" in response.text and "event: message_end" in response.text
    assert "event: content_delta" in response.text
    history = api.get(f"/api/v1/conversations/{identifier}").json()["messages"]
    assert [m["sequence"] for m in history] == [1, 2]
    assert history[1]["content"]["text"].endswith("Mhoro 🌍")
    payload.update(content="Second turn", stream=False)
    assert api.post("/api/v1/chat/completions", json=payload).json()["message_id"]
    assert (
        api.patch(f"/api/v1/conversations/{identifier}", json={"title": "Renamed"}).status_code
        == 200
    )
    assert api.get("/api/v1/conversations?limit=1").json()["total"] == 1
    owner_cookies = dict(api.cookies)
    signup(api, "other@example.com")
    assert api.get(f"/api/v1/conversations/{identifier}").status_code == 404
    assert api.post("/api/v1/chat/completions", json=payload).status_code == 404
    assert api.get("/api/v1/conversations").json()["items"] == []
    api.cookies.clear()
    api.cookies.update(owner_cookies)
    api.headers["X-CSRF-Token"] = api.cookies["onesa_csrf"]
    assert api.delete(f"/api/v1/conversations/{identifier}").status_code == 204
    with Session(pg) as db:
        assert db.scalar(select(func.count()).select_from(Message)) == 0
        assert db.scalar(select(func.count()).select_from(InferenceRun)) == 0


def test_model_failure_keeps_user_but_not_partial_assistant(api: TestClient, pg: Engine) -> None:
    class Broken(MockModelClient):
        async def stream(self, messages):
            yield "partial"
            raise RuntimeError("private-url/secret")

    signup(api)
    identifier = new(api)
    api.app.state.model_client = Broken()
    response = api.post(
        "/api/v1/chat/completions", json={"conversation_id": identifier, "content": "Hello"}
    )
    assert "event: error" in response.text and "event: message_end" not in response.text
    assert "secret" not in response.text
    with Session(pg) as db:
        assert db.scalar(select(func.count()).select_from(Message)) == 1
        run = db.scalar(select(InferenceRun))
        assert run is not None and run.status == "failed"
        row = db.get(Conversation, UUID(identifier))
        assert row is not None and row.active_run_id is None


@pytest.mark.parametrize("empty", [False, True])
def test_failed_chat_reports_safe_reason_and_releases_lease(api, pg, empty):
    import json

    class Broken(MockModelClient):
        async def stream(self, messages):
            if empty:
                return
            yield "partial"
            raise InferenceError(
                "generation_failed", reason="provider_stream_error", provider_error_code=3040
            )

    signup(api)
    identifier = new(api)
    api.app.state.model_client = Broken()
    response = api.post(
        "/api/v1/chat/completions", json={"conversation_id": identifier, "content": "Synthetic"}
    )
    error_frame = next(
        frame for frame in response.text.split("\n\n") if frame.startswith("event: error")
    )
    error = json.loads(error_frame.split("data: ", 1)[1])
    assert error["code"] == "generation_failed"
    assert error["message"] == "Response interrupted; retry"
    assert error["failure_reason"] == ("empty_model_response" if empty else "provider_stream_error")
    assert error.get("provider_error_code") == (None if empty else 3040)
    assert "event: message_end" not in response.text
    with Session(pg) as db:
        assert db.scalar(select(func.count()).select_from(Message)) == 1
        assert db.scalar(select(InferenceRun)).status == "failed"
        assert db.get(Conversation, UUID(identifier)).active_run_id is None


def test_long_history_bounds_database_read_and_preserves_context_order(api, pg):
    from sqlalchemy import event

    signup(api)
    identifier = new(api)
    with Session(pg) as db:
        db.add_all(
            Message(
                conversation_id=UUID(identifier),
                role="user" if sequence % 2 else "assistant",
                content={"text": f"turn-{sequence}"},
                sequence=sequence,
            )
            for sequence in range(1, 76)
        )
        db.commit()
    context = []
    bounded_queries = []

    class Capture(MockModelClient):
        async def stream(self, messages):
            context.extend(messages)
            yield "Synthetic response"

    def observe(_conn, _cursor, statement, parameters, _context, _executemany):
        if "FROM messages" in statement and "ORDER BY messages.sequence DESC" in statement:
            bounded_queries.append((statement, parameters))

    api.app.state.model_client = Capture()
    event.listen(api.app.state.engine, "before_cursor_execute", observe)
    try:
        response = api.post(
            "/api/v1/chat/completions",
            json={"conversation_id": identifier, "content": "Next", "stream": False},
        )
        assert response.status_code == 200
    finally:
        event.remove(api.app.state.engine, "before_cursor_execute", observe)
    assert [message.content for message in context] == [
        CONVERSATION_INSTRUCTION,
        *[f"turn-{sequence}" for sequence in range(46, 76)],
        "Next",
    ]
    assert context[0].role == "system"
    assert len(bounded_queries) == 1 and "LIMIT" in bounded_queries[0][0]
    assert 30 in bounded_queries[0][1].values()
    history = api.get(f"/api/v1/conversations/{identifier}").json()["messages"]
    assert [item["sequence"] for item in history] == list(range(1, 78))


def test_each_turn_receives_supplied_context_without_persisting_system_instruction(api):
    signup(api)
    identifier = new(api)
    requests = []

    class Capture(MockModelClient):
        async def stream(self, messages):
            requests.append([(message.role, message.content) for message in messages])
            yield "Acknowledged."

    api.app.state.model_client = Capture()
    for content in ["Remember the orchard name: Alder.", "Which orchard did I name?"]:
        response = api.post(
            "/api/v1/chat/completions",
            json={"conversation_id": identifier, "content": content, "stream": False},
        )
        assert response.status_code == 200
    assert requests == [
        [("system", CONVERSATION_INSTRUCTION), ("user", "Remember the orchard name: Alder.")],
        [
            ("system", CONVERSATION_INSTRUCTION),
            ("user", "Remember the orchard name: Alder."),
            ("assistant", "Acknowledged."),
            ("user", "Which orchard did I name?"),
        ],
    ]
    history = api.get(f"/api/v1/conversations/{identifier}").json()["messages"]
    assert [item["role"] for item in history] == ["user", "assistant", "user", "assistant"]
    assert all(item["content"]["text"] != CONVERSATION_INSTRUCTION for item in history)


def test_busy_and_expired_lease_recovery(api: TestClient, pg: Engine) -> None:
    signup(api)
    identifier = new(api)
    with Session(pg) as db:
        row = db.get(Conversation, UUID(identifier))
        assert row is not None
        row.active_run_id = uuid4()
        row.lease_until = now() + timedelta(seconds=60)
        db.commit()
    payload = {"conversation_id": identifier, "content": "Hello", "stream": False}
    assert api.post("/api/v1/chat/completions", json=payload).status_code == 409
    with Session(pg) as db:
        row = db.get(Conversation, UUID(identifier))
        assert row is not None
        row.lease_until = now() - timedelta(seconds=1)
        db.commit()
    assert api.post("/api/v1/chat/completions", json=payload).status_code == 200


def test_database_constraints(api: TestClient, pg: Engine) -> None:
    signup(api)
    identifier = new(api)
    with Session(pg) as db:
        db.add(
            Message(
                conversation_id=UUID(identifier), role="user", content={"text": "Hi"}, sequence=1
            )
        )
        db.commit()
        db.add(
            Message(
                conversation_id=UUID(identifier), role="user", content={"text": "Race"}, sequence=1
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        db.add(
            Message(conversation_id=uuid4(), role="user", content={"text": "No parent"}, sequence=1)
        )
        with pytest.raises(IntegrityError):
            db.commit()


def test_validation_does_not_echo_password(api: TestClient) -> None:
    response = api.post("/api/v1/auth/register", json={"password": "secret"})
    assert response.status_code == 422 and "secret" not in response.text


def test_concurrent_generation_is_serialized(api: TestClient) -> None:
    import asyncio
    import threading
    from concurrent.futures import ThreadPoolExecutor

    started = threading.Event()

    class Slow(MockModelClient):
        async def stream(self, messages):
            started.set()
            await asyncio.sleep(0.2)
            yield "Complete response"

    signup(api)
    identifier = new(api)
    api.app.state.model_client = Slow()
    body = {"conversation_id": identifier, "content": "First", "stream": False}
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(api.post, "/api/v1/chat/completions", json=body)
        assert started.wait(timeout=2)
        assert api.post("/api/v1/chat/completions", json=body).status_code == 409
        assert future.result(timeout=3).status_code == 200


def test_network_disconnect_cancels_without_partial_assistant(api: TestClient, pg: Engine) -> None:
    import asyncio
    import socket
    import threading
    import time

    import httpx
    import uvicorn

    class Slow(MockModelClient):
        async def stream(self, messages):
            yield "partial"
            await asyncio.sleep(10)
            yield "should not complete"

    signup(api)
    identifier = new(api)
    api.app.state.model_client = Slow()
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(api.app, log_level="critical", access_log=False))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
    thread.start()
    deadline = time.monotonic() + 3
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.01)
    assert server.started
    try:
        with httpx.Client(
            base_url=f"http://127.0.0.1:{port}",
            cookies=dict(api.cookies),
            headers={"Origin": "http://localhost:3000", "X-CSRF-Token": api.cookies["onesa_csrf"]},
        ) as client:
            with client.stream(
                "POST",
                "/api/v1/chat/completions",
                json={"conversation_id": identifier, "content": "Stop generation"},
            ) as response:
                assert response.status_code == 200
                for line in response.iter_lines():
                    if line.startswith("event: content_delta"):
                        break
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            with Session(pg) as db:
                run = db.scalar(select(InferenceRun))
                if run and run.status == "cancelled":
                    assert db.scalar(select(func.count()).select_from(Message)) == 1
                    break
            time.sleep(0.02)
        else:
            pytest.fail("Disconnected generation did not release its lease")
    finally:
        server.should_exit = True
        thread.join(timeout=3)
        listener.close()


def test_real_adapter_metadata_usage_and_recovery(api: TestClient, pg: Engine) -> None:
    import json

    import httpx

    from app.inference import OllamaModelClient

    available = True

    def handler(request: httpx.Request) -> httpx.Response:
        if not available:
            return httpx.Response(404, json={"error": "secret-internal-host"})
        assert json.loads(request.content)["messages"][-1]["role"] == "user"
        return httpx.Response(
            200,
            text='data: {"choices":[{"delta":{"content":"Generated fixture"}}]}\n\n'
            'data: {"choices":[],"usage":{"prompt_tokens":10,"completion_tokens":2}}\n\n'
            "data: [DONE]\n\n",
        )

    signup(api)
    api.app.state.settings.model_backend = "ollama"
    api.app.state.settings.model_base_url = "https://model.example.invalid/v1"
    api.app.state.settings.model_name = "test-model"
    api.app.state.model_client = OllamaModelClient(
        api.app.state.settings, httpx.MockTransport(handler)
    )
    identifier = new(api)
    payload = {"conversation_id": identifier, "content": "Hi", "stream": False}
    response = api.post("/api/v1/chat/completions", json=payload)
    assert response.status_code == 200
    assert response.json()["model"]["backend"] == "ollama"
    assert response.json()["metrics"]["output_tokens"] == 2
    with Session(pg) as db:
        run = db.scalar(select(InferenceRun))
        assert run.input_tokens == 10 and run.output_tokens == 2
    available = False
    response = api.post("/api/v1/chat/completions", json=payload)
    assert response.status_code == 503 and "secret" not in response.text
    assert response.json()["error"]["code"] == "model_not_available"
    available = True
    assert api.post("/api/v1/chat/completions", json=payload).status_code == 200
    history = api.get(f"/api/v1/conversations/{identifier}").json()["messages"]
    assert len(history) == 5
    assert history[-1]["content"]["inference"]["model"]["model_identifier"] == "test-model"
