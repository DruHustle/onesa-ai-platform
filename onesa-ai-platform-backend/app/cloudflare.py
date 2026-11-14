"""Explicit Qwen Matryoshka256 conversion; hosted alias is not a pinned weight digest."""

import json
import math

import httpx

from app.config import Settings


def embeddings(
    texts: list[str],
    config: Settings,
    *,
    query: bool = False,
    transport: httpx.BaseTransport | None = None,
) -> list[list[float]]:
    if not 1 <= len(texts) <= 16 or any(not text or len(text) > 4000 for text in texts):
        raise ValueError("Cloudflare embedding input exceeds bounds")
    body: dict[str, object] = {"queries" if query else "documents": texts}
    if query and config.embedding_query_instruction:
        body["instruction"] = config.embedding_query_instruction
    with httpx.Client(timeout=httpx.Timeout(30, connect=3), transport=transport) as client:
        with client.stream(
            "POST",
            config.embedding_base_url.rstrip("/") + "/run/" + config.embedding_name,
            headers={"Authorization": "Bearer " + config.embedding_api_key},
            json=body,
        ) as response:
            response.raise_for_status()
            content = bytearray()
            for part in response.iter_bytes():
                content.extend(part)
                if len(content) > 1024 * 1024:
                    raise ValueError("Cloudflare embedding response exceeds bounds")
    result = json.loads(content)
    if result.get("success") is not True or result.get("errors"):
        raise ValueError("Cloudflare embedding unavailable")
    value = result["result"]
    rows = value["data"]
    # Only this reviewed MRL model may be projected; other dimensions fail closed.
    shape = value.get("shape")
    if (
        not isinstance(shape, list)
        or any(type(x) is not int for x in shape)
        or shape != [len(texts), 1024]
        or not isinstance(rows, list)
        or len(rows) != len(texts)
    ):
        raise ValueError("Cloudflare embedding shape is incompatible")
    output = []
    for row in rows:
        if (
            not isinstance(row, list)
            or len(row) != 1024
            or any(type(x) not in (int, float) or not math.isfinite(x) for x in row)
        ):
            raise ValueError("Cloudflare embedding values are invalid")
        vector = [float(x) for x in row[:256]]
        norm = math.sqrt(sum(x * x for x in vector))
        if not math.isfinite(norm) or norm <= 0:
            raise ValueError("Cloudflare embedding norm is invalid")
        output.append([x / norm for x in vector])
    return output
