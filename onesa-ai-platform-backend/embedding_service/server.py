"""Bounded, bearer-protected local serving of a pinned Qwen embedding model."""

import argparse
import hashlib
import math
import os
import secrets
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.types import ASGIApp, Receive, Scope, Send

MODEL = "Qwen/Qwen3-Embedding-0.6B"
REVISION = "97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3"
WEIGHT_SHA256 = "0437e45c94563b09e13cb7a64478fc406947a93cb34a7e05870fc8dcd48e23fd"
MAX_BODY = 65536


class Boundary:
    def __init__(self, app: ASGIApp, key: str):
        self.app, self.key = app, key

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        original_send = send

        async def private_send(message):
            if message["type"] == "http.response.start":
                message["headers"] = list(message.get("headers", [])) + [
                    (b"cache-control", b"no-store"),
                    (b"x-content-type-options", b"nosniff"),
                ]
            await original_send(message)

        send = private_send
        if scope["path"] != "/v1/embeddings":
            await self.app(scope, receive, send)
            return
        headers = dict(scope["headers"])
        supplied = headers.get(b"authorization", b"")
        if not secrets.compare_digest(supplied, b"Bearer " + self.key.encode()):
            await JSONResponse({"error": {"code": "unauthorized"}}, status_code=401)(
                scope, receive, send
            )
            return
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > MAX_BODY:
                await JSONResponse({"error": {"code": "body_too_large"}}, status_code=413)(
                    scope, receive, send
                )
                return
            if not message.get("more_body", False):
                break

        async def replay() -> dict:
            return {"type": "http.request", "body": bytes(body), "more_body": False}

        await self.app(scope, replay, send)


class EmbeddingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: Literal["Qwen/Qwen3-Embedding-0.6B"]
    input: list[str] = Field(min_length=1, max_length=16)
    dimensions: Literal[256, 1024] = 256


class EmbeddingRow(BaseModel):
    object: Literal["embedding"] = "embedding"
    index: int
    embedding: list[float]


class EmbeddingResponse(BaseModel):
    object: Literal["list"] = "list"
    model: str
    data: list[EmbeddingRow]


def create_app(encode: Callable[[list[str], int], list[list[float]]], key: str) -> FastAPI:
    if len(key) < 32:
        raise ValueError("Embedding service requires a bearer key of at least 32 characters")
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(Boundary, key=key)
    gate = threading.BoundedSemaphore(1)

    @app.exception_handler(RequestValidationError)
    async def invalid(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse({"error": {"code": "invalid_request"}}, status_code=422)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ready"}

    @app.post("/v1/embeddings", response_model=EmbeddingResponse)
    def embeddings(body: EmbeddingRequest) -> EmbeddingResponse:
        if any(not value.strip() or len(value) > 8192 for value in body.input):
            raise HTTPException(422, "Invalid embedding input")
        if sum(len(value) for value in body.input) > 32768:
            raise HTTPException(413, "Embedding batch too large")
        if not gate.acquire(blocking=False):
            raise HTTPException(429, "Embedding service busy")
        try:
            vectors = encode(body.input, body.dimensions)
            if len(vectors) != len(body.input) or any(
                len(vector) != body.dimensions
                or not all(math.isfinite(v) for v in vector)
                or abs(sum(v * v for v in vector) - 1) > 0.001
                for vector in vectors
            ):
                raise ValueError("Invalid encoder outcome")
            return EmbeddingResponse(
                model=MODEL,
                data=[EmbeddingRow(index=i, embedding=v) for i, v in enumerate(vectors)],
            )
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(503, "Embedding service unavailable") from None
        finally:
            gate.release()

    return app


def load_encoder(directory: Path, device: str) -> Callable[[list[str], int], list[list[float]]]:
    import torch
    from sentence_transformers import SentenceTransformer

    if not directory.is_dir():
        raise ValueError("Use an existing verified local model directory")
    if directory.name != REVISION:
        raise ValueError("Model directory must identify the qualified pinned revision")
    with (directory / "model.safetensors").open("rb") as weights:
        if hashlib.file_digest(weights, "sha256").hexdigest() != WEIGHT_SHA256:
            raise ValueError("Model weights do not match the qualified publisher checksum")
    if device == "mps" and not torch.backends.mps.is_available():
        raise ValueError("Requested MPS device is unavailable")
    torch.set_num_threads(2)
    model = SentenceTransformer(
        str(directory),
        device=device,
        local_files_only=True,
        trust_remote_code=False,
        model_kwargs={"dtype": torch.float32},
    )
    model.max_seq_length = 2048

    def encode(texts: list[str], dimensions: int) -> list[list[float]]:
        # Check before the library's automatic truncation: never silently drop text.
        lengths = model.tokenizer(texts, padding=False, truncation=False)["input_ids"]
        if any(len(tokens) > model.max_seq_length for tokens in lengths):
            raise HTTPException(413, "Embedding input exceeds token limit")
        return model.encode(
            texts,
            batch_size=4,
            truncate_dim=dimensions,
            normalize_embeddings=True,
            show_progress_bar=False,
        ).tolist()

    return encode


if __name__ == "__main__":
    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("--model-directory", type=Path, required=True)
    parser.add_argument("--device", choices=["cpu", "mps"], default="mps")
    parser.add_argument("--port", type=int, default=8364)
    args = parser.parse_args()
    encoder = load_encoder(args.model_directory, args.device)
    application = create_app(encoder, os.environ.get("ONESA_EMBEDDING_API_KEY", ""))
    uvicorn.run(application, host="127.0.0.1", port=args.port, access_log=False)
