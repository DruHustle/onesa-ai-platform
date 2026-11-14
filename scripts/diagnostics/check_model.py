"""Probe a configured already-running inference server; no weight downloads."""

import json
import time

import httpx
from app.config import Settings

config = Settings()
if config.model_backend != "vllm":
    raise SystemExit(
        "Set ONESA_MODEL_BACKEND=vllm and an already-running private model URL"
    )
with httpx.Client(
    base_url=config.model_base_url.rstrip("/") + "/",
    timeout=120,
    headers={"Authorization": "Bearer " + config.model_api_key},
) as client:
    discovery = client.get("models")
    discovery.raise_for_status()
    if config.model_name not in [r["id"] for r in discovery.json()["data"]]:
        raise SystemExit("Configured model is not loaded")
    started = time.monotonic()
    response = client.post(
        "chat/completions",
        json={
            "model": config.model_name,
            "messages": [{"role": "user", "content": "Say hello in one sentence."}],
            "max_tokens": 32,
            "stream": False,
        },
    )
    response.raise_for_status()
    elapsed = time.monotonic() - started
    result = response.json()
    tokens = result.get("usage", {}).get("completion_tokens")
    print(
        json.dumps(
            {
                "model": config.model_name,
                "latency_seconds": elapsed,
                "output_tokens": tokens,
                "tokens_per_second": tokens / elapsed if tokens else None,
                "output": result["choices"][0]["message"]["content"],
            },
            indent=2,
        )
    )
