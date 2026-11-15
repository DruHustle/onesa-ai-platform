"""The optional adapter validates its own wire contract without a peer checkout."""

import json

import httpx
import pytest

from app.twin_mqtt import MqttConfig, retryable_platform_response, translate


@pytest.fixture
def config():
    return MqttConfig(
        broker="127.0.0.1",
        port=18883,
        tls=False,
        client_id="local-contract-test",
        topic="factory/demo/line/bearing/telemetry",
        api_origin="http://127.0.0.1:3100",
        source_id="00000000-0000-0000-0000-000000000001",
        mode="simulated",
        metrics={"vibration": ("vibration", "mm/s")},
    )


@pytest.mark.parametrize(
    "status,quality", [("ok", "good"), ("read_error", "bad"), (None, "unknown")]
)
def test_source_quality_is_explicit_and_missing_quality_is_unknown(config, status, quality):
    wire = {"deviceId": "bearing", "timestamp": 1792920000000, "vibration": 2}
    if status is not None:
        wire["sensorStatus"] = status
    data = json.dumps(wire).encode()
    first = translate(config, config.topic, data)
    assert first.samples[0].quality == quality
    assert translate(config, config.topic, data) == first
    assert first.mode == "simulated"


@pytest.mark.parametrize(
    "update",
    [
        {"sensorStatus": "unverified"},
        {"sensorStatus": []},
        {"sensorStatus": {}},
        {"sensorStatus": 0},
        {"deviceId": "another-device"},
        {"timestamp": True},
        {"vibration": True},
        {"vibration": float("nan")},
    ],
)
def test_wrong_binding_quality_and_invalid_measurements_are_rejected(config, update):
    wire = {"deviceId": "bearing", "timestamp": 1792920000000, "vibration": 2, **update}
    with pytest.raises(ValueError):
        translate(config, config.topic, json.dumps(wire).encode())
    with pytest.raises(ValueError):
        translate(config, "factory/demo/line/bearing/commands", json.dumps(wire).encode())


def test_remote_plaintext_configuration_is_rejected(config):
    with pytest.raises(ValueError):
        MqttConfig.model_validate({**config.model_dump(), "broker": "example.com"})
    with pytest.raises(ValueError):
        MqttConfig.model_validate({**config.model_dump(), "api_origin": "http://example.com"})


@pytest.mark.parametrize(
    ("status", "body", "retry"),
    [
        (200, b"", False),
        (401, b"", False),
        (408, b"", True),
        (425, b"", True),
        (429, b"", True),
        (503, b"", True),
        (409, b"not-json", True),
        (409, b"[]", True),
        (409, b'{"error": null}', True),
        (409, b'{"error": []}', True),
        (409, b'{"error": {"code": "reading_capacity"}}', True),
        (409, b'{"error": {"code": "unrecognized_conflict"}}', True),
        (409, b'{"error": {"code": "sample_identity_conflict"}}', False),
        (409, b'{"error": {"code": "sample_time_conflict"}}', False),
    ],
)
def test_unknown_platform_conflict_never_acks_mqtt_qos_evidence(status, body, retry):
    # An invalid 409 body used to raise JSONDecodeError in the callback,
    # which was treated as malformed source data and acknowledged (lost).
    response = httpx.Response(status, content=body)
    assert retryable_platform_response(response) is retry
