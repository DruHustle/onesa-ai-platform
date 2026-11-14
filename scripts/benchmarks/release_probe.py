"""Bounded loopback-only synthetic workload. No production/load qualification claim."""

import argparse
import json
import math
import secrets
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit

import httpx


def run(url, users, rounds):
    target = urlsplit(url)
    if (
        target.scheme != "http"
        or target.hostname not in {"localhost", "127.0.0.1"}
        or target.username
        or target.password
        or target.path
    ):
        raise ValueError("Only an explicitly isolated loopback candidate is allowed")
    if not 1 <= users <= 4 or not 1 <= rounds <= 4:
        raise ValueError("Probe exceeds the approved local engineering bound")

    def user(_):
        samples = []
        with httpx.Client(base_url=url, headers={"Origin": url}, timeout=90) as client:
            response = client.post(
                "/api/v1/auth/register",
                json={
                    "email": f"probe-{secrets.token_hex(10)}@example.com",
                    "display_name": "Synthetic probe",
                    "password": secrets.token_urlsafe(24),
                },
            )
            response.raise_for_status()
            client.headers["X-CSRF-Token"] = client.cookies["onesa_csrf"]
            model = client.get("/api/v1/models/default").json()
            for _ in range(rounds):
                response = client.post("/api/v1/conversations", json={})
                response.raise_for_status()
                identifier = response.json()["id"]
                started = time.monotonic()
                response = client.post(
                    "/api/v1/chat/completions",
                    json={
                        "conversation_id": identifier,
                        "content": "Reply with one short sentence describing safe engineering.",
                        "stream": False,
                    },
                )
                samples.append(
                    {
                        "status": response.status_code,
                        "seconds": time.monotonic() - started,
                    }
                )
                if response.status_code == 200:
                    assert response.json()["content"]
            return samples, model.get("backend", "unavailable")

    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=users) as pool:
        results = list(pool.map(user, range(users)))
    samples = [s for group, _ in results for s in group]
    latency = sorted(s["seconds"] for s in samples)
    return {
        "environment": "isolated local synthetic; not hosted acceptance",
        "backend": sorted({b for _, b in results}),
        "users": users,
        "requests": len(samples),
        "errors": sum(s["status"] != 200 for s in samples),
        "p50_seconds": latency[math.ceil(len(latency) * 0.5) - 1],
        "p95_seconds": latency[math.ceil(len(latency) * 0.95) - 1],
        "elapsed_seconds": time.monotonic() - started,
        "samples": samples,
        "actual_token_throughput": None,
        "targets": "Provisional only; 0 request errors, <=30s model p95; no success threshold tuning",
        "capacity_qualified": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("--users", type=int, default=2)
    parser.add_argument("--rounds", type=int, default=2)
    args = parser.parse_args()
    result = run(args.url, args.users, args.rounds)
    print(json.dumps(result, indent=2))
    if result["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
