"""Rehearse session/history recovery on the explicitly isolated split deployment."""

import os
import secrets
import subprocess
import sys
import time

import httpx

url = "http://localhost:3121"
with httpx.Client(base_url=url, headers={"Origin": url}, timeout=15) as client:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": f"split-restart-{secrets.token_hex(8)}@example.com",
            "password": secrets.token_urlsafe(24),
            "display_name": "Restart fixture",
        },
    )
    response.raise_for_status()
    user = response.json()["id"]
    client.headers["X-CSRF-Token"] = client.cookies["onesa_csrf"]
    response = client.post(
        "/api/v1/conversations", json={"title": "Split restart fixture"}
    )
    response.raise_for_status()
    identifier = response.json()["id"]
    response = client.post(
        "/api/v1/chat/completions",
        json={
            "conversation_id": identifier,
            "content": "Persist this synthetic fixture",
            "stream": True,
        },
    )
    response.raise_for_status()
    assert (
        "event: content_delta" in response.text
        and "event: message_end" in response.text
    )
    before = client.get(f"/api/v1/conversations/{identifier}").json()
    started = time.monotonic()
    subprocess.run(
        [
            "docker",
            "compose",
            "-p",
            "onesa-platform-split",
            "-f",
            "compose.yaml",
            "-f",
            "compose.staging.yaml",
            "restart",
            "api",
            "chat",
            "proxy",
        ],
        check=True,
        capture_output=True,
    )
    for _ in range(60):
        try:
            if client.get("/ready").status_code == 200:
                break
        except httpx.HTTPError:
            pass
        time.sleep(1)
    else:
        raise SystemExit("Readiness did not recover after restart")
    assert client.get("/api/v1/auth/me").json()["id"] == user
    assert client.get(f"/api/v1/conversations/{identifier}").json() == before
    assert client.get("/metrics").status_code == 404
    assert client.get("/api/metrics").status_code == 404
    print(
        f"Session and streamed history preserved after service restart; ready in {time.monotonic() - started:.2f}s"
    )

    if "--rollback" in sys.argv:
        compose = [
            "docker",
            "compose",
            "-p",
            "onesa-platform-split",
            "-f",
            "compose.yaml",
            "-f",
            "compose.staging.yaml",
        ]
        environment = {
            **os.environ,
            "ONESA_MODEL_BACKEND": "mock",
            "ONESA_PUBLIC_ORIGIN": url,
        }
        try:
            subprocess.run(
                compose
                + [
                    "-f",
                    "infra/deployment/rollback.yaml",
                    "up",
                    "--no-build",
                    "--wait",
                    "--wait-timeout",
                    "180",
                ],
                env=environment,
                check=True,
                capture_output=True,
            )
            assert client.get("/api/v1/auth/me").json()["id"] == user
            assert client.get(f"/api/v1/conversations/{identifier}").json() == before
            print(
                "Baseline-image rollback preserved the existing session and full conversation"
            )
        finally:
            subprocess.run(
                compose + ["up", "--no-build", "--wait", "--wait-timeout", "180"],
                env=environment,
                check=True,
                capture_output=True,
            )
        assert client.get("/api/v1/auth/me").json()["id"] == user
        assert client.get(f"/api/v1/conversations/{identifier}").json() == before
        print(
            "Forward recovery to split images preserved the same session and conversation"
        )
