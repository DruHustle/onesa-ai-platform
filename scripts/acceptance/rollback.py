"""Rehearse rollback with preserved main images in staging only, keeping the current database."""

import json
import secrets
import ssl
import subprocess
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / "data/acceptance-005"
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
]


def command(arguments):
    return subprocess.run(
        arguments, check=True, text=True, capture_output=True
    ).stdout.strip()


images = {}
for service in ["api", "chat"]:
    identifier = command(
        ["docker", "inspect", "--format", "{{.Image}}", f"onesa-platform-{service}-1"]
    )
    tag = f"onesa-{service}:pre-acceptance-005"
    command(["docker", "tag", identifier, tag])
    images[service] = {"image": tag, "id": identifier}
rollback = STATE / "rollback.yaml"
rollback.write_text(
    "services:\n"
    + "".join(
        f"  {name}:\n    image: {item['image']}\n    pull_policy: never\n"
        for name, item in images.items()
    )
)
context = ssl.create_default_context(cafile=str(STATE / "staging-ca.crt"))
with httpx.Client(
    base_url="https://localhost:3443",
    verify=context,
    headers={"Origin": "https://localhost:3443"},
    timeout=30,
) as client:
    client.post(
        "/api/v1/auth/register",
        json={
            "email": f"rollback-{secrets.token_hex(8)}@example.com",
            "password": secrets.token_urlsafe(24),
            "display_name": "Rollback fixture",
        },
    ).raise_for_status()
    client.headers["X-CSRF-Token"] = client.cookies["onesa_csrf"]
    conversation = client.post(
        "/api/v1/conversations", json={"title": "Rollback retained"}
    ).json()["id"]
    with client.stream(
        "POST",
        "/api/v1/chat/completions",
        json={
            "conversation_id": conversation,
            "content": "Synthetic retained record",
            "stream": True,
        },
    ) as response:
        response.raise_for_status()
        assert any(line == "event: message_end" for line in response.iter_lines())
    document = client.post(
        "/api/v1/knowledge/documents",
        files={"file": ("rollback.txt", b"Synthetic retained knowledge", "text/plain")},
    ).json()["id"]
    agent = client.post(
        "/api/v1/agents/runs",
        json={
            "goal": "Count words",
            "allowed_tools": ["text_stats"],
            "steps": [{"tool": "text_stats", "arguments": {"text": "Count words"}}],
        },
    ).json()["id"]
    trip = client.post(
        "/api/v1/travel/trips",
        json={"destination": "Berlin", "duration": 1, "budget": 100},
    ).json()["id"]
    paths = [
        "/auth/me",
        f"/conversations/{conversation}",
        f"/knowledge/documents/{document}",
        f"/agents/runs/{agent}",
        f"/travel/trips/{trip}",
    ]

    def snapshot():
        result = []
        for path in paths:
            response = client.get("/api/v1" + path)
            response.raise_for_status()
            result.append(response.json())
        return result

    before = snapshot()
    started = time.monotonic()
    try:
        command(
            COMPOSE
            + [
                "-f",
                str(rollback),
                "up",
                "--no-build",
                "--no-deps",
                "-d",
                "--wait",
                "--wait-timeout",
                "180",
                "api",
                "chat",
            ]
        )
        assert snapshot() == before, "Rollback changed persisted records/session"
        elapsed = time.monotonic() - started
    finally:
        command(
            COMPOSE
            + [
                "up",
                "--no-build",
                "--no-deps",
                "-d",
                "--wait",
                "--wait-timeout",
                "180",
                "api",
                "chat",
            ]
        )
    assert snapshot() == before, "Forward recovery changed persisted records/session"
(STATE / "rollback.json").write_text(
    json.dumps(
        {
            "environment": "isolated TLS staging",
            "prior_images": images,
            "rollback_seconds": elapsed,
            "same_session_retained": True,
            "five_resource_reads_identical": True,
            "forward_recovery_passed": True,
            "schema_changed": False,
            "production_rollback_tested": False,
        },
        indent=2,
    )
    + "\n"
)
print(
    "Prior images and forward recovery preserved the same session and all five resource reads"
)
