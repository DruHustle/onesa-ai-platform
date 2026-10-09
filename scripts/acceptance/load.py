"""Bounded synthetic authenticated workload; mock application capacity and real chat are distinct."""

import argparse
import asyncio
import json
import math
import platform
import secrets
import ssl
import subprocess
import time
from collections import defaultdict
from pathlib import Path

import httpx


def percentiles(values):
    ordered = sorted(values)
    return (
        {
            "p50_seconds": ordered[max(0, math.ceil(len(ordered) * 0.5) - 1)],
            "p95_seconds": ordered[max(0, math.ceil(len(ordered) * 0.95) - 1)],
        }
        if ordered
        else {}
    )


async def run(args):
    context = ssl.create_default_context(cafile=str(args.ca))
    samples = defaultdict(list)
    first_tokens, tokens_per_second, failures = [], [], []
    semaphore = asyncio.Semaphore(args.users)
    backend = None
    attempted = 0
    failed_requests = 0

    async def user(index):
        nonlocal backend, attempted, failed_requests
        async with (
            semaphore,
            httpx.AsyncClient(
                base_url=args.url,
                verify=context,
                headers={"Origin": args.url},
                timeout=90,
            ) as client,
        ):

            async def request(name, method, path, **kwargs):
                nonlocal attempted, failed_requests
                attempted += 1
                started = time.monotonic()
                response = await client.request(method, "/api/v1" + path, **kwargs)
                samples[name].append(time.monotonic() - started)
                if response.status_code >= 400:
                    failed_requests += 1
                response.raise_for_status()
                return response

            try:
                identity = secrets.token_hex(8)
                await request(
                    "registration",
                    "POST",
                    "/auth/register",
                    json={
                        "email": f"load-{identity}@example.com",
                        "password": secrets.token_urlsafe(24),
                        "display_name": "Synthetic load fixture",
                    },
                )
                client.headers["X-CSRF-Token"] = client.cookies["onesa_csrf"]
                model = (await request("models", "GET", "/models")).json()["items"][0]
                backend = model["backend"]
                if args.workload == "application" and backend != "mock":
                    raise ValueError(
                        "Application-capacity workload requires mock inference"
                    )
                for iteration in range(args.iterations):
                    identifier = (
                        await request(
                            "conversation_create",
                            "POST",
                            "/conversations",
                            json={"title": "Synthetic load fixture"},
                        )
                    ).json()["id"]
                    attempted += 1
                    started = time.monotonic()
                    first = None
                    completed = False
                    with_data = []
                    async with client.stream(
                        "POST",
                        "/api/v1/chat/completions",
                        json={
                            "conversation_id": identifier,
                            "content": "Explain private self-hosted AI in two short sentences.",
                            "stream": True,
                        },
                    ) as response:
                        if response.status_code >= 400:
                            failed_requests += 1
                        response.raise_for_status()
                        async for line in response.aiter_lines():
                            if line == "event: content_delta" and first is None:
                                first = time.monotonic() - started
                            if line == "event: message_end":
                                completed = True
                            if line == "event: error":
                                raise ValueError("Inference stream failed")
                            if line.startswith("data: "):
                                with_data.append(json.loads(line[6:]))
                    samples["stream_full"].append(time.monotonic() - started)
                    if not completed or first is None:
                        raise ValueError("Incomplete stream")
                    first_tokens.append(first)
                    usage = (
                        with_data[-1].get("metrics", {}).get("output_tokens_per_second")
                    )
                    if usage is not None:
                        tokens_per_second.append(usage)
                    history = (
                        await request(
                            "conversation_read", "GET", f"/conversations/{identifier}"
                        )
                    ).json()
                    if len(history["messages"]) != 2:
                        raise ValueError("Conversation persistence failed")
                    if args.workload == "application":
                        document = (
                            await request(
                                "knowledge_upload",
                                "POST",
                                "/knowledge/documents",
                                files={
                                    "file": (
                                        "synthetic.txt",
                                        f"Berlin acceptance fixture {identity} {iteration}".encode(),
                                        "text/plain",
                                    )
                                },
                            )
                        ).json()["id"]
                        search = (
                            await request(
                                "knowledge_search",
                                "POST",
                                "/knowledge/search",
                                json={
                                    "query": "Berlin acceptance",
                                    "document_ids": [document],
                                },
                            )
                        ).json()
                        if not search["sources"]:
                            raise ValueError("No owned retrieval")
                        agent = (
                            await request(
                                "agent_run",
                                "POST",
                                "/agents/runs",
                                json={
                                    "goal": "Count three words",
                                    "allowed_tools": ["text_stats"],
                                    "steps": [
                                        {
                                            "tool": "text_stats",
                                            "arguments": {"text": "Count three words"},
                                        }
                                    ],
                                },
                            )
                        ).json()
                        if agent["status"] != "completed":
                            raise ValueError("Agent failed")
                        trip = (
                            await request(
                                "travel_plan",
                                "POST",
                                "/travel/trips",
                                json={
                                    "destination": "Berlin",
                                    "duration": 1,
                                    "budget": 100,
                                },
                            )
                        ).json()["id"]
                        await request("travel_read", "GET", f"/travel/trips/{trip}")
                    await request("history_list", "GET", "/conversations")
            except (
                httpx.HTTPError,
                ValueError,
                KeyError,
                IndexError,
                TypeError,
            ) as exc:
                # Class only: no credentials, document content or URLs from errors.
                failures.append({"user": index, "error": type(exc).__name__})

    resource_samples = []
    finished = asyncio.Event()

    async def resources():
        while not finished.is_set():
            result = await asyncio.to_thread(
                subprocess.run,
                [
                    "docker",
                    "stats",
                    "--no-stream",
                    "--format",
                    "{{json .}}",
                    "onesa-acceptance-005-api-1",
                    "onesa-acceptance-005-chat-1",
                    "onesa-acceptance-005-db-1",
                ],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            if result.returncode == 0:
                resource_samples.append(
                    {
                        "elapsed_seconds": time.monotonic() - started,
                        "containers": [
                            json.loads(line) for line in result.stdout.splitlines()
                        ],
                    }
                )
            await asyncio.sleep(0.25)

    started = time.monotonic()
    sampler = asyncio.create_task(resources()) if args.resources else None
    await asyncio.gather(*(user(index) for index in range(args.users)))
    finished.set()
    if sampler:
        await sampler
    total = sum(len(values) for values in samples.values())
    return {
        "percentile_method": "nearest rank; small samples do not establish population tails",
        "latency_samples_seconds": dict(samples),
        "first_text_samples_seconds": first_tokens,
        "resource_samples": resource_samples,
        "workload": args.workload,
        "backend": backend,
        "environment": {
            "client_system": platform.system(),
            "client_machine": platform.machine(),
            "url": args.url,
            "tls_ca_verified": True,
        },
        "concurrent_users": args.users,
        "iterations_per_user": args.iterations,
        "measured_requests": total,
        "attempted_requests": attempted,
        "http_error_rate": failed_requests / attempted if attempted else None,
        "wall_seconds": time.monotonic() - started,
        "failed_users": failures,
        "user_error_rate": len(failures) / args.users,
        "operations": {
            name: {"samples": len(values), **percentiles(values)}
            for name, values in samples.items()
        },
        "time_to_first_text": percentiles(first_tokens),
        "mean_reported_output_tokens_per_full_request_second": sum(tokens_per_second)
        / len(tokens_per_second)
        if tokens_per_second
        else None,
        "provisional_targets": {
            "mock_non_auth_p95_seconds": 2,
            "mock_first_text_p95_seconds": 2,
            "failed_user_rate": 0.01,
        },
        "customer_data_used": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="https://localhost:3443")
    parser.add_argument(
        "--ca", type=Path, default=Path("data/acceptance-005/staging-ca.crt")
    )
    parser.add_argument("--resources", action="store_true")
    parser.add_argument("--users", type=int, default=4)
    parser.add_argument("--iterations", type=int, default=2)
    parser.add_argument(
        "--workload", choices=["application", "inference"], default="application"
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if (
        not 1 <= args.users <= 16
        or not 1 <= args.iterations <= 10
        or args.url != "https://localhost:3443"
    ):
        raise SystemExit(
            "Use the explicitly isolated loopback TLS stack and bounded load"
        )
    report = asyncio.run(run(args))
    with args.output.open("x") as output:
        json.dump(report, output, indent=2)
        output.write("\n")
    print(
        json.dumps(
            {
                "users": args.users,
                "requests": report["measured_requests"],
                "error_rate": report["user_error_rate"],
            }
        )
    )
    raise SystemExit(bool(report["failed_users"]))
