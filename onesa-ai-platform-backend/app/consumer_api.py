"""Opt-in, stateless text inference for independently integrated consumers."""

import asyncio
import time
from contextlib import suppress
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import Field, model_validator
from starlette.concurrency import run_in_threadpool

from app import capacity
from app.auth import Auth
from app.consumer import CONTRACT_VERSION, MAX_INPUT_CHARS, MAX_OUTPUT_CHARS
from app.errors import fail
from app.inference import (
    GenerationStats,
    InferenceError,
    ModelMessage,
    model_metadata,
    observe_generation,
)
from app.responses import ModelOut
from app.schemas import Strict

router = APIRouter(prefix="/api/v1/inference", tags=["consumer inference"])


class ConsumerMessage(Strict):
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1, max_length=MAX_INPUT_CHARS)


class ConsumerRequest(Strict):
    messages: list[ConsumerMessage] = Field(min_length=1, max_length=32)
    model_id: Literal["default"] = "default"

    @model_validator(mode="after")
    def bounded_history(self) -> "ConsumerRequest":
        if (
            self.messages[-1].role != "user"
            or sum(len(m.content) for m in self.messages) > MAX_INPUT_CHARS
        ):
            raise ValueError("Bounded history must end in a user message")
        for message in self.messages:
            if not message.content.strip():
                raise ValueError("Messages must contain text")
            message.content.encode("utf-8")
        return self


class ConsumerUsage(Strict):
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)


class ConsumerCompletion(Strict):
    contract_version: Literal["onesa-inference-v1"]
    outcome: Literal["completed"]
    text: str = Field(min_length=1, max_length=MAX_OUTPUT_CHARS)
    model: ModelOut
    request_id: UUID
    usage: ConsumerUsage


@router.post("/completions", response_model=ConsumerCompletion)
async def complete(body: ConsumerRequest, request: Request, auth: Auth) -> dict[str, Any]:
    if not request.app.state.settings.consumer_inference_enabled:
        fail(404, "not_found", "Consumer inference is not enabled")
    # The existing admission rechecks identity/CSRF, invitation and shared budgets.
    lease = await run_in_threadpool(capacity.begin, request)
    task: asyncio.Task[str] | None = None
    stats = GenerationStats()

    async def collect() -> str:
        parts = []
        size = 0
        iterator = request.app.state.model_client.stream(
            [ModelMessage(role=m.role, content=m.content) for m in body.messages]
        )
        try:
            with observe_generation(stats):
                async for part in iterator:
                    if not isinstance(part, str):
                        raise InferenceError()
                    size += len(part)
                    if size > MAX_OUTPUT_CHARS:
                        raise InferenceError()
                    parts.append(part)
        finally:
            close = getattr(iterator, "aclose", None)
            if close is not None:
                await close()
        text = "".join(parts)
        if not text.strip() or stats.finish_reason not in {None, "stop"}:
            raise InferenceError()
        text.encode("utf-8")
        return text

    try:
        async with asyncio.timeout(request.app.state.settings.generation_timeout):
            task = asyncio.create_task(collect())
            checked = 0.0
            while True:
                done, _ = await asyncio.wait({task}, timeout=0.25)
                if await request.is_disconnected():
                    fail(409, "generation_cancelled", "Consumer disconnected")
                if done or time.monotonic() - checked >= 1:
                    if not await run_in_threadpool(capacity.active, request, lease):
                        fail(401, "unauthorized", "Request authority expired")
                    checked = time.monotonic()
                if done:
                    return {
                        "contract_version": CONTRACT_VERSION,
                        "outcome": "completed",
                        "text": task.result(),
                        "model": model_metadata(request.app.state.settings),
                        "request_id": request.state.request_id,
                        "usage": {
                            "prompt_tokens": stats.input_tokens,
                            "completion_tokens": stats.output_tokens,
                        },
                    }
    except HTTPException:
        raise
    except Exception:
        fail(503, "inference_unavailable", "Unable to complete consumer inference")
    finally:
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await task
        await run_in_threadpool(capacity.end, request, lease)
