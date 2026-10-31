"""Portable text inference client. No application state, tools or provider fallback.

This module intentionally has no Onesa application imports. Independent products
can vendor these reviewed bytes without importing another repository at runtime.
"""

import asyncio
import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Literal
from urllib.parse import urlsplit

import httpx

CONTRACT_VERSION = "onesa-inference-v1"
MAX_MESSAGES = 32
MAX_INPUT_CHARS = 32000
MAX_OUTPUT_CHARS = 8000
MAX_RESPONSE_BYTES = 65536


class CompletionError(ValueError):
    def __init__(self) -> None:
        super().__init__("Inference provider unavailable or response incompatible")


def https_base(value: str) -> str:
    """Only operator-selected HTTPS bases; never accept endpoints from a prompt."""
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        raise ValueError("Invalid AI endpoint") from None
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or "\\" in value
        or any(ord(c) <= 32 or ord(c) == 127 for c in value)
        or (port is not None and not 1 <= port <= 65535)
    ):
        raise ValueError("AI endpoint requires an HTTPS base without credentials or query")
    return value.rstrip("/")


@dataclass(frozen=True)
class Connection:
    provider: Literal["onesa", "openai-compatible"]
    base_url: str
    model: str = "default"
    api_key: str = field(default="", repr=False)
    session: str = field(default="", repr=False)
    csrf: str = field(default="", repr=False)
    origin: str = ""

    def __post_init__(self) -> None:
        https_base(self.base_url)
        if self.provider not in {"onesa", "openai-compatible"}:
            raise ValueError("Unknown inference provider")
        if not self.model or len(self.model) > 200 or any(ord(c) < 32 for c in self.model):
            raise ValueError("Invalid inference model")
        if self.provider == "onesa":
            origin = urlsplit(https_base(self.origin))
            if (
                self.origin != f"{origin.scheme}://{origin.netloc}"
                or not self.session
                or not self.csrf
            ):
                raise ValueError("Onesa requires a dedicated session, CSRF and exact origin")
        elif not self.api_key or len(self.api_key) > 8192:
            raise ValueError("Compatible provider requires an approved server credential")

    def client(self, transport: httpx.AsyncBaseTransport | None = None) -> httpx.AsyncClient:
        headers = {"Accept": "application/json", "Accept-Encoding": "identity"}
        cookies = {}
        if self.provider == "onesa":
            headers.update({"Origin": self.origin, "X-CSRF-Token": self.csrf})
            cookies["onesa_session"] = self.session
        else:
            headers["Authorization"] = "Bearer " + self.api_key
        return httpx.AsyncClient(
            base_url=https_base(self.base_url) + "/",
            headers=headers,
            cookies=cookies,
            timeout=httpx.Timeout(20, connect=5),
            follow_redirects=False,
            trust_env=False,
            transport=transport,
        )


@dataclass(frozen=True)
class Message:
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(frozen=True)
class Completion:
    text: str
    provider: str
    model: str
    inference_kind: Literal["real", "mock", "unverified"]
    contract_version: str = CONTRACT_VERSION
    revision: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None


def message_records(messages: Sequence[Message]) -> list[dict[str, str]]:
    if not 1 <= len(messages) <= MAX_MESSAGES or messages[-1].role != "user":
        raise ValueError("Supply bounded history ending in a user message")
    total = 0
    records = []
    for item in messages:
        if item.role not in {"system", "user", "assistant"} or not isinstance(item.content, str):
            raise ValueError("Unsupported text message")
        if not item.content.strip():
            raise ValueError("Empty text message")
        try:
            item.content.encode("utf-8")
        except UnicodeError:
            raise ValueError("Invalid Unicode text message") from None
        total += len(item.content)
        records.append({"role": item.role, "content": item.content})
    if total > MAX_INPUT_CHARS:
        raise ValueError("Inference input exceeds the contract limit")
    return records


async def json_response(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    *,
    expected_status: int = 200,
) -> dict[str, Any]:
    async with client.stream(method, path, json=payload) as response:
        response.raise_for_status()
        # Redirect responses must never be interpreted as successful contracts.
        if (
            response.status_code != expected_status
            or response.headers.get("content-type", "").split(";")[0].strip().lower()
            != "application/json"
            or response.headers.get("content-encoding", "identity").lower() != "identity"
        ):
            raise CompletionError()
        chunks = []
        size = 0
        async for part in response.aiter_bytes():
            size += len(part)
            if size > MAX_RESPONSE_BYTES:
                raise CompletionError()
            chunks.append(part)
        try:
            result = json.loads(b"".join(chunks))
        except (ValueError, RecursionError):
            # The byte ceiling does not bound JSON nesting. Treat decoder
            # exhaustion as an incompatible provider, without exposing its body.
            raise CompletionError() from None
        if not isinstance(result, dict) or "error" in result:
            raise CompletionError()
        return result


async def complete(
    connection: Connection,
    messages: Sequence[Message],
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> Completion:
    records = message_records(messages)
    try:
        async with asyncio.timeout(25), connection.client(transport) as client:
            if connection.provider == "onesa":
                result = await json_response(
                    client,
                    "POST",
                    "api/v1/inference/completions",
                    {"messages": records, "model_id": connection.model},
                )
                if (
                    result.get("contract_version") != CONTRACT_VERSION
                    or result.get("outcome") != "completed"
                ):
                    raise CompletionError()
                text = result["text"]
                metadata = result["model"]
                model = metadata["model_identifier"]
                real = metadata["real_inference"]
                if type(real) is not bool:
                    raise CompletionError()
                kind: Literal["real", "mock", "unverified"] = "real" if real else "mock"
                revision = metadata.get("revision")
            else:
                result = await json_response(
                    client,
                    "POST",
                    "chat/completions",
                    {
                        "messages": records,
                        "model": connection.model,
                        "stream": False,
                        "max_tokens": 1024,
                    },
                )
                choices = result["choices"]
                if not isinstance(choices, list) or len(choices) != 1:
                    raise CompletionError()
                choice = choices[0]
                if not isinstance(choice, dict):
                    raise CompletionError()
                message = choice["message"]
                if not isinstance(message, dict):
                    raise CompletionError()
                if (
                    choice.get("finish_reason") != "stop"
                    or message.get("role") != "assistant"
                    or message.get("tool_calls")
                    or message.get("function_call")
                    or message.get("refusal")
                ):
                    raise CompletionError()
                text, model, kind = message["content"], result["model"], "unverified"
                revision = None
            if not isinstance(text, str) or not text.strip() or len(text) > MAX_OUTPUT_CHARS:
                raise CompletionError()
            text.encode("utf-8")
            if not isinstance(model, str) or not model or len(model) > 256:
                raise CompletionError()
            if revision is not None and (not isinstance(revision, str) or len(revision) > 128):
                raise CompletionError()
            usage = result.get("usage", {})
            if not isinstance(usage, dict):
                raise CompletionError()
            counts = [usage.get(name) for name in ("prompt_tokens", "completion_tokens")]
            if any(v is not None and (type(v) is not int or v < 0) for v in counts):
                raise CompletionError()
            return Completion(
                text, connection.provider, model, kind, CONTRACT_VERSION, revision, *counts
            )
    except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError, TimeoutError):
        # Provider URLs, credentials, response bodies and exceptions never enter diagnostics.
        raise CompletionError() from None
