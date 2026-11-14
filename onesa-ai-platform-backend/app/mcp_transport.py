"""Bounded stdio framing with responsive, request-scoped cancellation.

Cancellation stops this bridge's outstanding HTTP work. It cannot undo a remote
operation that already committed, and never retries or replays that operation.
"""

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any, TextIO

MAX_LINE = 65536
MAX_IN_FLIGHT = 4
REQUEST_SECONDS = 25


def error(identifier: str | int | None, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": identifier, "error": {"code": code, "message": message}}


async def frame(reader: asyncio.StreamReader) -> tuple[bytes, bool]:
    """Drain an entire oversized line; never interpret its tail as a new request."""
    oversized = False
    while True:
        try:
            data = await reader.readuntil(b"\n")
        except asyncio.LimitOverrunError as refused:
            await reader.readexactly(refused.consumed)
            oversized = True
            continue
        except asyncio.IncompleteReadError as ended:
            data = ended.partial
        return data, oversized or len(data) > MAX_LINE


async def serve(
    dispatch: Callable[[Any], Awaitable[dict[str, Any] | None]],
    reader: asyncio.StreamReader,
    stdout: TextIO,
) -> None:
    active: dict[str | int, asyncio.Task[None]] = {}

    def emit(value: dict[str, Any] | None) -> None:
        if value is not None:
            stdout.write(json.dumps(value, ensure_ascii=True, allow_nan=False) + "\n")
            stdout.flush()

    def reject_constant(value: str) -> None:
        raise ValueError("Non-JSON number")

    async def execute(value: dict[str, Any]) -> None:
        try:
            async with asyncio.timeout(REQUEST_SECONDS):
                response = await dispatch(value)
        except TimeoutError:
            response = error(value["id"], -32603, "Request deadline exceeded")
        # CancelledError propagates: no response or remote replay follows cancellation.
        emit(response)

    def reap() -> None:
        for identifier, task in list(active.items()):
            if task.done():
                del active[identifier]
                if not task.cancelled():
                    task.result()

    try:
        while True:
            data, oversized = await frame(reader)
            reap()
            if oversized:
                emit(error(None, -32600, "Request exceeds the protocol limit"))
                continue
            if not data:
                break
            try:
                value = json.loads(data.decode("utf-8"), parse_constant=reject_constant)
            except (ValueError, RecursionError):
                emit(error(None, -32700, "Invalid JSON"))
                continue
            if (
                isinstance(value, dict)
                and value.get("jsonrpc") == "2.0"
                and "id" not in value
                and value.get("method") == "notifications/cancelled"
            ):
                params = value.get("params")
                if (
                    isinstance(params, dict)
                    and type(params.get("requestId")) in {str, int}
                    and set(params) <= {"requestId", "reason", "_meta"}
                    and isinstance(params.get("reason", ""), str)
                    and isinstance(params.get("_meta", {}), dict)
                ):
                    task = active.get(params["requestId"])
                    if task is not None:
                        task.cancel()
                # Unknown/completed IDs and malformed cancellations have no effect.
                continue
            if (
                isinstance(value, dict)
                and type(value.get("id")) in {str, int}
                and value["id"] in active
            ):
                emit(error(None, -32600, "Request identifier is already active"))
                continue
            if (
                not isinstance(value, dict)
                or type(value.get("id")) not in {str, int}
                or value.get("method") in {"initialize", "ping"}
            ):
                # Initialization is ordered and cannot be cancelled. Notifications
                # never invoke remote work; ping remains responsive under load.
                emit(await dispatch(value))
                continue
            if len(active) >= MAX_IN_FLIGHT:
                emit(error(value["id"], -32000, "Too many outstanding requests"))
                continue
            active[value["id"]] = asyncio.create_task(execute(value))
            # A buffered input stream must not starve the task it just submitted.
            await asyncio.sleep(0)
        if active:
            await asyncio.gather(*active.values(), return_exceptions=True)
            reap()
    finally:
        for task in active.values():
            task.cancel()
        await asyncio.gather(*active.values(), return_exceptions=True)
