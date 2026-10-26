"""The optional adapter validates its own wire contract without a peer checkout."""

import json

import pytest

from app.twin_mqtt import MqttConfig, translate


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
