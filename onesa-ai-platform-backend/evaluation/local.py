"""Bounded, repeatable inference probes. Mechanical checks require human review."""

import argparse
import asyncio
import hashlib
import json
import platform
import statistics
import subprocess
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv

from app.config import Settings
from app.inference import (
    GenerationStats,
    ModelMessage,
    build_model_client,
    observe_generation,
)


def hardware() -> dict:
    result = {"os": platform.platform(), "architecture": platform.machine()}
    if platform.system() == "Darwin":
        for key, field in [
            ("hw.memsize", "memory_bytes"),
            ("machdep.cpu.brand_string", "chip"),
        ]:
            command = subprocess.run(
                ["sysctl", "-n", key], capture_output=True, text=True, check=False
            )
            result[field] = command.stdout.strip() or None
    return result


def runtime(config: Settings) -> dict:
    result = {
        "backend": config.model_backend,
        "model": config.model_name,
        "configured_revision": config.model_revision,
        "context_tokens": config.model_context_length,
        "configured_quantization": config.model_quantization,
        "modalities": config.model_modalities,
    }
    if config.model_backend == "ollama":
        base = config.model_base_url.rstrip("/").removesuffix("/v1")
        try:
            with httpx.Client(base_url=base, timeout=5) as client:
                result["server_version"] = client.get("/api/version").json()["version"]
                show = client.post("/api/show", json={"model": config.model_name})
                show.raise_for_status()
                result["model_details"] = show.json().get("details")
                result["capabilities"] = show.json().get("capabilities")
                tags = client.get("/api/tags").json()["models"]
                result["installed_artifact"] = next(
                    (row for row in tags if row["name"] == config.model_name), None
                )
                result["resident_models"] = client.get("/api/ps").json()["models"]
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            result["runtime_observation_error"] = "Runtime metadata unavailable"
    return result


async def measure(config: Settings, messages: list[dict]) -> dict:
    stats = GenerationStats()
    started = time.perf_counter()
    text = ""
    try:
        with observe_generation(stats):
            async with asyncio.timeout(config.generation_timeout):
                async for part in build_model_client(config).stream(
                    [ModelMessage(**m) for m in messages]
                ):
                    if part and stats.first_token_seconds is None:
                        stats.first_token_seconds = time.perf_counter() - started
                    text += part
                    if len(text) > 128000:
                        raise ValueError("Output exceeds limit")
        success = bool(text)
        error = None if success else "empty_response"
    except (
        httpx.HTTPError,
        ValueError,
        KeyError,
        TypeError,
        TimeoutError,
        RuntimeError,
    ) as exc:
        success, error = False, type(exc).__name__
    stats.total_seconds = time.perf_counter() - started
    return {
        "success": success,
        "error_type": error,
        "response": text,
        "prompt_characters": sum(len(m["content"]) for m in messages),
        **asdict(stats),
        "output_tokens_per_second": stats.output_tokens / stats.total_seconds
        if stats.output_tokens is not None and stats.total_seconds
        else None,
    }


async def cancellation(config: Settings) -> dict:
    first = asyncio.Event()

    async def consume() -> None:
        async for _ in build_model_client(config).stream(
            [
                ModelMessage(
                    role="user",
                    content="Write a long numbered list of 500 different ordinary household items.",
                )
            ]
        ):
            first.set()

    task = asyncio.create_task(consume())
    try:
        await asyncio.wait_for(first.wait(), timeout=config.generation_timeout)
        started = time.perf_counter()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        elapsed = time.perf_counter() - started
        followup = await measure(config, [{"role": "user", "content": "Reply with READY only."}])
        return {
            "client_cancel_seconds": elapsed,
            "followup_success": followup["success"],
            "followup_seconds": followup["total_seconds"],
            "server_compute_stop_verified": False,
        }
    except (
        httpx.HTTPError,
        ValueError,
        KeyError,
        TypeError,
        TimeoutError,
        RuntimeError,
    ) as exc:
        return {"error_type": type(exc).__name__, "server_compute_stop_verified": False}
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)


def check_response(case: dict, response: str) -> bool:
    kind = case["check"]
    if kind == "exact":
        return response.strip() == case["expected"]
    if kind == "contains":
        return all(term.casefold() in response.casefold() for term in case["terms"])
    if kind == "refusal":
        return any(
            term in response.casefold()
            for term in [
                "cannot",
                "can’t",
                "can't",
                "no access",
                "do not have access",
                "don't have access",
                "unable",
            ]
        )
    if kind == "not_contains":
        return not any(term.casefold() in response.casefold() for term in case["terms"])
    if kind == "json":
        try:
            return json.loads(response) == case["expected"]
        except ValueError:
            return False
    if kind == "tool":
        try:
            value = json.loads(response)
            return value == [
                {
                    "tool": "arithmetic",
                    "arguments": {"operation": "add", "values": [2, 3]},
                }
            ]
        except ValueError:
            return False
    raise ValueError("Unknown case check")


