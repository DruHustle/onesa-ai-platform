"""Portable transport and stateless API regressions with synthetic providers."""

import asyncio
import json
from dataclasses import asdict
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from app import capacity, consumer_api
from app.auth import authenticated
from app.config import Settings
from app.consumer import (
    CONTRACT_VERSION,
    CompletionError,
    Connection,
    Message,
    complete,
    https_base,
)
from app.inference import InferenceError
from app.main import create_app
from tests.conftest import signup

HISTORY = [
    Message("system", "Read-only advisory"),
    Message("user", "The asset is P-101"),
    Message("assistant", "Recorded P-101"),
    Message("user", "Which asset?"),
]


def onesa_connection(**extra):
    return Connection(
        "onesa",
        "https://onesa.example.test",
        session="synthetic-session",
        csrf="synthetic-csrf",
        origin="https://console.example.test",
        **extra,
    )


def compatible_response(**changes):
    return {
        "model": "synthetic-model",
        "choices": [
            {
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": "P-101", **changes},
            }
        ],
    }


@pytest.mark.parametrize(
    "base",
    [
        "http://localhost:80",
        "https://u:p@host.test",
        "https://host.test?q=x",
        "https://host.test/#x",
        "https://host.test\\other",
        "https://host.test:0",
        "https://host.test/\n",
        "https://host.test:70000",
        "https://",
    ],
)
def test_endpoint_must_be_operator_selected_verified_https(base):
    with pytest.raises(ValueError):
        https_base(base)


def test_same_consumer_business_code_preserves_history_across_providers():
    requests, ledger = [], []

    def handle(request):
        requests.append(request)
        body = json.loads(request.content)
        assert body["messages"] == [asdict(m) for m in HISTORY]
        if request.url.path == "/api/v1/inference/completions":
            assert "Authorization" not in request.headers
            assert request.headers["X-CSRF-Token"] == "synthetic-csrf"
            assert request.headers["Origin"] == "https://console.example.test"
            assert request.headers["Cookie"] == "onesa_session=synthetic-session"
            return httpx.Response(
                200,
                json={
                    "contract_version": CONTRACT_VERSION,
                    "outcome": "completed",
                    "text": "P-101",
                    "model": {"model_identifier": "synthetic-model", "real_inference": False},
                },
            )
        assert request.url.path == "/gateway/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer synthetic-key"
        assert "Cookie" not in request.headers and "X-CSRF-Token" not in request.headers
        assert body["stream"] is False and "tools" not in body
        return httpx.Response(200, json=compatible_response())

    async def application(connection):
        result = await complete(connection, HISTORY, transport=httpx.MockTransport(handle))
        ledger.append({"messages": [asdict(m) for m in HISTORY], "completion": asdict(result)})
        return result.text

    assert asyncio.run(application(onesa_connection())) == "P-101"
    other = Connection(
        "openai-compatible",
        "https://alternative.example.test/gateway/v1",
        "alternative-model",
        api_key="synthetic-key",
    )
    assert asyncio.run(application(other)) == "P-101"
    assert len(requests) == 2 and ledger[0]["messages"] == ledger[1]["messages"]
    assert ledger[0]["completion"]["provider"] != ledger[1]["completion"]["provider"]
    assert ledger[0]["completion"]["inference_kind"] == "mock"
    assert "synthetic-key" not in repr(other) and "synthetic-session" not in repr(
        onesa_connection()
    )


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(401, text="private-provider-details"),
        httpx.Response(302, headers={"Location": "https://foreign.example.test"}),
        httpx.Response(200, text="not-json", headers={"Content-Type": "application/json"}),
        httpx.Response(
            200,
            content=b'{"private-provider-details":' + b"[" * 2000 + b"0" + b"]" * 2000 + b"}",
            headers={"Content-Type": "application/json"},
        ),
        httpx.Response(200, json=[]),
        httpx.Response(200, json={"error": {"message": "private-provider-details"}}),
        httpx.Response(200, json={"model": "model", "choices": []}),
        httpx.Response(200, json={"model": "model", "choices": [{"message": []}]}),
        httpx.Response(200, json=compatible_response(tool_calls=[{"function": "launch"}])),
        httpx.Response(200, json=compatible_response(content="x" * 8001)),
        httpx.Response(200, json=compatible_response(content=" ")),
        httpx.Response(200, json=compatible_response(content={"text": "wrong type"})),
        httpx.Response(200, json=compatible_response(refusal="refused")),
        httpx.Response(
            200,
            json={
                "model": "model",
                "choices": [
                    {
                        "finish_reason": "length",
                        "message": {"role": "assistant", "content": "partial"},
                    }
                ],
            },
        ),
        httpx.Response(
            200,
            json={
                "model": "model",
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {"role": "assistant", "content": "partial"},
                    }
                ],
            },
        ),
        httpx.Response(200, content=b"x" * 65537, headers={"Content-Type": "application/json"}),
    ],
)
def test_incompatible_or_failed_provider_never_becomes_success_or_redirect(response):
    calls = []

    def handle(request):
        calls.append(request)
        return response

    cfg = Connection(
        "openai-compatible", "https://provider.example.test/v1", api_key="synthetic-key"
    )
    with pytest.raises(CompletionError) as exc:
        asyncio.run(complete(cfg, HISTORY, transport=httpx.MockTransport(handle)))
    assert len(calls) == 1
    assert "private-provider-details" not in str(exc.value)


