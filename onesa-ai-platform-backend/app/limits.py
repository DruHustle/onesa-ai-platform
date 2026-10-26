"""Bound total request size before JSON/multipart parsing."""

import asyncio
import time

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class BodyLimit:
    def __init__(self, app: ASGIApp, maximum: int = 6 * 1024 * 1024, deadline: float = 30):
        self.app, self.maximum, self.deadline = app, maximum, deadline

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] in {"GET", "HEAD", "OPTIONS"}:
            await self.app(scope, receive, send)
            return
        parts: list[bytes] = []
        bounded = {
            "/api/v1/industrial/imports/preview": 512 * 1024,
            # The validated bundle still has its own 512 KiB ceiling. Leave a
            # small bounded envelope for the investigation UUID/selection.
            "/api/v1/industrial/investigations": 516 * 1024,
        }
        maximum = min(self.maximum, bounded.get(scope.get("path", ""), self.maximum))
        if scope.get("path", "").startswith("/api/v1/cybersecurity/"):
            maximum = 2 * 1048576 if scope["path"].endswith("/reports") else 1048576
        size = 0
        expires = time.monotonic() + self.deadline
        while True:
            try:
                async with asyncio.timeout(max(0, expires - time.monotonic())):
                    message = await receive()
            except TimeoutError:
                response = JSONResponse(
                    {"error": {"code": "request_timeout", "message": "Request body timed out"}},
                    status_code=408,
                )
                await response(scope, receive, send)
                return
            if message["type"] == "http.disconnect":
                return
            data = message.get("body", b"")
            size += len(data)
            if size > maximum:
                response = JSONResponse(
                    {
                        "error": {
                            "code": "request_too_large",
                            "message": "Request exceeds the supported body size",
                            "request_id": scope.get("state", {}).get("request_id"),
                        }
                    },
                    status_code=413,
                )
                await response(scope, receive, send)
                return
            parts.append(data)
            if not message.get("more_body", False):
                break
        delivered = False

        async def replay() -> Message:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": b"".join(parts), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)
