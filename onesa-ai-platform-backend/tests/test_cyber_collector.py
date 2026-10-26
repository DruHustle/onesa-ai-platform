"""Durable delivery failure/restart checks with an entirely synthetic transport."""

import json
import os
from pathlib import Path

import httpx
import pytest

from app.cyber_collector import drain
from tests.test_cybersecurity import event


@pytest.fixture
def outbox(tmp_path):
    os.chmod(tmp_path, 0o700)
    box = tmp_path / "outbox"
    box.mkdir(mode=0o700)
    token = tmp_path / "source.token"
    token.write_text("x" * 43)
    token.chmod(0o600)
    config = tmp_path / "collector.json"
    config.write_text(
        json.dumps(
            {
                "endpoint": "https://configured.example.com/api/v1/cybersecurity/ingest",
                "token_file": str(token),
                "outbox": str(box),
            }
        )
    )
    config.chmod(0o600)
    payload = box / "batch.json"
    payload.write_text(json.dumps({"events": [event()]}))
    payload.chmod(0o600)
    return config, box, payload


class Transport:
    def __init__(self, statuses):
        self.statuses = iter(statuses)
        self.requests = []

    def post(self, endpoint, *, content, headers):
        assert endpoint.startswith("https://configured.example.com/")
        assert headers["Authorization"] == "Bearer " + "x" * 43
        self.requests.append(content)
        status = next(self.statuses)
        if status == "outage":
            raise httpx.ConnectError("synthetic outage")
        return httpx.Response(
            status,
            json={
                "inserted": 1,
                "duplicates": 0,
                "event_ids": ["00000000-0000-4000-8000-000000000001"],
            },
        )


def test_transient_outage_remains_durable_then_restart_acknowledges(outbox):
    config, box, payload = outbox
    first = Transport(["outage", 503, 429])
    pauses = []
    result = drain(config, client=first, pause=pauses.append)
    assert result == {"accepted": 0, "rejected": 0, "pending": 1, "requests": 3}
    assert payload.exists() and pauses == [0.5, 1]
    second = Transport([200])
    result = drain(config, client=second)
    assert result["accepted"] == 1 and not payload.exists()
    assert len(list((box / "accepted").glob("*.json"))) == 1
    assert first.requests[0] == second.requests[0]


@pytest.mark.parametrize("status", [301, 302, 400, 401, 403, 409, 413, 422])
def test_permanent_receiver_rejection_is_not_retried(outbox, status):
    config, box, payload = outbox
    transport = Transport([status])
    result = drain(
        config, client=transport, pause=lambda _: pytest.fail("permanent rejection retried")
    )
    assert result["requests"] == 1 and result["rejected"] == 1 and not payload.exists()
    assert len(list((box / "rejected").glob("*.json"))) == 1
    assert drain(config, client=transport)["requests"] == 0


def test_malformed_payload_is_quarantined_without_transport(outbox):
    config, box, payload = outbox
    payload.write_text('{"events":[{"sourceId":"other-owner"}]}')
    result = drain(config, client=Transport([]))
    assert result["requests"] == 0 and result["rejected"] == 1


@pytest.mark.parametrize("mutation", ["http", "url-token", "public-token", "symlink"])
def test_private_scope_tls_and_credential_custody_fail_closed(outbox, mutation):
    config, box, _ = outbox
    value = json.loads(config.read_text())
    if mutation == "http":
        value["endpoint"] = value["endpoint"].replace("https:", "http:")
    if mutation == "url-token":
        value["endpoint"] += "?token=not-allowed"
    if mutation == "public-token":
        Path(value["token_file"]).chmod(0o644)
    if mutation == "symlink":
        symlink = box.parent / "link.token"
        symlink.symlink_to(value["token_file"])
        value["token_file"] = str(symlink)
    config.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        drain(config, client=Transport([]))


def test_interrupted_after_receiver_acceptance_retries_identical_evidence(outbox, monkeypatch):
    from app import cyber_collector

    config, _, payload = outbox
    original = payload.read_bytes()
    replace = cyber_collector.os.replace

    def interrupted(*_args):
        raise OSError("synthetic interrupted archive")

    monkeypatch.setattr(cyber_collector.os, "replace", interrupted)
    with pytest.raises(OSError):
        drain(config, client=Transport([200]))
    assert payload.read_bytes() == original
    monkeypatch.setattr(cyber_collector.os, "replace", replace)
    # Receiver's own unique source/event IDs make this redelivery idempotent.
    assert drain(config, client=Transport([200]))["accepted"] == 1


@pytest.mark.parametrize(
    "receipt",
    [
        {"inserted": 0, "duplicates": 0, "event_ids": []},
        {"inserted": -1, "duplicates": 2, "event_ids": []},
        {"inserted": True, "duplicates": 0, "event_ids": []},
        {"inserted": 1, "duplicates": 0, "event_ids": []},
        {"inserted": 1, "duplicates": 0, "event_ids": ["not-a-receiver-uuid"]},
        {"inserted": 1, "duplicates": 0, "event_ids": [{}]},
        {"inserted": 0, "duplicates": 2, "event_ids": []},
    ],
)
def test_incomplete_success_acknowledgement_never_discards_pending_evidence(outbox, receipt):
    config, box, payload = outbox
    original = payload.read_bytes()
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=receipt))
    ) as client:
        result = drain(config, client=client, pause=lambda _: None)
    assert result == {"accepted": 0, "rejected": 0, "pending": 1, "requests": 3}
    assert payload.read_bytes() == original
    assert not list((box / "accepted").iterdir())


def test_complete_idempotent_acknowledgement_archives_the_exact_pending_batch(outbox):
    config, box, payload = outbox
    original = payload.read_bytes()
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json={"inserted": 0, "duplicates": 1, "event_ids": []})
        )
    ) as client:
        result = drain(config, client=client)
    assert result == {"accepted": 1, "rejected": 0, "pending": 0, "requests": 1}
    assert not payload.exists()
    assert next((box / "accepted").iterdir()).read_bytes() == original
