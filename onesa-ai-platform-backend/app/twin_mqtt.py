"""Read-only Smart Factory MQTT wire adapter. Operator config is never imported from AAS."""

import hashlib
import json
import math
import os
import signal
import stat
from datetime import UTC, datetime
from pathlib import Path
from threading import Event
from typing import Any
from urllib.parse import urlsplit

import httpx
import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
from pydantic import Field, model_validator

from app.schemas import Strict
from app.twin_schemas import Batch, Sample


class MqttConfig(Strict):
    broker: str
    port: int = Field(default=8883, ge=1, le=65535)
    tls: bool = True
    username_env: str = "ONESA_MQTT_USERNAME"
    password_env: str = "ONESA_MQTT_PASSWORD"
    ca_file: str | None = None
    client_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,60}$")
    topic: str = Field(pattern=r"^factory/[A-Za-z0-9_-]+/[A-Za-z0-9_-]+/[A-Za-z0-9_-]+/telemetry$")
    api_origin: str
    source_id: str = Field(pattern=r"^[a-f0-9-]{36}$")
    source_token_env: str = "ONESA_TWIN_SOURCE_TOKEN"
    mode: str = Field(pattern="^(live|simulated)$")
    # Wire metric -> reviewed platform tag and source unit. Engineering conversion
    # is performed by the authenticated platform, never guessed from an AAS label.
    metrics: dict[str, tuple[str, str]] = Field(min_length=1, max_length=6)

    @model_validator(mode="after")
    def destinations(self) -> "MqttConfig":
        parsed = urlsplit(self.api_origin)
        if (
            parsed.username
            or parsed.password
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
            or parsed.scheme not in {"http", "https"}
        ):
            raise ValueError("API destination must be an exact configured origin")
        local = {"127.0.0.1", "localhost", "::1"}
        if (parsed.scheme != "https" and parsed.hostname not in local) or (
            not self.tls and self.broker not in local
        ):
            raise ValueError("Remote API and MQTT destinations require verified TLS")
        if set(self.metrics) - {"temperature", "vibration", "pressure", "rpm", "power", "humidity"}:
            raise ValueError("Unsupported Smart Factory measurement")
        return self


def translate(config: MqttConfig, topic: str, payload: bytes) -> Batch:
    if topic != config.topic or len(payload) > 4096:
        raise ValueError("Unexpected or oversized MQTT telemetry")
    record = json.loads(payload)
    if not isinstance(record, dict) or record.get("deviceId") != topic.split("/")[3]:
        raise ValueError("MQTT device binding mismatch")
    timestamp = record.get("timestamp")
    if (
        isinstance(timestamp, bool)
        or not isinstance(timestamp, int)
        or not 0 < timestamp < 32503680000000
    ):
        raise ValueError("Smart Factory timestamp must be epoch milliseconds")
    observed = datetime.fromtimestamp(timestamp / 1000, UTC)
    status = record.get("sensorStatus")
    if status not in {None, "ok", "read_error"}:
        raise ValueError("Unsupported MQTT source quality")
    quality = {None: "unknown", "ok": "good", "read_error": "bad"}[status]
    samples = []
    for metric, (tag, unit) in config.metrics.items():
        value = record.get(metric)
        if value is None:
            continue
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            raise ValueError("Invalid MQTT measurement")
        identity = hashlib.sha256(topic.encode() + b"\n" + payload).hexdigest()
        samples.append(
            Sample(
                message_id=identity,
                tag=tag,
                value=value,
                unit=unit,
                observed_at=observed,
                quality=quality,
            )
        )
    return Batch.model_validate({"mode": config.mode, "samples": samples})


def serve(config: MqttConfig) -> None:
    token = os.environ.get(config.source_token_env, "")
    if len(token) < 40:
        raise ValueError(
            "A source-scoped credential must be supplied through the "
            "configured environment variable"
        )
    client = mqtt.Client(
        CallbackAPIVersion.VERSION2,
        client_id=config.client_id,
        clean_session=False,
        manual_ack=True,
    )
    if config.tls:
        client.tls_set(ca_certs=config.ca_file)
    username, password = os.environ.get(config.username_env), os.environ.get(config.password_env)
    if config.broker not in {"127.0.0.1", "localhost", "::1"} and (not username or not password):
        raise ValueError("Remote MQTT requires operator-managed credentials")
    if username:
        client.username_pw_set(username, password)
    client.reconnect_delay_set(min_delay=1, max_delay=30)
    stopped = Event()
    retry_requested = False
    with httpx.Client(timeout=5, follow_redirects=False) as http:

        def connected(
            current: Any, _userdata: Any, _flags: Any, code: Any, _properties: Any
        ) -> None:
            if code == 0:
                current.subscribe(config.topic, qos=1)

        def received(current: Any, _userdata: Any, message: Any) -> None:
            nonlocal retry_requested
            try:
                batch = translate(config, message.topic, message.payload)
                response = http.post(
                    config.api_origin.rstrip("/")
                    + f"/api/v1/twins/sources/{config.source_id}/readings",
                    headers={"X-Onesa-Source-Token": token},
                    json=batch.model_dump(mode="json"),
                )
                if response.status_code == 200:
                    current.ack(message.mid, message.qos)
                    print("MQTT telemetry accepted", flush=True)
                elif response.status_code in {408, 425, 429} or (
                    response.status_code == 409
                    and response.json().get("error", {}).get("code") == "reading_capacity"
                ):
                    retry_requested = True
                    current.disconnect()
                elif response.status_code < 500:
                    # Invalid/revoked input must not hammer the API or be relabeled successful.
                    print(
                        "MQTT telemetry rejected by platform; check scoped configuration",
                        flush=True,
                    )
                    current.ack(message.mid, message.qos)
                else:
                    retry_requested = True
                    current.disconnect()  # Broker retains unacknowledged QoS evidence.
            except (ValueError, json.JSONDecodeError):
                print("MQTT telemetry rejected by wire validation", flush=True)
                current.ack(message.mid, message.qos)
            except httpx.HTTPError:
                retry_requested = True
                current.disconnect()

        def subscribed(
            _client: Any, _userdata: Any, _mid: Any, codes: Any, _properties: Any
        ) -> None:
            if codes and all(code.value < 128 for code in codes):
                print("MQTT source subscribed", flush=True)

        client.on_subscribe = subscribed
        client.on_connect = connected
        client.on_message = received

        def stop(*_arguments: Any) -> None:
            stopped.set()
            client.disconnect()

        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        client.connect(config.broker, config.port, keepalive=30)
        backoff = 1
        while not stopped.is_set():
            client.loop_forever(retry_first_connection=False)
            if stopped.is_set() or not retry_requested:
                break
            if stopped.wait(backoff):
                break
            backoff = min(30, backoff * 2)
            retry_requested = False
            # Persistent MQTT session/QoS retains unacknowledged input. Retrying
            # cannot duplicate platform state because source/message/tag IDs are immutable.
            try:
                client.reconnect()
            except OSError:
                retry_requested = True
                continue


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Read-only MQTT to Digital Twins ingestion")
    parser.add_argument("config", type=Path)
    args = parser.parse_args()
    if args.config.is_symlink() or args.config.stat().st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise ValueError("Use a private mode-0600 operator configuration")
    serve(MqttConfig.model_validate_json(args.config.read_bytes()))


if __name__ == "__main__":
    main()
