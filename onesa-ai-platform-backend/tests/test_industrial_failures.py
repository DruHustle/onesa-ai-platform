"""Bounded diagnosis without retaining model text or weakening source validation."""

import json
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app import industrial
from app.models import ModelLease, User, now
from tests.test_industrial import enable, explanation, new


class Response:
    def __init__(self, raw):
        self.raw, self.calls, self.closed = raw, 0, False

    async def stream(self, messages):
        self.calls += 1
        try:
            if self.raw is None:
                raise RuntimeError("private-provider-marker")
            yield self.raw
        finally:
            self.closed = True


def changed(field, value):
    result = explanation("demo-press-01-reference")
    result["hypotheses"][0][field] = value
    return json.dumps(result)


@pytest.mark.parametrize(
    "raw,code",
    [
        (" \t", "model_output_empty"),
        ("private-provider-marker", "model_output_json_invalid"),
        (json.dumps({"private-provider-marker": True}), "model_output_schema_invalid"),
        (changed("statement", "Pressure changed at 09:12"), "model_output_narrative_numbers"),
        (changed("human_review", "Check 3 samples"), "model_output_narrative_numbers"),
        (json.dumps(explanation("wrong-asset-reference")), "model_output_citation_invalid"),
        (changed("quote", "private-provider-marker"), "model_output_quote_invalid"),
        (
            json.dumps({**explanation("demo-press-01-reference"), "abstained": True}),
            "model_output_abstention_invalid",
        ),
        ("X" * 16001, "model_output_limit"),
        (None, "model_stream_unavailable"),
    ],
)
def test_generation_failure_category_preserves_facts_without_private_output(api, raw, code):
    enable(api)
    api.app.state.settings.model_backend = "vllm"
    provider = Response(raw)
    api.app.state.model_client = provider
    row = new(api)
    path = f"/api/v1/industrial/investigations/{row['id']}"
    result = api.post(path + "/generate", json={"expected_revision": 1})
    assert result.status_code == 200
    value = result.json()
    assert value["status"] == "failed" and value["payload"]["error"] == code
    assert value["payload"]["facts"] == row["payload"]["facts"]
    assert value["payload"]["explanation"] is None
    assert value["payload"]["generation"]["cost"] is None
    assert "private-provider-marker" not in json.dumps(value)
    assert provider.calls == 1 and provider.closed
    assert api.get(path).json()["status"] == "failed"


@pytest.mark.parametrize("failure", ["unavailable", "invalid"])
def test_retrieval_failure_finishes_the_investigation_instead_of_leaving_running(
    api, monkeypatch, failure
):
    enable(api)
    provider = Response("must not be requested")
    api.app.state.model_client = provider

    def rejected(*args, **kwargs):
        if failure == "unavailable":
            raise HTTPException(503, "private-provider-marker")
        raise ValueError("private-provider-marker")

    monkeypatch.setattr(industrial, "selected_references", rejected)
    row = new(api)
    result = api.post(
        f"/api/v1/industrial/investigations/{row['id']}/generate",
        json={"expected_revision": 1},
    )
    assert result.status_code == 200
    value = result.json()
    assert value["status"] == "failed"
    assert value["payload"]["error"] == "retrieval_" + failure
    assert value["payload"]["facts"] == row["payload"]["facts"]
    assert provider.calls == 0 and "private-provider-marker" not in json.dumps(value)


def test_valid_abstention_and_unknown_failure_categories_remain_explicit(api):
    enable(api)
    api.app.state.settings.model_backend = "vllm"
    api.app.state.model_client = Response(
        json.dumps({"hypotheses": [], "limitations": ["Cause not established"], "abstained": True})
    )
    row = new(api)
    result = api.post(
        f"/api/v1/industrial/investigations/{row['id']}/generate",
        json={"expected_revision": 1},
    ).json()
    assert result["status"] == "completed"
    assert result["payload"]["explanation"]["abstained"] is True
    assert industrial.GenerationFailure("private-provider-marker").code == (
        "generation_unavailable_or_invalid"
    )


@pytest.mark.parametrize("other_owner", [False, True])
def test_busy_capacity_never_calls_provider_or_changes_ready_facts(api, pg, other_owner):
    enable(api)
    api.app.state.settings.model_global_concurrency = 1
    api.app.state.settings.model_user_concurrency = 1
    api.app.state.settings.model_backend = "vllm"
    provider = Response(json.dumps(explanation("demo-press-01-reference")))
    api.app.state.model_client = provider
    row = new(api)
    user = UUID(api.get("/api/v1/auth/me").json()["id"])
    identifier = uuid4()
    with Session(pg) as db:
        if other_owner:
            user = uuid4()
            db.add(
                User(
                    id=user,
                    email=f"{user}@example.com",
                    password_hash="unused-offline-fixture",
                    display_name="Synthetic",
                    status="active",
                )
            )
            db.flush()
        db.add(ModelLease(id=identifier, user_id=user, expires_at=now() + timedelta(minutes=1)))
        db.commit()
    path = f"/api/v1/industrial/investigations/{row['id']}"
    denied = api.post(path + "/generate", json={"expected_revision": 1})
    assert denied.status_code == 429 and denied.json()["error"]["code"] == "model_capacity"
    assert provider.calls == 0
    saved = api.get(path).json()
    assert saved["status"] == "ready" and saved["revision"] == 1
    assert saved["payload"]["facts"] == row["payload"]["facts"]
    with Session(pg) as db:
        lease = db.get(ModelLease, identifier)
        assert lease.user_id == user
        db.delete(lease)  # Only the guarded local _test database's owned lease fixture.
        db.commit()
    result = api.post(path + "/generate", json={"expected_revision": 1})
    assert result.status_code == 200 and result.json()["status"] == "completed"
    assert result.json()["payload"]["facts"] == row["payload"]["facts"]
    assert provider.calls == 1 and provider.closed