async def native_tool_probe(config: Settings) -> dict:
    if config.model_backend == "mock":
        return {"tested": False, "reason": "mock"}
    schema = {
        "type": "function",
        "function": {
            "name": "add",
            "description": "Add two numbers",
            "parameters": {
                "type": "object",
                "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
                "required": ["a", "b"],
            },
        },
    }
    try:
        async with httpx.AsyncClient(timeout=config.generation_timeout) as client:
            response = await client.post(
                config.model_base_url.rstrip("/") + "/chat/completions",
                headers={"Authorization": "Bearer " + config.model_api_key},
                json={
                    "model": config.model_name,
                    "messages": [{"role": "user", "content": "Use add to add 2 and 3."}],
                    "tools": [schema],
                    "stream": False,
                    "temperature": 0,
                    "max_tokens": 128,
                },
            )
            response.raise_for_status()
            calls = response.json()["choices"][0]["message"].get("tool_calls", [])
            valid = (
                len(calls) == 1
                and calls[0]["function"]["name"] == "add"
                and json.loads(calls[0]["function"]["arguments"]) == {"a": 2, "b": 3}
            )
            return {
                "tested": True,
                "mechanical_check_passed": valid,
                "calls": calls,
                "tools_executed": False,
                "human_review_required": True,
            }
    except (
        httpx.HTTPError,
        ValueError,
        KeyError,
        TypeError,
        TimeoutError,
        RuntimeError,
    ) as exc:
        return {
            "tested": True,
            "mechanical_check_passed": False,
            "error_type": type(exc).__name__,
        }


async def run(args: argparse.Namespace, config: Settings) -> dict:
    if config.model_backend == "mock":
        raise ValueError("Live reports require ollama/vllm; use HTTP mocks in automated tests")
    if not await build_model_client(config).healthy():
        raise ValueError("Selected inference model is not available")
    report = {
        "created_at": datetime.now(UTC).isoformat(),
        "runtime_before": runtime(config),
        "benchmark_client_hardware": hardware(),
        "source": "measured-real-inference",
        "settings": {
            "max_output_tokens": config.model_max_output_tokens,
            "temperature": config.model_temperature,
            "timeout_seconds": config.generation_timeout,
        },
        "human_review_required": True,
    }
    if args.command == "evaluate":
        contents = args.cases.read_bytes()
        cases = [json.loads(line) for line in contents.decode().splitlines() if line.strip()]
        if not 1 <= len(cases) <= 64 or len({case["id"] for case in cases}) != len(cases):
            raise ValueError("Require 1–64 cases with unique IDs")
        rows = []
        for case in cases:
            row = await measure(config, case["messages"])
            row.update(
                id=case["id"],
                category=case["category"],
                language=case["language"],
                mechanical_check_passed=row["success"] and check_response(case, row["response"]),
            )
            rows.append(row)
        report.update(
            cases_sha256=hashlib.sha256(contents).hexdigest(),
            results=rows,
            mechanical_passes=sum(row["mechanical_check_passed"] for row in rows),
            samples=len(rows),
            native_tool_calling=await native_tool_probe(config),
        )
    else:
        semaphore = asyncio.Semaphore(args.concurrency)

        async def request() -> dict:
            async with semaphore:
                return await measure(config, [{"role": "user", "content": args.prompt}])

        started = time.perf_counter()
        rows = await asyncio.gather(*(request() for _ in range(args.requests)))
        latencies = [row["total_seconds"] for row in rows]
        report.update(
            requests=args.requests,
            concurrency=args.concurrency,
            results=rows,
            success_rate=sum(row["success"] for row in rows) / len(rows),
            error_rate=sum(not row["success"] for row in rows) / len(rows),
            mean_latency_seconds=statistics.mean(latencies),
            wall_seconds=time.perf_counter() - started,
            cancellation=await cancellation(config),
        )
    report["runtime_after"] = runtime(config)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["benchmark", "evaluate"])
    parser.add_argument("output", type=Path)
    parser.add_argument("--cases", type=Path, default=Path(__file__).with_name("cases.jsonl"))
    parser.add_argument("--base-url")
    parser.add_argument("--model")
    parser.add_argument("--requests", type=int, default=4)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--max-tokens", type=int, default=128)
    parser.add_argument(
        "--prompt", default="Explain private self-hosted AI in one short paragraph."
    )
    args = parser.parse_args()
    if args.output.exists() or not 1 <= args.requests <= 64 or not 1 <= args.concurrency <= 8:
        raise SystemExit("Use a new output path, 1–64 requests and 1–8 concurrency")
    load_dotenv(".env", override=False)
    overrides = {"model_max_output_tokens": args.max_tokens, "model_temperature": 0}
    if args.base_url:
        overrides["model_base_url"] = args.base_url
    if args.model:
        overrides["model_name"] = args.model
        overrides["model_revision"] = None
        overrides["model_quantization"] = None
    config = Settings(**overrides)
    report = asyncio.run(run(args, config))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as output:
        json.dump(report, output, indent=2, ensure_ascii=False)
        output.write("\n")
    print("Saved measured report:", args.output)


if __name__ == "__main__":
    main()
