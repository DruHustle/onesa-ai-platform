"""Provider-independent interface and explicitly deterministic test backend."""

import asyncio
import json
import re
from collections.abc import AsyncIterator, Iterator, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Literal, Protocol

import httpx
from pydantic import BaseModel, Field

from app.config import Settings

FAILURE_REASONS = frozenset(
    {
        "provider_stream_error",
        "invalid_stream_json",
        "invalid_stream_shape",
        "invalid_stream_delta",
        "stream_terminated_early",
        "empty_model_response",
        "response_size_limit",
        "generation_lease_lost",
    }
)


class InferenceError(ValueError):
    def __init__(
        self,
        code: str = "inference_unavailable",
        *,
        reason: str | None = None,
        provider_error_code: int | None = None,
    ):
        super().__init__("Inference temporarily unavailable")
        self.code = code
        # Provider messages may contain private request details. Expose only
        # fixed categories and a bounded numeric code, never their text.
        self.reason = reason if isinstance(reason, str) and reason in FAILURE_REASONS else None
        self.provider_error_code = (
            provider_error_code
            if type(provider_error_code) is int and 0 <= provider_error_code <= 999999
            else None
        )


@dataclass
class GenerationStats:
    retrieval_latency_ms: int | None = None
    generation_latency_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_seconds: float | None = None
    first_token_seconds: float | None = None


active_stats: ContextVar[GenerationStats | None] = ContextVar("generation_stats", default=None)


@contextmanager
def observe_generation(stats: GenerationStats) -> Iterator[None]:
    token = active_stats.set(stats)
    try:
        yield
    finally:
        active_stats.reset(token)


def read_usage(value: Any) -> None:
    if value is None:
        return
    if not isinstance(value, dict):
        raise InferenceError("invalid_inference_response")
    stats = active_stats.get()
    for key, attribute in (
        ("prompt_tokens", "input_tokens"),
        ("completion_tokens", "output_tokens"),
    ):
        count = value.get(key)
        if count is not None:
            if type(count) is not int or count < 0:
                raise InferenceError("invalid_inference_response")
            if stats is not None:
                setattr(stats, attribute, count)


class ModelMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1, max_length=32000)


class ModelClient(Protocol):
    async def healthy(self) -> bool: ...

    def stream(self, messages: Sequence[ModelMessage]) -> AsyncIterator[str]: ...


class MockModelClient:
    async def healthy(self) -> bool:
        return True

    async def stream(self, messages: Sequence[ModelMessage]) -> AsyncIterator[str]:
        if not messages or messages[-1].role != "user":
            raise ValueError("The last message must be a user message")
        response = "[Mock response — no AI inference] " + messages[-1].content
        for message in messages:
            if message.role == "system" and message.content.startswith("SOURCE_CONTEXT_JSON:"):
                sources = json.loads(message.content.split(":", 1)[1])
                response += "\n\nRetrieved excerpts (mock, not a generated answer):\n" + "\n".join(
                    f"[{source['title']}] {source['text']}" for source in sources
                )
        for start in range(0, len(response), 24):
            await asyncio.sleep(0)  # Cooperative scheduling and cancellation.
            yield response[start : start + 24]


