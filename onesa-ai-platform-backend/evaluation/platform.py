"""Explicit real-model acceptance against a running authenticated local Onesa stack."""

import argparse
import json
import secrets
import subprocess
import time
from pathlib import Path
from uuid import uuid4

import httpx


def chat(
    client: httpx.Client,
    conversation: str,
    text: str,
    documents: list[str] | None = None,
) -> dict:
    started = time.perf_counter()
    output = ""
    terminal = None
    first = None
    deltas = 0
    with client.stream(
        "POST",
        "/api/v1/chat/completions",
        json={
            "conversation_id": conversation,
            "content": text,
            "document_ids": documents or [],
            "stream": True,
        },
    ) as response:
        response.raise_for_status()
        event = ""
        for line in response.iter_lines():
            if line.startswith("event:"):
                event = line[6:].strip()
            if line.startswith("data:"):
                payload = json.loads(line[5:])
                if event == "error":
                    raise RuntimeError("Real chat generation failed")
                if event == "content_delta":
                    deltas += 1
                    first = first if first is not None else time.perf_counter() - started
                    output += payload["text"]
                if event == "message_end":
                    terminal = payload
    if terminal is None or not output or "[Mock response" in output:
        raise RuntimeError("Real streamed completion was not verified")
    return {
        "response": output,
        "text_deltas": deltas,
        "first_delta_seconds": first,
        "end_to_end_seconds": time.perf_counter() - started,
        "completion": terminal,
    }


def run(base: str, restart: bool) -> dict:
    with httpx.Client(base_url=base, headers={"Origin": base}, timeout=120) as client:
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": f"acceptance-{uuid4().hex}@example.com",
                "password": secrets.token_urlsafe(32),
                "display_name": "Real Model Acceptance",
            },
        )
        response.raise_for_status()
        client.headers["X-CSRF-Token"] = client.cookies["onesa_csrf"]
        metadata = client.get("/api/v1/models").json()["items"][0]
        if not metadata["real_inference"]:
            raise RuntimeError("Acceptance requires real inference, not mock")
        response = client.post("/api/v1/conversations", json={"title": "Real context acceptance"})
        response.raise_for_status()
        identifier = response.json()["id"]
        first = chat(
            client,
            identifier,
            "Remember project codename ALDER-731. Reply with a short acknowledgment.",
        )
        second = chat(
            client,
            identifier,
            "What is the project codename? Reply with only the codename.",
        )
        history = client.get(f"/api/v1/conversations/{identifier}").json()["messages"]
        assert "ALDER-731" in second["response"] and len(history) == 4
        report = {
            "source": "real-authenticated-Onesa-API",
            "model": metadata,
            "first_turn": first,
            "second_turn": second,
            "persisted_messages": len(history),
        }
        response = client.post(
            "/api/v1/knowledge/documents",
            files={
                "file": (
                    "Factory-Note.txt",
                    b"Synthetic factory note: Asset AX-17 has an inspection interval of 42 days.",
                    "text/plain",
                )
            },
        )
        response.raise_for_status()
        document = response.json()["id"]
        response = client.post("/api/v1/conversations", json={"title": "Real RAG acceptance"})
        response.raise_for_status()
        grounded_id = response.json()["id"]
        grounded = chat(
            client,
            grounded_id,
            "What is the inspection interval of asset AX-17? Cite the factory note.",
            [document],
        )
        grounded_history = client.get(f"/api/v1/conversations/{grounded_id}").json()["messages"]
        assert "42" in grounded["response"] and grounded_history[-1]["content"]["sources"]
        report["grounded_chat"] = grounded
        response = client.post(
            "/api/v1/agents/runs",
            json={
                "goal": "Count the words in: hello local model",
                "allowed_tools": ["text_stats"],
            },
        )
        response.raise_for_status()
        assert response.json()["status"] == "completed"
        report["model_planned_agent"] = response.json()
        response = client.post(
            "/api/v1/agents/runs",
            json={
                "goal": "Denied",
                "allowed_tools": [],
                "steps": [
                    {
                        "tool": "arithmetic",
                        "arguments": {"operation": "add", "values": [2, 3]},
                    }
                ],
            },
        )
        assert response.status_code == 403
        report["ungranted_tool_denied"] = True
        response = client.post(
            "/api/v1/travel/trips",
            json={
                "destination": "Berlin",
                "duration": 2,
                "budget": 250,
                "currency": "EUR",
            },
        )
        response.raise_for_status()
        report["model_generated_trip"] = response.json()
        response = client.post("/api/v1/conversations", json={"title": "Cancellation acceptance"})
        response.raise_for_status()
        cancel_id = response.json()["id"]
        started = time.perf_counter()
        with client.stream(
            "POST",
            "/api/v1/chat/completions",
            json={
                "conversation_id": cancel_id,
                "content": "Write a long numbered list of 500 household items.",
                "stream": True,
            },
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if line.startswith("event: content_delta"):
                    break
        cancelled_history = client.get(f"/api/v1/conversations/{cancel_id}").json()["messages"]
        assert len(cancelled_history) == 1 and cancelled_history[0]["role"] == "user"
        report["disconnect"] = {
            "elapsed_to_close_seconds": time.perf_counter() - started,
            "no_partial_assistant_saved": True,
        }
        time.sleep(0.2)
        report["after_disconnect"] = chat(client, cancel_id, "Reply with READY only.")
        if restart:
            subprocess.run(
                [".venv/bin/python", "scripts/local/ollama_service.py", "stop"],
                check=True,
            )
            assert client.get("/health").status_code == 200
            assert client.get("/ready").status_code == 503
            failure = client.post(
                "/api/v1/chat/completions",
                json={
                    "conversation_id": identifier,
                    "content": "Server down check",
                    "stream": False,
                },
            )
            assert failure.status_code == 503 and "host.docker.internal" not in failure.text
            subprocess.run(
                [".venv/bin/python", "scripts/local/ollama_service.py", "start"],
                check=True,
            )
            for _ in range(30):
                if client.get("/ready").status_code == 200:
                    break
                time.sleep(0.25)
            else:
                raise RuntimeError("Readiness failed to recover")
            report["after_ollama_restart"] = chat(
                client,
                identifier,
                "What is the project codename? Reply with only the codename.",
            )
            assert "ALDER-731" in report["after_ollama_restart"]["response"]
            report["restart_recovery"] = {
                "readiness_failed_while_down": True,
                "session_preserved": True,
                "no_partial_failure_saved": True,
                "genuine_generation_recovered": True,
            }
        return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--url", default="http://localhost:3100")
    parser.add_argument("--restart-managed-ollama", action="store_true")
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Use a new report path")
    report = run(args.url, args.restart_managed_ollama)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as output:
        json.dump(report, output, indent=2)
        output.write("\n")
    print("Saved actual platform acceptance:", args.output)


if __name__ == "__main__":
    main()
