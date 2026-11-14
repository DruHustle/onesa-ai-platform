"""Small explicit HTTP health load probe; no fabricated inference benchmark."""

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor

import httpx

parser = argparse.ArgumentParser()
parser.add_argument("url")
parser.add_argument("--requests", type=int, default=20)
parser.add_argument("--workers", type=int, default=4)
args = parser.parse_args()
if not 1 <= args.requests <= 10000 or not 1 <= args.workers <= 32:
    raise SystemExit("Requests/workers exceed bounded probe limits")


def probe(_: int) -> dict:
    started = time.monotonic()
    with httpx.Client(timeout=10) as client:
        response = client.get(args.url)
    return {"status": response.status_code, "seconds": time.monotonic() - started}


with ThreadPoolExecutor(max_workers=args.workers) as pool:
    results = list(pool.map(probe, range(args.requests)))
latency = sorted(r["seconds"] for r in results)
print(
    json.dumps(
        {
            "requests": len(results),
            "success": sum(r["status"] == 200 for r in results),
            "mean_seconds": sum(latency) / len(latency),
            "p95_seconds": latency[int((len(latency) - 1) * 0.95)],
        },
        indent=2,
    )
)
