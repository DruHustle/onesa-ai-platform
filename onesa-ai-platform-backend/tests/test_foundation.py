import asyncio
from collections.abc import AsyncIterator, Sequence
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings
from app.inference import MockModelClient, ModelMessage
from app.main import create_app


def test_liveness_and_mock_readiness() -> None:
    with TestClient(create_app(Settings())) as api:
        response = api.get("/health", headers={"X-Request-ID": "untrusted"})
        assert response.json() == {"status": "ok"}
        UUID(response.headers["X-Request-ID"])
        assert api.get("/ready").json() == {"status": "ready", "backend": "mock"}


@pytest.mark.parametrize("failure", [False, RuntimeError("internal secret")])
def test_unavailable_backend_is_not_ready(failure: bool | Exception) -> None:
    class Unavailable(MockModelClient):
        async def healthy(self) -> bool:
            if isinstance(failure, Exception):
                raise failure
            return failure

    with TestClient(create_app(Settings(), Unavailable())) as api:
        response = api.get("/ready")
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "dependency_unavailable"
        assert response.json()["error"]["request_id"] == response.headers["X-Request-ID"]
        assert "secret" not in response.text


def test_environment_config_and_no_silent_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ONESA_MODEL_NAME", "future-onesa-model")
    assert Settings().model_name == "future-onesa-model"
    monkeypatch.setenv("ONESA_MODEL_BACKEND", "unsupported")
    with pytest.raises(ValidationError):
        create_app()


@pytest.mark.parametrize("tokens", [0, -1, 8193])
def test_output_limit_validation(tokens: int) -> None:
    with pytest.raises(ValidationError):
        Settings(model_max_output_tokens=tokens)


def test_mock_stream_preserves_unicode_and_is_explicitly_mock() -> None:
    async def collect() -> str:
        messages = [ModelMessage(role="user", content="Mhoro 🌍")]
        return "".join([chunk async for chunk in MockModelClient().stream(messages)])

    assert asyncio.run(collect()) == "[Mock response — no AI inference] Mhoro 🌍"


def test_mock_rejects_invalid_history() -> None:
    async def collect(messages: Sequence[ModelMessage]) -> None:
        async for _ in MockModelClient().stream(messages):
            pass

    with pytest.raises(ValueError):
        asyncio.run(collect([]))
    with pytest.raises(ValueError):
        asyncio.run(collect([ModelMessage(role="assistant", content="Hi")]))


def test_readiness_timeout() -> None:
    class Slow(MockModelClient):
        async def healthy(self) -> bool:
            await asyncio.sleep(10)
            return True

    with TestClient(create_app(Settings(), Slow())) as api:
        assert api.get("/ready").status_code == 503


def test_cancelling_mock_stream_stops_generation() -> None:
    async def cancel() -> None:
        stream: AsyncIterator[str] = MockModelClient().stream(
            [ModelMessage(role="user", content="x" * 32000)]
        )

        async def consume() -> None:
            async for _ in stream:
                pass

        task = asyncio.create_task(consume())
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(cancel())