def test_timeout_and_cancellation_do_not_retry():
    calls = []

    def timeout(request):
        calls.append(request)
        raise httpx.ReadTimeout("private-provider-details")

    with pytest.raises(CompletionError):
        asyncio.run(complete(onesa_connection(), HISTORY, transport=httpx.MockTransport(timeout)))
    assert len(calls) == 1

    async def cancelled(request):
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(complete(onesa_connection(), HISTORY, transport=httpx.MockTransport(cancelled)))


@pytest.mark.parametrize(
    "usage", [{"prompt_tokens": -1}, {"completion_tokens": True}, {"prompt_tokens": "1"}, None]
)
def test_unknown_usage_is_not_fabricated_and_invalid_usage_is_refused(usage):
    cfg = Connection(
        "openai-compatible", "https://provider.example.test/v1", api_key="synthetic-key"
    )

    def handle(_):
        return httpx.Response(200, json={**compatible_response(), "usage": usage})

    with pytest.raises(CompletionError):
        asyncio.run(complete(cfg, HISTORY, transport=httpx.MockTransport(handle)))


@pytest.mark.parametrize(
    "history",
    [
        [],
        [Message("assistant", "not final user")],
        [Message("user", "x" * 32001)],
        [Message("user", " ")],
        [Message("tool", "launch")],
    ],
)
def test_invalid_history_refused_without_network(history):
    def forbidden(_):
        pytest.fail("Invalid history must not leave the consumer")

    with pytest.raises(ValueError):
        asyncio.run(complete(onesa_connection(), history, transport=httpx.MockTransport(forbidden)))


@pytest.fixture
def consumer_fixture(monkeypatch):
    state = {"admitted": 0, "released": 0, "active": True, "messages": [], "closed": False}

    class Model:
        async def healthy(self):
            return True

        async def stream(self, messages):
            state["messages"] = messages
            try:
                yield "P-101"
            finally:
                state["closed"] = True

    cfg = Settings(consumer_inference_enabled=True, environment="test")
    app = create_app(cfg, Model())
    app.dependency_overrides[authenticated] = lambda: (SimpleNamespace(id=uuid4()), None)

    def begin(_):
        state["admitted"] += 1
        return uuid4()

    def end(*_):
        state["released"] += 1

    monkeypatch.setattr(capacity, "begin", begin)
    monkeypatch.setattr(capacity, "end", end)
    monkeypatch.setattr(capacity, "active", lambda *_: state["active"])
    return app, state


def test_actual_stateless_route_and_client_round_trip_preserve_roles(consumer_fixture):
    app, state = consumer_fixture
    result = asyncio.run(complete(onesa_connection(), HISTORY, transport=httpx.ASGITransport(app)))
    assert result.text == "P-101" and result.inference_kind == "mock"
    assert [m.model_dump() for m in state["messages"]] == [asdict(m) for m in HISTORY]
    assert state["admitted"] == state["released"] == 1 and state["closed"]


def test_feature_default_and_unsupported_input_do_not_reserve_capacity(consumer_fixture):
    app, state = consumer_fixture
    body = {"messages": [asdict(m) for m in HISTORY]}
    with TestClient(app) as client:
        app.state.settings.consumer_inference_enabled = False
        assert client.post("/api/v1/inference/completions", json=body).status_code == 404
        app.state.settings.consumer_inference_enabled = True
        for change in (
            {"tools": []},
            {"stream": True},
            {"model_id": "foreign"},
            {"messages": [{"role": "tool", "content": "launch"}]},
        ):
            assert (
                client.post("/api/v1/inference/completions", json={**body, **change}).status_code
                == 422
            )
    assert state["admitted"] == state["released"] == 0
    assert Settings().consumer_inference_enabled is False


def test_body_limit_precedes_parsing_and_model_admission(consumer_fixture):
    app, state = consumer_fixture
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/inference/completions",
            content=b"x" * (384 * 1024 + 1),
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 413
    assert state["admitted"] == state["released"] == 0


