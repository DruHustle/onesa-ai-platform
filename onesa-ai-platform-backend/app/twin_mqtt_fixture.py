"""Finite actual MQTT fixture; credentials arrive on stdin, never in process arguments/logs."""

import json
import os
import selectors
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

from app.twin_mqtt import MqttConfig


def exercise(inputs: dict[str, Any]) -> dict[str, Any]:
    if urlsplit(inputs["api_origin"]).hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Synthetic MQTT fixture is loopback-only")
    port = int(inputs.get("broker_port", 18883))
    config = MqttConfig(
        broker="127.0.0.1",
        port=port,
        tls=False,
        client_id="onesa-twin-fixture-" + inputs["source_id"][:12],
        topic="factory/onesa-demo/pump-line/pump-01/telemetry",
        api_origin=inputs["api_origin"],
        source_id=inputs["source_id"],
        mode="simulated",
        metrics={"vibration": ("vibration", "mm/s")},
    )
    environment = {
        **os.environ,
        "ONESA_TWIN_SOURCE_TOKEN": inputs["source_token"],
        "ONESA_MQTT_USERNAME": "onesa-demo",
        "ONESA_MQTT_PASSWORD": "mqtt-fixture-only",
    }
    with tempfile.TemporaryDirectory(prefix="onesa-twin-mqtt-") as directory:
        path = Path(directory) / "adapter.json"
        path.write_text(config.model_dump_json())
        path.chmod(0o600)
        adapter = subprocess.Popen(
            [sys.executable, "-m", "app.twin_mqtt", str(path)],
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=0,
        )
        publisher = mqtt.Client(CallbackAPIVersion.VERSION2)
        publisher.username_pw_set("onesa-demo", "mqtt-fixture-only")
        try:
            publisher.connect("127.0.0.1", port)
            publisher.loop_start()
            assert adapter.stdout is not None
            selector = selectors.DefaultSelector()
            selector.register(adapter.stdout, selectors.EVENT_READ)
            deadline = time.monotonic() + 10
            subscribed = False
            while time.monotonic() < deadline:
                if (
                    selector.select(timeout=0.5)
                    and adapter.stdout.readline() == b"MQTT source subscribed\n"
                ):
                    subscribed = True
                    break
            if not subscribed:
                raise ValueError("MQTT adapter did not receive broker SUBACK")
            epoch = int(time.time() * 1000)
            for index, value in enumerate((2, 6, 4.5, 3)):
                payload = {
                    "deviceId": "pump-01",
                    "timestamp": epoch - 4000 + index * 1000,
                    "vibration": value,
                    "sensorStatus": "ok",
                }
                result = publisher.publish(config.topic, json.dumps(payload), qos=1)
                result.wait_for_publish(timeout=3)
                if not result.is_published():
                    raise ValueError("MQTT publish not acknowledged")
            assert adapter.stdout is not None
            accepted = 0
            deadline = time.monotonic() + 15
            while accepted < 4 and time.monotonic() < deadline:
                if selector.select(timeout=0.5):
                    line = adapter.stdout.readline()
                    if line == b"MQTT telemetry accepted\n":
                        accepted += 1
                    elif not line:
                        break
            selector.close()
            if accepted != 4:
                raise ValueError(
                    "The real MQTT adapter did not receive four platform acceptance receipts"
                )
            return {
                "protocol": "MQTT 3.1.1",
                "published": 4,
                "platform_accepted": accepted,
                "data_mode": "simulated",
                "scenario": (
                    "normal, threshold crossing, hysteresis, recovery; "
                    "stop publishing to observe stale/disconnected"
                ),
            }
        finally:
            publisher.disconnect()
            publisher.loop_stop()
            adapter.terminate()
            try:
                adapter.wait(timeout=5)
            except subprocess.TimeoutExpired:
                adapter.kill()
                adapter.wait(timeout=2)


if __name__ == "__main__":
    print(json.dumps(exercise(json.loads(sys.stdin.read(16000)))))