class OpenAIModelClient:
    """Private local OpenAI-compatible serving, never a silent mock fallback."""

    def __init__(self, settings: "Settings", transport: "httpx.AsyncBaseTransport | None" = None):
        self.settings = settings
        self.transport = transport

    def connection(self) -> "httpx.AsyncClient":
        if not self.settings.model_base_url:
            raise InferenceError()
        return httpx.AsyncClient(
            base_url=self.settings.model_base_url.rstrip("/") + "/",
            timeout=httpx.Timeout(self.settings.generation_timeout, connect=3),
            headers=(
                {"Authorization": "Bearer " + self.settings.model_api_key}
                if self.settings.model_api_key
                else {}
            ),
            transport=self.transport,
        )

    async def healthy(self) -> bool:
        async with self.connection() as client:
            response = await client.get("models")
            response.raise_for_status()
            return any(row.get("id") == self.settings.model_name for row in response.json()["data"])

    def completion_url(self) -> str:
        return "chat/completions"

    async def stream(self, messages: Sequence[ModelMessage]) -> AsyncIterator[str]:
        try:
            async with (
                self.connection() as client,
                client.stream(
                    "POST",
                    self.completion_url(),
                    json={
                        "model": self.settings.model_name,
                        "messages": [m.model_dump() for m in messages],
                        "stream": True,
                        "stream_options": {"include_usage": True},
                        "max_tokens": self.settings.model_max_output_tokens,
                        "temperature": self.settings.model_temperature,
                    },
                ) as response,
            ):
                if response.status_code == 404:
                    raise InferenceError("model_not_available")
                response.raise_for_status()
                ended = False
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    if payload == "[DONE]":
                        ended = True
                        break
                    if len(payload) > 1024 * 1024:
                        raise InferenceError("invalid_inference_response")
                    try:
                        data = json.loads(payload)
                    except json.JSONDecodeError as exc:
                        raise InferenceError(
                            "generation_failed", reason="invalid_stream_json"
                        ) from exc
                    if not isinstance(data, dict):
                        raise InferenceError("invalid_inference_response")
                    read_usage(data.get("usage"))
                    if "error" in data:
                        error = data["error"]
                        raise InferenceError(
                            "generation_failed",
                            reason="provider_stream_error",
                            provider_error_code=error.get("code")
                            if isinstance(error, dict)
                            else None,
                        )
                    choices = data.get("choices", [])
                    if not isinstance(choices, list):
                        raise InferenceError("generation_failed", reason="invalid_stream_shape")
                    for choice in choices:
                        if not isinstance(choice, dict) or not isinstance(
                            choice.get("delta", {}), dict
                        ):
                            raise InferenceError("generation_failed", reason="invalid_stream_shape")
                        content = choice.get("delta", {}).get("content")
                        if content is not None:
                            if not isinstance(content, str):
                                raise InferenceError(
                                    "generation_failed", reason="invalid_stream_delta"
                                )
                            yield content
                if not ended:
                    raise InferenceError("generation_failed", reason="stream_terminated_early")
        except httpx.TimeoutException as exc:
            raise InferenceError("inference_timeout") from exc
        except httpx.HTTPError as exc:
            raise InferenceError() from exc


class VLLMModelClient(OpenAIModelClient):
    """NVIDIA/Linux serving using the shared OpenAI-compatible implementation."""


class CloudflareModelClient(OpenAIModelClient):
    """Workers AI native endpoint with strict text choices; no response coercion."""

    def completion_url(self) -> str:
        # The compatible endpoint has emitted numeric content deltas for this
        # model. The native route preserves its text choices, including leading
        # zeroes. Keep the shared strict parser; the duplicate `response` field
        # is not a second output channel or a fallback.
        return (
            self.settings.model_base_url.rstrip("/").removesuffix("/v1")
            + "/run/"
            + self.settings.model_name
        )

    async def healthy(self) -> bool:
        async with self.connection() as client:
            response = await client.get(
                self.settings.model_base_url.rstrip("/").removesuffix("/v1") + "/models/search",
                params={"search": self.settings.model_name, "per_page": 20},
            )
            response.raise_for_status()
            if len(response.content) > 1024 * 1024:
                return False
            data = response.json()
            return data.get("success") is True and any(
                isinstance(row, dict) and row.get("name") == self.settings.model_name
                for row in data.get("result", [])
            )


class OllamaModelClient(OpenAIModelClient):
    """Native host Ollama /v1; no model downloads, cloud routing or silent fallback."""


def build_model_client(settings: Settings) -> ModelClient:
    if settings.model_backend == "mock":
        return MockModelClient()
    if settings.model_backend == "cloudflare":
        return CloudflareModelClient(settings)
    if settings.model_backend == "ollama":
        return OllamaModelClient(settings)
    return VLLMModelClient(settings)


def model_metadata(settings: Settings) -> dict[str, Any]:
    identifier = settings.model_name
    if settings.model_backend == "mock":
        identifier = "deterministic-mock"
    elif "://" in identifier or not re.fullmatch(
        r"(?:@cf/)?[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}", identifier
    ):
        identifier = "configured-model"
    return {
        "id": "default",
        "name": "Onesa Chat",
        "backend": settings.model_backend,
        "model_identifier": identifier,
        "context_tokens": settings.model_context_length,
        "modalities": settings.model_modalities,
        "quantization": settings.model_quantization,
        "revision": settings.model_revision,
        "real_inference": settings.model_backend != "mock",
    }