@pytest.mark.parametrize(
    "mode", ["revoked", "timeout", "oversize", "failed", "empty", "unexpected"]
)
def test_route_discards_partial_results_and_releases_owned_task(consumer_fixture, mode):
    app, state = consumer_fixture

    class Failure:
        async def stream(self, messages):
            try:
                if mode == "oversize":
                    yield "x" * 8001
                elif mode != "empty":
                    yield "partial-private-text"
                    if mode == "revoked":
                        state["active"] = False
                        await asyncio.sleep(10)
                    elif mode == "timeout":
                        await asyncio.sleep(10)
                    elif mode == "unexpected":
                        raise RuntimeError("private-provider-error")
                    else:
                        raise InferenceError()
            finally:
                state["closed"] = True

    app.state.model_client = Failure()
    app.state.settings.generation_timeout = 1
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/inference/completions",
            json={"messages": [{"role": "user", "content": "Explain"}]},
        )
    assert response.status_code == (401 if mode == "revoked" else 503)
    assert "partial-private-text" not in response.text
    assert "private-provider-error" not in response.text
    assert state["admitted"] == state["released"] == 1 and state["closed"]


def test_real_auth_csrf_budgets_and_stateless_storage(api, pg):
    """Requires the existing isolated PostgreSQL fixture; never runtime data."""
    from sqlalchemy import func, select
    from sqlalchemy.orm import Session

    from app.models import Conversation, ModelLease
    from app.models import Message as StoredMessage

    api.app.state.settings.consumer_inference_enabled = True
    body = {"messages": [{"role": "user", "content": "Synthetic portable request"}]}
    assert api.post("/api/v1/inference/completions", json=body).status_code == 401
    signup(api)
    csrf = api.headers.pop("X-CSRF-Token")
    assert api.post("/api/v1/inference/completions", json=body).status_code == 403
    api.headers["X-CSRF-Token"] = csrf
    assert api.post("/api/v1/inference/completions", json=body).status_code == 200
    with Session(pg) as db:
        for model in (Conversation, StoredMessage, ModelLease):
            assert db.scalar(select(func.count()).select_from(model)) == 0
    api.app.state.settings.model_user_requests_per_minute = 1
    assert api.post("/api/v1/inference/completions", json=body).status_code == 429
    api.post("/api/v1/auth/logout")
    assert api.post("/api/v1/inference/completions", json=body).status_code == 401


@pytest.mark.parametrize("reason", ["length", "content_filter", "tool_calls", "function_call"])
def test_upstream_explicit_truncation_or_nontext_finish_is_not_a_completed_advisory(
    consumer_fixture, reason
):
    from app.inference import OpenAIModelClient

    app, state = consumer_fixture

    def handle(_):
        data = {
            "choices": [{"delta": {"content": "private-partial-text"}, "finish_reason": reason}]
        }
        return httpx.Response(200, text="data: " + json.dumps(data) + "\n\ndata: [DONE]\n\n")

    cfg = Settings(model_base_url="https://provider.example.test/v1")
    app.state.model_client = OpenAIModelClient(cfg, httpx.MockTransport(handle))
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/inference/completions",
            json={"messages": [{"role": "user", "content": "Explain"}]},
        )
    assert response.status_code == 503 and "private-partial-text" not in response.text
    assert state["admitted"] == state["released"] == 1


def test_disconnected_consumer_cancels_its_owned_task(consumer_fixture):
    from fastapi import HTTPException

    app, state = consumer_fixture

    async def disconnected():
        return True

    request = SimpleNamespace(
        app=app, is_disconnected=disconnected, state=SimpleNamespace(request_id=str(uuid4()))
    )
    body = consumer_api.ConsumerRequest(messages=[{"role": "user", "content": "Explain"}])
    with pytest.raises(HTTPException) as exc:
        asyncio.run(consumer_api.complete(body, request, (SimpleNamespace(id=uuid4()), None)))
    assert exc.value.status_code == 409
    assert state["admitted"] == state["released"] == 1 and state["closed"]


def test_upstream_multiple_choices_are_not_coalesced_into_one_advisory(consumer_fixture):
    from app.inference import OpenAIModelClient

    app, state = consumer_fixture

    def handle(_):
        item = {"delta": {"content": "ambiguous-private-text"}, "finish_reason": "stop"}
        return httpx.Response(
            200, text="data: " + json.dumps({"choices": [item, item]}) + "\n\ndata: [DONE]\n\n"
        )

    app.state.model_client = OpenAIModelClient(
        Settings(model_base_url="https://provider.example.test/v1"), httpx.MockTransport(handle)
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/inference/completions",
            json={"messages": [{"role": "user", "content": "Explain"}]},
        )
    assert response.status_code == 503 and "ambiguous-private-text" not in response.text
    assert state["admitted"] == state["released"] == 1
