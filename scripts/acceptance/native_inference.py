"""Real native Ollama disconnection, safe failure, local alert and stream recovery."""

import json
import secrets
import ssl
import subprocess
import time
from pathlib import Path

import httpx

STATE = Path("data/acceptance-005")
COMPOSE = [
    "docker",
    "compose",
    "--env-file",
    str(STATE / "staging.env"),
    "-p",
    "onesa-acceptance-005",
    "-f",
    "compose.yaml",
    "-f",
    "compose.production.yaml",
    "-f",
    "compose.acceptance.yaml",
    "-f",
    "compose.ollama.yaml",
]
TLS = ssl.create_default_context(cafile=str(STATE / "staging-ca.crt"))
TOKEN = (STATE / "secrets/operations_token").read_text().strip()
report = {
    "environment": "isolated TLS staging + native Apple Silicon Ollama",
    "daemon_stopped": False,
    "mock_used": False,
}


def deploy(failure=False):
    arguments = COMPOSE + (
        ["-f", "compose.acceptance.ollama-failure.yaml"] if failure else []
    )
    subprocess.run(
        arguments + ["up", "--no-build", "--no-deps", "-d", "api"],
        check=True,
        capture_output=True,
    )


def wait(predicate, label):
    deadline = time.monotonic() + 100
    while time.monotonic() < deadline:
        try:
            if predicate():
                return
        except httpx.HTTPError:
            pass
        time.sleep(2)
    raise RuntimeError("Timed out: " + label)


def alerts(state, since):
    response = httpx.get(
        "http://localhost:9905/status", headers={"Authorization": "Bearer " + TOKEN}
    )
    response.raise_for_status()
    return any(
        item["name"] == "OnesaDependenciesUnavailable"
        and item["status"] == state
        and item["received_at"] >= since
        for item in response.json()["alerts"]
    )


with httpx.Client(
    base_url="https://localhost:3443",
    verify=TLS,
    headers={"Origin": "https://localhost:3443"},
    timeout=90,
) as client:
    wait(lambda: client.get("/ready").status_code == 200, "native readiness")
    client.post(
        "/api/v1/auth/register",
        json={
            "email": f"native-{secrets.token_hex(8)}@example.com",
            "password": secrets.token_urlsafe(24),
            "display_name": "Native recovery fixture",
        },
    ).raise_for_status()
    client.headers["X-CSRF-Token"] = client.cookies["onesa_csrf"]
    model = client.get("/api/v1/models").json()["items"][0]
    assert model["backend"] == "ollama"
    report["model"] = model
    conversation = client.post(
        "/api/v1/conversations", json={"title": "Native disconnect recovery"}
    ).json()["id"]
    with client.stream(
        "POST",
        "/api/v1/chat/completions",
        json={
            "conversation_id": conversation,
            "content": "Write a long numbered list of 500 household items.",
            "stream": True,
        },
    ) as response:
        response.raise_for_status()
        assert any(line == "event: content_delta" for line in response.iter_lines())
    time.sleep(3)
    history = client.get(f"/api/v1/conversations/{conversation}").json()
    assert len(history["messages"]) == 1
    report["client_disconnect_discards_partial_assistant"] = True
    started = time.time()
    try:
        deploy(True)
        wait(lambda: client.get("/ready").status_code == 503, "model outage")
        with client.stream(
            "POST",
            "/api/v1/chat/completions",
            json={
                "conversation_id": conversation,
                "content": "Reply with READY only.",
                "stream": True,
            },
        ) as response:
            response.raise_for_status()
            lines = list(response.iter_lines())
            assert "event: error" in lines and "event: message_end" not in lines
            assert "host.docker.internal" not in "\n".join(lines)
        report["backend_outage_sanitized_stream_error"] = True
        wait(lambda: alerts("firing", started), "model alert delivery")
        report["model_failure_alert_delivered"] = True
    finally:
        deploy(False)
    wait(lambda: client.get("/ready").status_code == 200, "model recovery")
    wait(lambda: alerts("resolved", started), "model recovery alert delivery")
    report["model_recovery_alert_delivered"] = True
    with client.stream(
        "POST",
        "/api/v1/chat/completions",
        json={
            "conversation_id": conversation,
            "content": "Reply with READY only.",
            "stream": True,
        },
    ) as response:
        response.raise_for_status()
        assert "event: message_end" in list(response.iter_lines())
    report["real_generation_recovers"] = True
report["loaded_model_memory"] = httpx.get("http://127.0.0.1:11434/api/ps").json()
(STATE / "native-recovery.json").write_text(json.dumps(report, indent=2) + "\n")
print(
    "Native stream disconnect, backend outage, real alert delivery and generation recovery passed"
)
